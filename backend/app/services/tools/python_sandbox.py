import ast
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from typing import Any, Dict, Optional, Set


ALLOWED_MODULES: Set[str] = {
    "math",
    "statistics",
    "json",
    "csv",
    "collections",
    "itertools",
    "functools",
    "datetime",
    "decimal",
    "fractions",
    "re",
    "random",
}

FORBIDDEN_CALLS: Set[str] = {
    "eval",
    "exec",
    "compile",
    "open",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "dir",
    "input",
    "breakpoint",
    "exit",
    "quit",
}

_SVG_SCRIPT_RE = re.compile(r"(?is)<script[^>]*>.*?</script>")
_SVG_ON_ATTR_RE = re.compile(r'(?i)\son[a-z]+\s*=\s*(?:"[^"]*"|\'[^\']*\')')

_SANDBOX_PRELUDE = '''
import math, statistics, json, csv, collections, itertools, functools, datetime, decimal, fractions, re, html as _html
__svg_outputs = []

def plot_bar(labels, values, title="Bar Chart"):
    labels = [str(l) for l in labels][:24]
    vals = [float(v) for v in values][:len(labels)]
    if not vals:
        return ""
    max_v = max(max(vals), 1e-9)
    w, h = 520, max(160, 48 + len(labels) * 28)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="background:#0b1120;border-radius:10px;font-family:system-ui,sans-serif">']
    lines.append(f'<text x="16" y="24" fill="#e2e8f0" font-size="13" font-weight="600">{_html.escape(str(title))}</text>')
    for idx, (lbl, val) in enumerate(zip(labels, vals)):
        y = 42 + idx * 28
        bar_w = max(2, int((max(0.0, val) / max_v) * 290))
        lines.append(f'<text x="16" y="{y+14}" fill="#94a3b8" font-size="11">{_html.escape(lbl[:18])}</text>')
        lines.append(f'<rect x="135" y="{y+2}" width="{bar_w}" height="16" rx="4" fill="#38bdf8"/>')
        lines.append(f'<text x="{142+bar_w}" y="{y+14}" fill="#e2e8f0" font-size="11">{val:g}</text>')
    lines.append("</svg>")
    svg = "".join(lines)
    __svg_outputs.append(svg)
    return svg

def plot_line(x_labels, values, title="Trend Chart"):
    labels = [str(l) for l in x_labels][:40]
    vals = [float(v) for v in values][:len(labels)]
    if len(vals) < 2:
        return ""
    w, h, pad = 520, 220, 36
    mn, mx = min(vals), max(vals)
    span = (mx - mn) or 1.0
    pts = []
    for i, v in enumerate(vals):
        x = pad + (i / (len(vals) - 1)) * (w - 2 * pad)
        y = (h - pad) - ((v - mn) / span) * (h - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" style="background:#0b1120;border-radius:10px;font-family:system-ui,sans-serif">'
        f'<text x="16" y="22" fill="#e2e8f0" font-size="13" font-weight="600">{_html.escape(str(title))}</text>'
        f'<polyline fill="none" stroke="#38bdf8" stroke-width="2.5" points="{poly}"/>'
        f'<text x="{pad}" y="{h-8}" fill="#94a3b8" font-size="10">{_html.escape(labels[0][:12])}..{_html.escape(labels[-1][:12])} (min {mn:g}, max {mx:g})</text>'
        '</svg>'
    )
    __svg_outputs.append(svg)
    return svg
'''


class PythonSandboxTool:
    """Strictly isolated subprocess Python runner for statistics, numeric checks, and lightweight SVG charts."""

    name = "python_data_analysis"

    @classmethod
    def validate_ast(cls, code: str) -> Optional[str]:
        if not code or not code.strip():
            return "Empty Python code"
        if len(code) > 8000:
            return "Code exceeds 8,000 character limit"

        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            return f"SyntaxError at line {exc.lineno}: {exc.msg}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod not in ALLOWED_MODULES:
                        return f"Import of '{alias.name}' is blocked in sandbox"
            elif isinstance(node, ast.ImportFrom):
                root_mod = (node.module or "").split(".")[0]
                if root_mod not in ALLOWED_MODULES:
                    return f"Import from '{node.module}' is blocked in sandbox"
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__"):
                    return f"Access to dunder attribute '{node.attr}' is forbidden"
            elif isinstance(node, ast.Name):
                if node.id.startswith("__") and node.id != "__name__":
                    return f"Access to dunder identifier '{node.id}' is forbidden"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                    return f"Call to '{node.func.id}()' is forbidden in sandbox"
        return None

    @staticmethod
    def _sanitize_svg(raw_svg: str) -> str:
        clean = _SVG_SCRIPT_RE.sub("", raw_svg or "")
        clean = _SVG_ON_ATTR_RE.sub("", clean)
        return clean.strip()

    @classmethod
    def execute(
        cls,
        code: str,
        timeout_seconds: int = 6,
        memory_mb: int = 128,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        err = cls.validate_ast(code)
        if err:
            return {"ok": False, "status": "blocked", "error": err, "duration_ms": 0}

        # Scrub sensitive environment variables completely before spawning child process
        safe_env: Dict[str, str] = {}
        for k in ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "LANG", "LC_ALL"):
            if k in os.environ:
                safe_env[k] = os.environ[k]
        safe_env["PYTHONIOENCODING"] = "utf-8"

        resource_guard = ""
        if os.name == "posix":
            mem_bytes = max(32, int(memory_mb)) * 1024 * 1024
            cpu_sec = max(2, int(timeout_seconds))
            resource_guard = textwrap.dedent(
                f"""
                try:
                    import resource
                    resource.setrlimit(resource.RLIMIT_AS, ({mem_bytes}, {mem_bytes}))
                    resource.setrlimit(resource.RLIMIT_CPU, ({cpu_sec}, {cpu_sec}))
                except Exception:
                    pass
                """
            )

        runner_source = (
            resource_guard
            + _SANDBOX_PRELUDE
            + "\n"
            + textwrap.dedent(code)
            + '\nfor __s in __svg_outputs:\n    print("\\n__AUREVON_SVG_START__" + __s + "__AUREVON_SVG_END__")\n'
        )

        with tempfile.TemporaryDirectory(prefix="aurevon_py_") as sandbox_dir:
            script_path = os.path.join(sandbox_dir, "run.py")
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write(runner_source)

            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", script_path],
                    cwd=sandbox_dir,
                    env=safe_env,
                    capture_output=True,
                    text=True,
                    timeout=max(1, min(15, int(timeout_seconds))),
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return {
                    "ok": False,
                    "status": "timeout",
                    "error": f"Python sandbox exceeded {timeout_seconds}s time limit",
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                }

        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout = (proc.stdout or "")[:32000]
        stderr = (proc.stderr or "")[:4000]

        charts = []
        svg_pattern = re.compile(r"__AUREVON_SVG_START__(.*?)__AUREVON_SVG_END__", re.DOTALL)
        for match in svg_pattern.findall(stdout):
            sanitized = cls._sanitize_svg(match)
            if sanitized.startswith("<svg"):
                charts.append(sanitized)
        clean_stdout = svg_pattern.sub("", stdout).strip()

        if proc.returncode != 0:
            return {
                "ok": False,
                "status": "error",
                "stdout": clean_stdout[:4000],
                "error": stderr.strip() or f"Exited with code {proc.returncode}",
                "duration_ms": duration_ms,
            }

        return {
            "ok": True,
            "status": "success",
            "stdout": clean_stdout[:12000],
            "charts": charts[:2],
            "duration_ms": duration_ms,
        }
