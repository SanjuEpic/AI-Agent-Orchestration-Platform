import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class Agent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    role: str
    system_prompt: str
    model_provider: str = Field(default="gemini")  # gemini, openai, anthropic
    model_name: str = Field(default="gemini-2.5-flash")
    memory_limit: int = Field(default=10)  # Rolling window size K
    tools: str = Field(default="")  # Comma-separated list of enabled tools (e.g. "search,calculator")
    channels: str = Field(default="telegram")  # Comma-separated channels (e.g. "telegram,slack")
    guardrails: str = Field(default="{}")  # JSON string of safety parameters/rules
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class Workflow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = Field(default=None)
    nodes_json: str = Field(default="[]")  # Serialized React Flow nodes
    edges_json: str = Field(default="[]")  # Serialized React Flow edges
    is_active: bool = Field(default=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class WorkflowRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflow.id")
    session_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="running")  # running, completed, failed
    started_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    completed_at: Optional[datetime.datetime] = Field(default=None)
    trigger_source: str = Field(default="manual")  # telegram, slack, schedule, manual
    trigger_metadata: str = Field(default="{}")  # JSON metadata (e.g., chat_id, user_name)

class RunLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_run_id: int = Field(foreign_key="workflowrun.id")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    step_type: str  # agent_thought, tool_call, tool_response, agent_message, inter_agent_msg, error
    node_id: Optional[str] = Field(default=None)  # React Flow node ID executing this step
    message_from: Optional[str] = Field(default=None)  # Sender name/agent ID
    message_to: Optional[str] = Field(default=None)  # Recipient name/agent ID
    content: str
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    thought_tokens: int = Field(default=0)
    usd_cost: float = Field(default=0.0)

class Schedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflow.id")
    name: str
    cron_expression: str  # e.g., "*/5 * * * *"
    chat_id: Optional[str] = Field(default=None)  # Telegram chat to deliver scheduled output to
    is_active: bool = Field(default=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class AgentMemory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflow.id")
    session_id: Optional[str] = Field(default=None, index=True)  # Scope facts to a specific chat session for memory decay
    key: str
    value: str
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class Message(SQLModel, table=True):
    """Stores the ongoing multi-turn chat history for rolling window session memory."""
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)  # maps to Telegram chat ID or Slack channel ID
    role: str  # user, assistant, system
    content: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class SystemSetting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: str


class UserSessionState(SQLModel, table=True):
    chat_id: str = Field(primary_key=True)
    active_workflow_id: Optional[int] = Field(default=None)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

