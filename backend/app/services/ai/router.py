import re
from dataclasses import dataclass, field
from typing import List, Optional


INTENT_CATEGORIES = (
    "greeting",
    "general",
    "knowledge",
    "reasoning",
    "math",
    "programming",
    "document_analysis",
    "web_research",
    "data_analysis",
    "memory",
    "tool_execution",
    "app_help",
    "weather",
    "news",
    "currency",
    "age_date_calc",
)

_GREETING_PATTERN = re.compile(
    r"^\s*(?:hi+|hello+|hey+|heya|yo|hola|greetings|good\s+(?:morning|afternoon|evening|night)|howdy|sup|what'?s\s+up|how\s+are\s+you(?:\s+doing)?|thanks(?:\s+a\s+lot)?|thank\s+you(?:\s+so\s+much)?|ok(?:ay)?|cool|nice|bye|goodbye)(?:\s+(?:there|aurevon|ai|friend))?[\s!?.,]*(?:how\s+are\s+you(?:\s+doing)?[\s!?.]*)?$",
    re.IGNORECASE,
)

_MATH_EXPRESSION_RE = re.compile(
    r"(?:what\s+is\s+|calculate\s+|compute\s+|solve\s+|evaluate\s+)?([\(\)\d\.\+\-\*/\^%\s]{3,})",
    re.IGNORECASE,
)


@dataclass
class RoutingDecision:
    intent: str
    use_fast_greeting: bool = False
    fast_greeting_reply: Optional[str] = None
    needs_memory: bool = True
    needs_rag: bool = True
    suggested_tools: List[str] = field(default_factory=list)
    prefer_coding_model: bool = False
    compact_system_prompt: bool = False
    max_history_turns: int = 24
    reason: str = ""


