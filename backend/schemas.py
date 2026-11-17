from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class Request(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Versions(Request):
    participant_version: int = 1
    constraint_version: int = 1
    evidence_version: int = 1
    plan_revision: int = 0


class ConfirmationTarget(Versions):
    content_hash: str


class Register(Request):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)


class Login(Request):
    email: str
    password: str


class Anchor(Request):
    label: str
    address: str
    latitude: float
    longitude: float
    source_ref: str | None = None


class TripConfig(Request):
    region: str = '여수'
    start_date: str
    end_date: str
    per_person_budget_krw: int = Field(ge=0)
    transport: Literal['car'] = 'car'
    day_start_time: str = '09:00'
    day_end_time: str = '18:00'
    origin: dict | None = None
    destination: dict | None = None
    lodging: dict | None = None
    fixed_costs: list[dict] = Field(default_factory=list)


class CreateRoom(TripConfig):
    title: str = Field(min_length=1, max_length=200)


class JoinRoom(Request):
    invite_code: str


class TextMessage(Request):
    text: str = Field(min_length=1, max_length=10000)


class ValueAnswer(Request):
    value: Any


class Confirm(Request):
    target: ConfirmationTarget


class Activate(Request):
    plan_revision: int


class SelectOption(Request):
    option_id: str


class AgentRun(Request):
    reason: Literal['manual_replan']


class Register(Request):
    name: str
    email: str
    password: str

class AnchorAnswer(Request):
    label: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    source_ref: str | None = None
    address: str | None = None


class MenuAnswer(Request):
    menu_id: str
    quantity: float = Field(gt=0)
    scope: Literal['shared','per_person']


class StayAnswer(Request):
    stay_minutes: int = Field(gt=0)


class SupportAnswer(Request):
    item_id: str
