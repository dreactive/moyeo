from backend.schemas import AnchorAnswer, MenuAnswer, StayAnswer, SupportAnswer, ValueAnswer, LookupAnswer
from backend.services.agent_requests import active_lookup
from backend.services.consensus import apply_support
from backend.services.consensus import edit_constraint
from fastapi import HTTPException
from pydantic import ValidationError
from datetime import datetime, timezone


ANSWER_TYPES = {'origin':AnchorAnswer,'destination':AnchorAnswer,'lodging':AnchorAnswer,'menu_selection':MenuAnswer,'visit_duration':StayAnswer,'constraint_value':ValueAnswer,'support_target':SupportAnswer,'target_places':LookupAnswer,'region':ValueAnswer,'route_departure':ValueAnswer}


def validate_answer(room, question, actor_id, value):
    if question['owner_id'] not in (None, actor_id):
        raise HTTPException(403, 'Only question owner may answer')
    field = question['field']
    targets = {item['id'] for item in room['items']}
    if field == 'support_target':
        targets.add(None)
    if field == 'constraint_value':
        targets = {item['id'] for item in room['constraints'] if item['owner_id'] == actor_id}
    if field in ('target_places','route_departure'):
        request = active_lookup(room, question['target_ref'], actor_id)
        targets = {request['request_id']} if request else set()
    if field == 'region':
        targets = {'config:region'}
    if field in ('origin','destination','lodging'):
        targets = {'anchor:' + field}
    if question['target_ref'] not in targets:
        raise HTTPException(409, 'Question target unavailable')
    try:
        return ANSWER_TYPES[field].model_validate(value).model_dump(exclude_none=True)
    except (ValidationError, KeyError):
        raise HTTPException(422, 'Invalid question answer')



def answer_question(room, question_id, actor_id, value, observations=None):
    question = next((q for q in room['questions'] if q['id'] == question_id), None)
    if question is None:
        raise HTTPException(404, 'Question not found')
    if question.get('status') in ('cancelled','closed'):
        raise HTTPException(409, 'Question is closed')
    value = validate_answer(room, question, actor_id, value)
    field = question['field']
    if field == 'menu_selection':
        validate_menu_answer(room, question, value['menu_id'], observations or [])
    if field == 'support_target':
        resolve_support_answer(room, question, actor_id, value['item_id'])
    if field == 'target_places':
        resolve_lookup_answer(room, question, actor_id, value, observations or [])
    if field == 'region':
        region = value['value']
        if not isinstance(region,str) or not region.strip() or len(region)>100:
            raise HTTPException(422, 'Invalid search region')
        room['config']['region'] = region.strip()
    if field == 'route_departure':
        try:
            departure = datetime.fromisoformat(value['value'])
            if departure.tzinfo is None or departure <= datetime.now(timezone.utc):
                raise ValueError('Future timezone-aware departure required')
        except (ValueError,TypeError):
            raise HTTPException(422, 'A future departure with timezone is required') from None
        request = active_lookup(room, question['target_ref'], actor_id)
        request.update(departure_at=departure.isoformat(), route_timing='scheduled',answer=dict(value),status='pending')
    if field in ('origin','destination','lodging'):
        room['config'][field] = value
    if field == 'constraint_value':
        condition = edit_constraint(room, question['target_ref'], actor_id, value['value'])
        question['target_ref'] = condition['id']
    question.update(answer=value, answered_by=actor_id, status='answered')
    if field not in ('support_target','target_places','route_departure'):
        room['versions']['constraint_version'] += 1
        room.update(active_target=None, review_plan=None, confirmations=[])
    return question


def resolve_lookup_answer(room, question, actor_id, answer, observations):
    request = active_lookup(room, question['target_ref'], actor_id)
    names = [name.strip() for name in answer.get('target_names', [])]
    if any(not name or len(name)>1000 for name in names):
        raise HTTPException(422, 'Invalid lookup target names')
    ref = answer.get('place_ref')
    places = {p['id']:p for o in observations if o['tool_name']=='search_places'
              for p in o['result'].get('places', [])}
    if ref:
        offered = {choice.get('place_ref') for choice in question.get('place_choices', [])}
        if ref not in places or ref not in offered:
            raise HTTPException(422, 'Place is outside the observed choices')
        names = [places[ref]['name']]
        answer['target_names'] = names
    if not names:
        raise HTTPException(422, 'Lookup needs a target')
    target = question.get('target_name')
    original = request.get('target_names', [])
    if target and target in original:
        position = original.index(target)
        request['target_names'] = list(dict.fromkeys(original[:position]+names+original[position+1:]))
    else:
        request['target_names'] = list(dict.fromkeys(names))
    if ref:
        request['target_refs'] = list(dict.fromkeys(request.get('target_refs', []) + [ref]))
    request['unresolved_target_names'] = [name for name in request['target_names']
                                         if not any(p['name']==name for r,p in places.items()
                                                    if r in request.get('target_refs', []))]
    request['answer'] = dict(answer)
    request['status'] = 'resolved' if not request['unresolved_target_names'] else 'pending'




def resolve_support_answer(room, question, actor_id, item_id):
    parts = question['id'].split(':', 3)
    item = next((item for item in room['items'] if item['id'] == item_id), None)
    if question['owner_id'] != actor_id or len(parts) != 4 or parts[2] not in ('support','oppose','withdraw') or item is None:
        raise HTTPException(409, 'Support source unavailable')
    if question['related_item_ids'] and item_id not in question['related_item_ids']:
        raise HTTPException(409, 'Answer is outside the offered targets')
    observation = dict(item_id=item_id, item_version=item['item_version'], author_id=actor_id, stance=parts[2], source_message_id=parts[3])
    if not apply_support(room, observation, actor_id):
        raise HTTPException(409, 'Support source changed')
    question['target_ref'] = item_id


def validate_menu_answer(room, question, menu_id, observations):
    plan = room['current_plan']
    places = {item['place_ref'] for item in plan['item_snapshots'] if item['id'] == question['target_ref']} if plan else set()
    menus = {
        menu['id']
        for observation in observations
        if observation['tool_name'] == 'get_place_details' and observation['result']['place']['id'] in places
        for menu in observation['result']['menus']
    }
    if menu_id not in menus:
        raise HTTPException(422, 'Menu does not belong to the target place')
