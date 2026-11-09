import ast
import operator
import re
from typing import Dict, Any, Callable, List, Optional
from backend.app.services.research.search import WebSearchService
from backend.app.services.documents.rag import RAGService
from sqlalchemy.ext.asyncio import AsyncSession


class SafeCalculator:
    """Safely evaluates arithmetic expressions using AST without eval()."""

    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    @classmethod
    def evaluate(cls, expression: str) -> float:
        cleaned = re.sub(r"[^0-9\+\-\*\/\.\(\)\^\% ]", "", expression.replace("^", "**")).strip()
        tree = ast.parse(cleaned, mode="eval")
        return cls._eval_node(tree.body)

    @classmethod
    def _eval_node(cls, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)
            op = cls._operators.get(type(node.op))
            if not op:
                raise ValueError(f"Unsupported operator: {type(node.op)}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = cls._eval_node(node.operand)
            op = cls._operators.get(type(node.op))
            if not op:
                raise ValueError(f"Unsupported unary operator: {type(node.op)}")
            return op(operand)
        else:
            raise ValueError(f"Unsupported expression construct: {type(node)}")


class CodeAnalyzer:
    """Analyzes syntax, functions, classes, and structure of code snippets."""

    @classmethod
    def analyze(cls, code: str, language: str = "python") -> Dict[str, Any]:
        lang = language.lower().strip()
        lines = code.split("\n")
        total_lines = len(lines)
        non_empty = len([l for l in lines if l.strip()])

        if lang == "python":
            try:
                tree = ast.parse(code)
                functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                imports = [
                    alias.name
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Import)
                    for alias in node.names
                ]
                return {
                    "valid_syntax": True,
                    "total_lines": total_lines,
                    "non_empty_lines": non_empty,
                    "functions": functions,
                    "classes": classes,
                    "imported_modules": imports,
                }
            except SyntaxError as e:
                return {
                    "valid_syntax": False,
                    "syntax_error": str(e),
                    "error_line": e.lineno,
                    "total_lines": total_lines,
                }

        # Generic JS/TS/Other parser via regex
        fn_matches = re.findall(r"(?:function\s+([a-zA-Z0-9_$]+)|(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)", code)
        flat_fns = [m[0] or m[1] for m in fn_matches if m[0] or m[1]]
        class_matches = re.findall(r"class\s+([a-zA-Z0-9_$]+)", code)

        return {
            "valid_syntax": True,
            "language": lang,
            "total_lines": total_lines,
            "non_empty_lines": non_empty,
            "functions": flat_fns,
            "classes": class_matches,
        }


class ToolRegistry:
    """Central registry of approved and sandboxed tools executable by agents."""

    @classmethod
    async def execute_tool(
        cls,
        tool_name: str,
        arguments: Dict[str, Any],
        session: Optional[AsyncSession] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        name = tool_name.lower().strip()

        if name == "web_search":
            query = arguments.get("query", "")
            results = await WebSearchService.search(query, max_results=arguments.get("max_results", 4))
            return {"status": "success", "results": results}

        elif name == "calculator":
            expr = arguments.get("expression", "")
            try:
                val = SafeCalculator.evaluate(expr)
                return {"status": "success", "result": val}
            except Exception as e:
                return {"status": "error", "error": f"Math error: {str(e)}"}

        elif name == "code_analyzer":
            code = arguments.get("code", "")
            lang = arguments.get("language", "python")
            analysis = CodeAnalyzer.analyze(code, language=lang)
            return {"status": "success", "analysis": analysis}

        elif name == "document_search":
            if not session:
                return {"status": "error", "error": "Database session required for document search"}
            query = arguments.get("query", "")
            chunks = await RAGService.retrieve_relevant_chunks(session, query, user_id=user_id, top_k=3)
            return {"status": "success", "chunks": chunks}

        else:
            return {"status": "error", "error": f"Tool '{tool_name}' not found in registry."}

    @classmethod
    def list_available_tools(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": "web_search",
                "description": "Searches the web for facts, documentation, or real-time topics.",
                "parameters": {"query": "string", "max_results": "integer (optional)"},
            },
            {
                "name": "calculator",
                "description": "Safely evaluates mathematical expressions without shell access.",
                "parameters": {"expression": "string, e.g. (42 * 105) / 1.5"},
            },
            {
                "name": "code_analyzer",
                "description": "Parses and inspects code syntax, functions, and structure.",
                "parameters": {"code": "string", "language": "string (python/typescript/javascript)"},
            },
            {
                "name": "document_search",
                "description": "Searches user's uploaded documents via semantic vector index.",
                "parameters": {"query": "string"},
            },
        ]