class RequestRouter:
    """Zero-latency deterministic intent router that selects context, tools, and fast-paths."""

    _GREETING_REPLIES = [
        "Hello! I'm AUREVON AI. How can I help you today?",
        "Hi there! Ready when you are — what are we working on?",
        "Hey! How can I help you today?",
    ]

    _THANKS_REPLIES = [
        "You're welcome! Let me know if there's anything else I can help with.",
        "Happy to help! Feel free to ask whenever you need anything else.",
    ]

    _HOW_ARE_YOU_REPLIES = [
        "I'm running smoothly and ready to help. What would you like to tackle?",
    ]

    @classmethod
    def classify(
        cls,
        prompt: str,
        *,
        document_ids: Optional[List[str]] = None,
        web_search: bool = False,
        has_documents: bool = False,
        has_memories: bool = False,
        message_index_hint: int = 0,
    ) -> RoutingDecision:
        text = (prompt or "").strip()
        lower = text.lower()

        # 1. Instant conversational greeting fast-path (when no attachments or web search requested)
        if not document_ids and not web_search and _GREETING_PATTERN.match(text):
            if any(w in lower for w in ("thank", "thanks")):
                reply = cls._THANKS_REPLIES[len(text) % len(cls._THANKS_REPLIES)]
            elif "how are you" in lower:
                reply = cls._HOW_ARE_YOU_REPLIES[0]
            elif any(w in lower for w in ("bye", "goodbye")):
                reply = "Goodbye! Feel free to come back anytime."
            else:
                reply = cls._GREETING_REPLIES[(len(text) + message_index_hint) % len(cls._GREETING_REPLIES)]
            return RoutingDecision(
                intent="greeting",
                use_fast_greeting=True,
                fast_greeting_reply=reply,
                needs_memory=False,
                needs_rag=False,
                suggested_tools=[],
                compact_system_prompt=True,
                max_history_turns=6,
                reason="Pure conversational greeting/ack",
            )

        # 2. App Help (questions specifically about AUREVON AI features / setup / Control Centre)
        if any(
            k in lower
            for k in (
                "what is aurevon",
                "about aurevon",
                "how to use aurevon",
                "aurevon features",
                "aurevon help",
                "control centre",
                "control center",
                "admin console",
                "/admin",
                "how to upload document",
                "how does memory work",
            )
        ):
            return RoutingDecision(
                intent="app_help",
                needs_memory=has_memories,
                needs_rag=has_documents,
                compact_system_prompt=False,
                max_history_turns=16,
                reason="Question about AUREVON AI platform features",
            )

        # 3. Document Analysis (explicit attachment or file-focused prompt)
        if document_ids or any(
            k in lower
            for k in (
                "uploaded document",
                "attached file",
                "my document",
                "my file",
                "pdf",
                "docx",
                "xlsx",
                "spreadsheet",
                "summarize the doc",
                "in the document",
                "from the uploaded",
                "according to the file",
            )
        ):
            return RoutingDecision(
                intent="document_analysis",
                needs_memory=has_memories,
                needs_rag=True,
                suggested_tools=["knowledge_retrieval"],
                max_history_turns=20,
                reason="Document-grounded analysis requested",
            )

        # 4. Live Weather & Forecasts
        if any(
            k in lower
            for k in (
                "weather",
                "forecast",
                "will it rain",
                "is it raining",
                "is it going to rain",
                "temperature in",
                "temperature today",
                "temperature tomorrow",
                "humidity in",
                "climate in",
            )
        ):
            return RoutingDecision(
                intent="weather",
                needs_memory=False,
                needs_rag=False,
                suggested_tools=["weather"],
                compact_system_prompt=True,
                max_history_turns=12,
                reason="Live meteorological conditions or forecast query",
            )

        # 5. Exact Age and Date Calculations
        if any(
            k in lower
            for k in (
                "how old am i",
                "my age",
                "calculate age",
                "born on",
                "date of birth",
                "days between",
                "weeks between",
                "working days between",
                "days until",
            )
        ):
            return RoutingDecision(
                intent="age_date_calc",
                needs_memory=False,
                needs_rag=False,
                suggested_tools=["date_time"],
                compact_system_prompt=True,
                max_history_turns=12,
                reason="Exact calendar age or date span calculation",
            )

        # 6. Currency & Exchange Rates
        if (
            any(k in lower for k in ("exchange rate", "currency", "usd to lkr", "eur to usd", "gbp to lkr", "convert currency"))
            or bool(re.search(r"(?i)(?:convert\s+)?\d+(?:\.\d+)?\s*[a-zA-Z]{3}\s+(?:to|in|into)\s+[a-zA-Z]{3}", lower))
        ):
            return RoutingDecision(
                intent="currency",
                needs_memory=False,
                needs_rag=False,
                suggested_tools=["currency_converter"],
                compact_system_prompt=True,
                max_history_turns=12,
                reason="Live currency conversion or forex rate lookup",
            )

        # 7. Recent News & Headlines
        if any(
            k in lower
            for k in (
                "latest news",
                "recent news",
                "news headlines",
                "breaking news",
                "ai news",
                "tech news",
                "sri lankan news",
            )
        ):
            return RoutingDecision(
                intent="news",
                needs_memory=False,
                needs_rag=has_documents,
                suggested_tools=["news_search"],
                compact_system_prompt=False,
                max_history_turns=16,
                reason="Recent news reporting or topic headlines",
            )

        # 8. Web Research
        if web_search or any(
            k in lower
            for k in (
                "search the web",
                "look up online",
                "latest news",
                "current price",
                "today's news",
                "recent headlines",
                "web search",
            )
        ):
            return RoutingDecision(
                intent="web_research",
                needs_memory=has_memories,
                needs_rag=has_documents,
                suggested_tools=["web_search"],
                max_history_turns=16,
                reason="Live/web research requested",
            )

        # 5. Memory management ("remember that...", "what do you remember about me")
        if any(
            k in lower
            for k in (
                "remember that",
                "remember my",
                "save to memory",
                "save this to memory",
                "keep in mind",
                "what do you remember",
                "my preferences",
            )
        ):
            return RoutingDecision(
                intent="memory",
                needs_memory=True,
                needs_rag=False,
                max_history_turns=20,
                reason="Explicit memory storage or recall request",
            )

        # 6. Data Analysis (CSV, tables, statistics, chart/plot, python calculation over data)
        if any(
            k in lower
            for k in (
                "dataset",
                "csv",
                "mean",
                "median",
                "standard deviation",
                "variance",
                "correlation",
                "plot ",
                "chart",
                "bar chart",
                "line chart",
                "analyze this data",
                "analyze the numbers",
                "run python",
                "execute python",
            )
        ):
            return RoutingDecision(
                intent="data_analysis",
                needs_memory=has_memories,
                needs_rag=has_documents,
                suggested_tools=["python_data_analysis", "calculator"],
                max_history_turns=20,
                reason="Quantitative/tabular data analysis or visualization",
            )

        # 7. Tool Execution (explicit date/time/timezone/unit conversion queries)
        if any(
            k in lower
            for k in (
                "what time is it",
                "current time",
                "current date",
                "today's date",
                "what day is it",
                "utc time",
                "convert ",
            )
        ) and not ("code" in lower or "json" in lower or "typescript" in lower):
            tools = ["date_time"] if "time" in lower or "date" in lower or "day" in lower else ["calculator"]
            return RoutingDecision(
                intent="tool_execution",
                needs_memory=False,
                needs_rag=False,
                suggested_tools=tools,
                compact_system_prompt=True,
                max_history_turns=12,
                reason="Deterministic date/time or conversion tool lookup",
            )

        # 8. Math (arithmetic, scientific math, percentages, equations)
        has_math_ops = bool(re.search(r"\d+\s*[\+\-\*/\^%]\s*\d+", text))
        has_math_words = any(
            k in lower
            for k in (
                "calculate",
                "compute",
                "square root",
                "sqrt",
                "factorial",
                "percentage",
                "% of ",
                "sin(",
                "cos(",
                "log(",
                "sum of",
                "average of",
            )
        )
        if (has_math_ops or has_math_words) and not any(c in lower for c in ("def ", "function ", "class ", "import ", "```")):
            return RoutingDecision(
                intent="math",
                needs_memory=False,
                needs_rag=False,
                suggested_tools=["calculator"],
                compact_system_prompt=True,
                max_history_turns=12,
                reason="Mathematical expression or quantitative evaluation",
            )

        # 9. Programming / Software Engineering
        if any(
            k in lower
            for k in (
                "```",
                "python",
                "typescript",
                "javascript",
                "react",
                "fastapi",
                "sqlalchemy",
                "sql",
                "debug",
                "stack trace",
                "traceback",
                "refactor",
                "regex",
                "function",
                "algorithm",
                "api endpoint",
                "unit test",
                "pytest",
                "dockerfile",
            )
        ):
            return RoutingDecision(
                intent="programming",
                needs_memory=has_memories,
                needs_rag=has_documents,
                prefer_coding_model=True,
                suggested_tools=["python_data_analysis"] if "verify" in lower or "test" in lower else [],
                max_history_turns=24,
                reason="Programming / code generation / debugging task",
            )

        # 10. Reasoning / Planning / Architecture / Tradeoff analysis
        if any(
            k in lower
            for k in (
                "why ",
                "compare ",
                "tradeoff",
                "trade-off",
                "pros and cons",
                "architecture",
                "design a ",
                "step by step",
                "step-by-step",
                "analyze",
                "evaluate",
                "plan for",
                "strategy",
            )
        ):
            return RoutingDecision(
                intent="reasoning",
                needs_memory=has_memories,
                needs_rag=has_documents,
                max_history_turns=24,
                reason="Multi-step analytical reasoning or planning",
            )

        # 11. Knowledge / Factual explanation
        if any(
            k in lower
            for k in (
                "what is ",
                "who is ",
                "explain ",
                "define ",
                "how does ",
                "difference between ",
                "history of ",
            )
        ):
            return RoutingDecision(
                intent="knowledge",
                needs_memory=has_memories,
                needs_rag=has_documents,
                max_history_turns=16,
                reason="Knowledge or conceptual explanation",
            )

        # 12. General fallback
        return RoutingDecision(
            intent="general",
            needs_memory=has_memories,
            needs_rag=has_documents,
            max_history_turns=20,
            reason="General conversational request",
        )
