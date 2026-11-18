"""Validated auxiliary facts. Models never supply authoritative authors or tools."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Id = Annotated[str, Field(min_length=1, max_length=200)]
Text = Annotated[str, Field(min_length=1, max_length=1000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Evidence(StrictModel):
    message_id: Id
    quote: Annotated[str, Field(min_length=1, max_length=10000)]


class AuxiliaryItem(StrictModel):
    title: Text
    mention_text: Text
    evidence: Evidence
    client_ref: Id | None = None
    existing_item_id: Id | None = None


class AuxiliaryCondition(StrictModel):
    key: Annotated[str, Field(min_length=1, max_length=64)]
    value: int | str | bool
    evidence: Evidence
    kind: Literal['hard', 'preference'] = 'hard'
    replaces_constraint_id: Id | None = None
    context_message_ids: Annotated[list[Id], Field(max_length=8)] = Field(default_factory=list)


class AuxiliaryOpinion(StrictModel):
    question_id: Id | None = None
    item_id: Id
    item_version: Annotated[int, Field(ge=1)]
    stance: Literal['support', 'oppose', 'withdraw', 'unclear']
    evidence: Evidence
    context_message_ids: Annotated[list[Id], Field(max_length=8)] = Field(default_factory=list)


class MissingField(StrictModel):
    stance: Literal['support', 'oppose', 'withdraw'] | None = None
    field: Annotated[str, Field(min_length=1, max_length=64)]
    target_ref: Id | None
    text: Text
    owner_id: Id | None
    source_message_ids: Annotated[list[Id], Field(max_length=20)] = Field(default_factory=list)
    source: Literal['user', 'history', 'observation'] = 'user'


class AuxiliaryRequest(StrictModel):
    intent: Literal['place_details']
    evidence: Evidence
    target_names: Annotated[list[Text], Field(max_length=20)] = Field(default_factory=list)
    excluded_names: Annotated[list[Text], Field(max_length=20)] = Field(default_factory=list)
    context_evidence: Annotated[list[Evidence], Field(max_length=8)] = Field(default_factory=list)


class AuxiliaryAnalysis(StrictModel):
    requests: Annotated[list[AuxiliaryRequest], Field(max_length=20)] = Field(default_factory=list)
    summary: Annotated[str, Field(max_length=2000)]
    needs_context: bool
    context_queries: Annotated[list[Text], Field(max_length=8)]
    missing_fields: Annotated[list[MissingField], Field(max_length=20)]
    unsupported: bool
    unsupported_reason: Annotated[str, Field(max_length=1000)]
    direct_text: Annotated[str, Field(max_length=2000)]
    noop: bool
    source_message_ids: Annotated[list[Id], Field(max_length=20)] = Field(default_factory=list)
    source_refs: Annotated[list[Id], Field(max_length=40)] = Field(default_factory=list)


class AuxiliaryBatch(StrictModel):
    item_proposals: Annotated[list[AuxiliaryItem], Field(max_length=40)] = Field(default_factory=list)
    constraint_proposals: Annotated[list[AuxiliaryCondition], Field(max_length=40)] = Field(default_factory=list)
    support_observations: Annotated[list[AuxiliaryOpinion], Field(max_length=40)] = Field(default_factory=list)
    analysis: AuxiliaryAnalysis
