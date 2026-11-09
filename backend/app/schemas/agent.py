from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class AgentRunRequest(BaseModel):
    task: str = Field(..., min_length=3, description="Goal or objective for the autonomous agent")
    model: Optional[str] = None


class AgentRunResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    task: str
    status: str
    execution_log: List[Dict[str, Any]]
    final_output: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ToolInfoResponse(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
