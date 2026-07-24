from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    REPORTING = "reporting"


@dataclass
class AgentMessage:
    sender: str
    receiver: str
    message_type: str
    payload: dict[str, Any]


@dataclass
class AgentResult:
    agent_id: str
    agent_type: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class Agent:
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state = AgentState.IDLE
        self.tools: dict[str, Callable] = {}
        self.messages_received: list[AgentMessage] = []

    def register_tool(self, name: str, func: Callable):
        self.tools[name] = func

    def use_tool(self, tool_name: str, **kwargs) -> Any:
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not registered")
        return self.tools[tool_name](**kwargs)

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        self.messages_received.append(message)
        logger.info(f"{self.agent_id} received {message.message_type} from {message.sender}")
        return None

    def get_state(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "state": self.state.value,
            "messages_received": len(self.messages_received),
        }
