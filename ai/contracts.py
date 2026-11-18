"""Internal structural boundaries. Backend imports none of these types."""
from typing import Awaitable, Callable, NotRequired, Protocol, TypedDict


class AgentInput(TypedDict):
    run_id: str
    room_id: str
    base_versions: dict
    goal: str
    recent_messages: list[dict]
    conversation_context: NotRequired[list[dict]]
    members: list[dict]
    config: dict
    constraints: list[dict]
    items: list[dict]
    questions: list[dict]
    user_selection: dict | None
    current_plan: dict | None
    observations: list[dict]


class AgentResult(TypedDict):
    run_id: str
    room_id: str
    base_versions: dict
    constraint_proposals: list[dict]
    support_observations: list[dict]
    item_proposals: list[dict]
    plan_draft: dict | None
    observations: list[dict]
    conflicts: list[dict]
    questions: list[dict]
    completion: str
    last_processed_message_id: str | None
    candidates: NotRequired[list[dict]]
    extraction_report: NotRequired[dict]


class ModelBackend(Protocol):
    def generate_json(self, request: dict) -> dict: ...


class ToolExecutor(Protocol):
    async def execute(self, name: str, arguments: dict) -> dict: ...


TraceSink = Callable[[dict], Awaitable[None]]
