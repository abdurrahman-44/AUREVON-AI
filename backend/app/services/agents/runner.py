import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.services.agents.tools import ToolRegistry
from backend.app.services.ai.factory import get_ai_provider

logger = logging.getLogger("aurevon.agents.runner")


class AgentRunner:
    """Orchestrates multi-step agent planning, tool calling, state logging, and synthesis."""

    def __init__(self, session: AsyncSession, user_id: Optional[str] = None):
        self.session = session
        self.user_id = user_id
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    async def execute_task(self, task_description: str, model: Optional[str] = None) -> Dict[str, Any]:
        logs = []

        def log_step(step_name: str, details: Dict[str, Any]):
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "step": step_name,
                "details": details,
            }
            logs.append(entry)

        log_step("planning", {"objective": task_description, "status": "Deconstructing task into tool actions"})

        # Step 1: Detect suitable tool based on objective
        lower_task = task_description.lower()
        selected_tool = None
        tool_args = {}

        if any(w in lower_task for w in ["calculate", "math", "+", "*", "compute", "formula", "sqrt"]):
            selected_tool = "calculator"
            tool_args = {"expression": task_description}
        elif any(w in lower_task for w in ["analyze code", "def ", "function", "class ", "import "]):
            selected_tool = "code_analyzer"
            tool_args = {"code": task_description, "language": "python"}
        elif any(w in lower_task for w in ["document", "pdf", "file", "uploaded"]):
            selected_tool = "document_search"
            tool_args = {"query": task_description}
        else:
            selected_tool = "web_search"
            tool_args = {"query": task_description}

        if self.cancelled:
            log_step("cancelled", {"message": "Execution cancelled before tool run."})
            return {"status": "cancelled", "logs": logs, "output": "Task was cancelled."}

        # Step 2: Execute Tool
        log_step("tool_execution_start", {"tool": selected_tool, "arguments": tool_args})
        try:
            tool_result = await ToolRegistry.execute_tool(
                tool_name=selected_tool,
                arguments=tool_args,
                session=self.session,
                user_id=self.user_id,
            )
            log_step("tool_execution_complete", {"tool": selected_tool, "result": tool_result})
        except Exception as e:
            log_step("tool_error", {"tool": selected_tool, "error": str(e)})
            tool_result = {"status": "error", "error": str(e)}

        if self.cancelled:
            log_step("cancelled", {"message": "Execution cancelled after tool run."})
            return {"status": "cancelled", "logs": logs, "output": "Task was cancelled."}

        # Step 3: Synthesis Report
        log_step("synthesis", {"status": "Compiling final agent briefing"})
        final_summary = self._synthesize_report(task_description, selected_tool, tool_result)

        log_step("completed", {"status": "success"})

        return {
            "status": "completed",
            "logs": logs,
            "output": final_summary,
        }

    def _synthesize_report(self, task: str, tool: str, result: Dict[str, Any]) -> str:
        report = [
            f"### 🤖 Agent Execution Report",
            f"**Task Objective**: {task}",
            f"**Autonomous Tool Used**: `{tool}`",
            "",
            "#### Tool Findings:",
        ]

        if tool == "calculator":
            report.append(f"- **Calculated Result**: `{result.get('result', 'Error')}`")
        elif tool == "web_search":
            hits = result.get("results", [])
            for h in hits:
                report.append(f"- **[{h['title']}]({h['url']})**:\n  {h['snippet']}")
        elif tool == "code_analyzer":
            analysis = result.get("analysis", {})
            report.append(f"- **Valid Syntax**: {analysis.get('valid_syntax')}")
            report.append(f"- **Functions Detected**: {', '.join(analysis.get('functions', [])) or 'None'}")
            report.append(f"- **Classes Detected**: {', '.join(analysis.get('classes', [])) or 'None'}")
        elif tool == "document_search":
            chunks = result.get("chunks", [])
            for c in chunks:
                report.append(f"- **From {c['filename']}**: {c['content']}")
        else:
            report.append(f"```json\n{json.dumps(result, indent=2)}\n```")

        report.append("\n*Observation complete. All steps logged to audit record.*")
        return "\n".join(report)
