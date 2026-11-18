"""Editable developer sandbox inputs; no database room is read or changed."""
from typing import Literal
from pydantic import Field
from backend.schemas import Request, TripConfig, Versions


class DevContext(Request):
    config: TripConfig
    room_id: str = 'dev-sandbox'
    run_id: str = 'dev-run'
    base_versions: Versions = Field(default_factory=Versions)
    members: list[dict] = Field(default_factory=lambda: [{'user_id': 'u1', 'name': 'Developer'}])
    recent_messages: list[dict] = Field(default_factory=list)
    constraints: list[dict] = Field(default_factory=list)
    items: list[dict] = Field(default_factory=list)
    questions: list[dict] = Field(default_factory=list)
    observations: list[dict] = Field(default_factory=list)
    current_plan: dict | None = None
    user_selection: dict | None = None
    goal: str = 'manual_replan'


class SearchArguments(Request):
    query: str = Field(min_length=1)
    region: str = '여수'
    category: str | None = None


class DetailsArguments(Request):
    place_ref: str


class RouteArguments(Request):
    from_ref: str
    to_ref: str
    departure_at: str | None = None


class ItineraryArguments(Request):
    visits: list[dict]
    anchors: dict
    constraints: list[dict]
    route_legs: list[dict]


class CostArguments(Request):
    lines: list[dict]
    member_ids: list[str]
    budget_by_user: dict[str, int | None]


class SearchTool(Request):
    context: DevContext
    arguments: SearchArguments


class DetailsTool(Request):
    context: DevContext
    arguments: DetailsArguments


class RouteTool(Request):
    context: DevContext
    arguments: RouteArguments


class ItineraryTool(Request):
    context: DevContext
    arguments: ItineraryArguments | None = Field(default=None, description='Omit to derive canonical arguments from context. Explicit arguments must match context.')


class CostTool(Request):
    context: DevContext
    arguments: CostArguments | None = Field(default=None, description='Omit to derive canonical costs from observed prices and user inputs in context.')


class Utterance(Request):
    context: DevContext
    text: str = Field(min_length=1, max_length=10000, pattern=r'\S')
    author_id: str = 'u1'
    goal: Literal['new_message', 'manual_replan', 'extract'] = 'new_message'
