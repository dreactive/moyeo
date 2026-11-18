"""Internal extraction schema; projected to the existing JSON AgentResult boundary."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(min_length=1, max_length=1000)]
Identifier = Annotated[str, Field(min_length=1, max_length=200)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class EvidenceQuote(StrictModel):
    message_id: Identifier
    quote: Text


class MessageAssessment(StrictModel):
    message_id: Identifier
    intents: Annotated[list[Literal['chitchat', 'place', 'condition', 'support', 'region', 'unclear']], Field(min_length=1, max_length=6)]


class ConstraintProposal(StrictModel):
    owner_id: Identifier
    key: Annotated[str, Field(min_length=1, max_length=64)]
    value: int | str | bool
    kind: Literal['hard', 'preference']
    replaces_constraint_id: Identifier | None
    evidence: EvidenceQuote


class ItemProposal(StrictModel):
    title: Text
    mention_text: Text
    existing_item_id: Identifier | None
    evidence: EvidenceQuote


class SupportProposal(StrictModel):
    item_id: Identifier
    item_version: Annotated[int, Field(ge=1)]
    author_id: Identifier
    stance: Literal['support', 'oppose', 'withdraw', 'unclear']
    evidence: EvidenceQuote


class ExtractionBatch(StrictModel):
    message_assessments: Annotated[list[MessageAssessment], Field(max_length=20)]
    constraint_proposals: Annotated[list[ConstraintProposal], Field(max_length=40)]
    item_proposals: Annotated[list[ItemProposal], Field(max_length=40)]
    support_observations: Annotated[list[SupportProposal], Field(max_length=40)]


class ConditionFact(StrictModel):
    key: Annotated[str, Field(min_length=1, max_length=64)]
    value: int | str | bool


class MessageFacts(StrictModel):
    places: Annotated[list[Text], Field(max_length=20)]
    conditions: Annotated[list[ConditionFact], Field(max_length=20)]
    intents: Annotated[list[Literal['chitchat', 'place', 'condition', 'support', 'region', 'unclear']], Field(min_length=1, max_length=6)]
