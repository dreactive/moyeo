from fastapi import HTTPException
from pydantic import ValidationError
from backend.schemas import AnchorAnswer, MenuAnswer, StayAnswer, SupportAnswer, ValueAnswer

ANSWER_TYPES = {'origin':AnchorAnswer,'destination':AnchorAnswer,'lodging':AnchorAnswer,'menu_selection':MenuAnswer,'visit_duration':StayAnswer,'constraint_value':ValueAnswer,'support_target':SupportAnswer}


def validate_answer(room, question, actor_id, value):
    if question['owner_id'] not in (None, actor_id):
        raise HTTPException(403, 'Only question owner may answer')
    field = question['field']
    targets = {item['id'] for item in room['items']}
    if field == 'constraint_value':
        targets = {item['id'] for item in room['constraints'] if item['owner_id'] == actor_id}
    if field in ('origin','destination','lodging'):
        targets = {'anchor:' + field}
    if question['target_ref'] not in targets:
        raise HTTPException(409, 'Question target unavailable')
    try:
        return ANSWER_TYPES[field].model_validate(value).model_dump(exclude_none=True)
    except (ValidationError, KeyError):
        raise HTTPException(422, 'Invalid question answer')
