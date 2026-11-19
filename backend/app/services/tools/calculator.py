import ast
import math
import operator
import re
from typing import Any, Callable, Dict, Optional, Union


_BIN_OPS: Dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_UNARY_OPS: Dict[type, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_SAFE_FUNCS: Dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "ln": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "floor": math.floor,
    "ceil": math.ceil,
    "factorial": math.factorial,
    "radians": math.radians,
    "degrees": math.degrees,
}

_SAFE_CONSTS: Dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

# Unit conversion multipliers to base unit per category
_UNIT_CATEGORIES: Dict[str, Dict[str, float]] = {
    "length": {
        "m": 1.0, "meter": 1.0, "meters": 1.0,
        "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
        "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
        "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
        "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
        "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
        "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
        "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    },
    "mass": {
        "g": 1.0, "gram": 1.0, "grams": 1.0,
        "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0,
        "mg": 0.001,
        "lb": 453.59237, "lbs": 453.59237, "pound": 453.59237, "pounds": 453.59237,
        "oz": 28.349523, "ounce": 28.349523, "ounces": 28.349523,
    },
    "time": {
        "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
        "min": 60.0, "minute": 60.0, "minutes": 60.0,
        "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
        "d": 86400.0, "day": 86400.0, "days": 86400.0,
    },
    "data": {
        "b": 1.0, "byte": 1.0, "bytes": 1.0,
        "kb": 1024.0, "mb": 1024.0 ** 2, "gb": 1024.0 ** 3, "tb": 1024.0 ** 4,
    },
}

_TEMP_ALIASES = {
    "c": "c", "celsius": "c", "degc": "c",
    "f": "f", "fahrenheit": "f", "degf": "f",
    "k": "k", "kelvin": "k",
}

_CONVERSION_RE = re.compile(
    r"^\s*(?:convert\s+)?(-?\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+(?:to|in|into)\s+([a-zA-Z]+)\s*\??$",
    re.IGNORECASE,
)

_PERCENT_OF_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*%\s+of\s+(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


class CalculatorTool:
    """Safe AST scientific calculator and physical/digital unit converter (no eval())."""

    name = "calculator"

    @classmethod
    def _convert_units(cls, value: float, src_unit: str, dst_unit: str) -> Optional[Dict[str, Any]]:
        s = src_unit.lower().strip()
        d = dst_unit.lower().strip()

        if s in _TEMP_ALIASES and d in _TEMP_ALIASES:
            sc, dc = _TEMP_ALIASES[s], _TEMP_ALIASES[d]
            if sc == "c":
                celsius = value
            elif sc == "f":
                celsius = (value - 32.0) * 5.0 / 9.0
            else:
                celsius = value - 273.15

            if dc == "c":
                out = celsius
            elif dc == "f":
                out = (celsius * 9.0 / 5.0) + 32.0
            else:
                out = celsius + 273.15
            return {
                "input": f"{value} {src_unit}",
                "converted": round(out, 6),
                "unit": dst_unit,
                "formatted": f"{round(out, 4):g} {dst_unit}",
            }

        for cat_units in _UNIT_CATEGORIES.values():
            if s in cat_units and d in cat_units:
                base_val = value * cat_units[s]
                out = base_val / cat_units[d]
                return {
                    "input": f"{value} {src_unit}",
                    "converted": round(out, 6),
                    "unit": dst_unit,
                    "formatted": f"{round(out, 6):g} {dst_unit}",
                }
        return None

    @classmethod
    def _eval_node(cls, node: ast.AST) -> Union[int, float]:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            ident = node.id.lower()
            if ident in _SAFE_CONSTS:
                return _SAFE_CONSTS[ident]
            raise ValueError(f"Unknown identifier: {node.id}")
        if isinstance(node, ast.BinOp):
            op_fn = _BIN_OPS.get(type(node.op))
            if not op_fn:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(float(right)) > 1000:
                raise ValueError("Exponent exceeds safe magnitude limit (1000)")
            return op_fn(left, right)
        if isinstance(node, ast.UnaryOp):
            op_fn = _UNARY_OPS.get(type(node.op))
            if not op_fn:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op_fn(cls._eval_node(node.operand))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only direct safe math functions are permitted")
            fn_name = node.func.id.lower()
            fn = _SAFE_FUNCS.get(fn_name)
            if not fn:
                raise ValueError(f"Unsupported math function: {fn_name}")
            if node.keywords:
                raise ValueError("Keyword arguments are not supported")
            args = [cls._eval_node(a) for a in node.args]
            if fn_name in ("min", "max", "sum"):
                return fn(args)
            return fn(*args)
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    @classmethod
    def extract_expression_from_prompt(cls, prompt: str) -> Optional[str]:
        text = (prompt or "").strip()
        conv = _CONVERSION_RE.match(text)
        if conv:
            return text
        if _PERCENT_OF_RE.search(text):
            m = _PERCENT_OF_RE.search(text)
            if m:
                return f"({m.group(1)} / 100) * {m.group(2)}"
        # Explicit arithmetic snippet inside a short query
        if len(text) <= 160:
            candidate = re.sub(
                r"(?i)^(what\s+is|calculate|compute|evaluate|solve)\s+",
                "",
                text,
            ).rstrip("?.! ").strip()
            candidate = candidate.replace("^", "**")
            if any(op in candidate for op in ("+", "-", "*", "/", "sqrt(", "sin(", "cos(", "log(", "factorial(")):
                # Only treat as pure expression if characters fall inside math charset
                if re.fullmatch(r"[0-9a-zA-Z\.\+\-\*/\(\),%\s_]+", candidate):
                    return candidate
        return None

    @classmethod
    def execute(cls, expression: str) -> Dict[str, Any]:
        raw = (expression or "").strip()
        if not raw:
            return {"ok": False, "error": "Empty expression"}

        # 1. Unit conversion check
        conv_match = _CONVERSION_RE.match(raw)
        if conv_match:
            val = float(conv_match.group(1))
            converted = cls._convert_units(val, conv_match.group(2), conv_match.group(3))
            if converted:
                return {"ok": True, "mode": "unit_conversion", **converted}

        # 2. Percentage shorthand ("15% of 240")
        expr_norm = _PERCENT_OF_RE.sub(lambda m: f"(({m.group(1)} / 100) * {m.group(2)})", raw)
        expr_norm = expr_norm.replace("^", "**").strip()
        if len(expr_norm) > 250:
            return {"ok": False, "error": "Expression too long (max 250 chars)"}

        try:
            tree = ast.parse(expr_norm, mode="eval")
            value = cls._eval_node(tree.body)
            if isinstance(value, float):
                if abs(value - round(value)) < 1e-12:
                    display = int(round(value))
                else:
                    display = round(value, 10)
            else:
                display = value
            return {
                "ok": True,
                "mode": "expression",
                "expression": raw,
                "result": display,
            }
        except ZeroDivisionError:
            return {"ok": False, "error": "Division by zero"}
        except Exception as exc:
            return {"ok": False, "error": f"Invalid expression: {exc}"}
