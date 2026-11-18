from backend.db import serialized
from backend.services.extraction import record_extraction_failure, latest_processed
from backend.domain import apply_item_proposals, resolve_refs, add_constraint_proposal
from backend.services.consensus import apply_support
from backend.services.events import publish_event
from backend.services.observations import get_observations
from backend.services.observations import known_place_ids
from backend.services.observations import merge_observations
from backend.services.observations import relevant_evidence
from backend.services.planning import build_plan, validate_effect
from backend.services.agent_requests import persist_requests, persist_partial_results, active_lookup
from copy import deepcopy


def valid_result_base(db, result):
    run = db.get('run:' + result['run_id'])
    room = db.get('room:' + result['room_id'])
    return bool(
        run and room and not run.get('applied')
        and run['room_id'] == result['room_id']
        and run['base_versions'] == result['base_versions'] == room['versions']
    )



def apply_proposals(room, result):
    refs = apply_item_proposals(room, result['item_proposals'])
    mapped = resolve_refs(result, refs)
    changed = [add_constraint_proposal(room, proposal) for proposal in mapped['constraint_proposals']]
    if any(changed):
        room['versions']['constraint_version'] += 1
        room.update(review_plan=None, active_target=None, confirmations=[])
    for observation in mapped['support_observations']:
        apply_support(room, observation, observation['author_id'])
    return mapped



def apply_questions(room, proposals):
    retained = {q['id']:deepcopy(q) for q in room['questions']}
    members = {member['user_id'] for member in room['members']}
    for proposal in proposals:
        if proposal['owner_id'] is not None and proposal['owner_id'] not in members:
            raise ValueError('Unknown question owner')
        if retained.get(proposal['id'], {}).get('status') in ('answered','cancelled','closed'):
            continue
        question = deepcopy(proposal)
        question.update(status='open', answer=None, answered_by=None)
        retained[question['id']] = question
    room['questions'] = list(retained.values())



def apply_plan(room, draft, old_observations, observations):
    basis = room['review_plan'] or room['current_plan'] or draft
    if basis and relevant_evidence(basis, observations) != relevant_evidence(basis, old_observations):
        room['versions']['evidence_version'] += 1
        room.update(review_plan=None, active_target=None, confirmations=[])
    if draft is not None:
        validate_plan_refs(room, draft, observations)
        room['current_plan'] = build_plan(room, draft, relevant_evidence(draft, observations))



def prepare_result(room, result, old_observations):
    updated = deepcopy(room)
    mapped = apply_proposals(updated, result)
    if 'pending_item_ids' in mapped:
        pending = mapped['pending_item_ids']
        if not isinstance(pending, list) or any(ref not in {i['id'] for i in updated['items']} for ref in pending):
            raise ValueError('Unknown pending item reference')
        updated['agent_pending_item_ids'] = list(dict.fromkeys(pending))
    observations = merge_observations(old_observations, mapped['observations'])
    if 'request_states' in mapped:
        persist_requests(updated, mapped['request_states'], observations)
    retired = {r['request_id']:r['status'] for r in updated.get('agent_requests', [])
               if r.get('status') in ('completed','cancelled','superseded','unsupported')}
    closed_questions = set()
    for q in updated['questions']:
        if q.get('field') in ('target_places','route_departure') and q.get('status')=='open' and q.get('target_ref') in retired:
            reason = retired[q['target_ref']]
            q.update(status='cancelled' if reason=='cancelled' else 'closed',closed_reason='request_'+reason)
            closed_questions.add(q['id'])
    mapped['questions'] = [q for q in mapped['questions'] if q['id'] not in closed_questions]
    failures = {str((f.get('tool_name'), f.get('arguments'))):deepcopy(f)
                for f in updated.get('agent_tool_failures', [])}
    succeeded = {(o['tool_name'], str(o.get('arguments', {}))) for o in mapped['observations']}
    failures = {key:f for key,f in failures.items()
                if (f.get('tool_name'),str(f.get('arguments', {}))) not in succeeded}
    for failure in mapped.get('tool_failures', []):
        failures[str((failure.get('tool_name'),failure.get('arguments')))] = deepcopy(failure)
    updated['agent_tool_failures'] = list(failures.values())
    validate_questions(updated, mapped['questions'], observations)
    apply_questions(updated, mapped['questions'])
    apply_plan(updated, mapped['plan_draft'], old_observations, observations)
    updated['conflicts'] = deepcopy(mapped['conflicts'])
    for conflict in updated['conflicts']:
        if not set(conflict['affected_item_ids']) <= {item['id'] for item in updated['items']}:
            raise ValueError('Invalid conflict item')
        for option in conflict['options']:
            validate_effect(updated, option['effect'], observations)
        conflict['base_versions'] = deepcopy(updated['versions'])
    persist_partial_results(updated, mapped)
    return updated, observations



@serialized
def apply_agent_result(db, result):
    if not valid_result_base(db, result):
        return False
    if result.get("extraction_report", {}).get("status") == "failed":
        record_extraction_failure(db, result)
        return False
    room_id = result['room_id']
    room, observations = prepare_result(db.get('room:' + room_id), result, get_observations(db, room_id))
    run = db.get('run:' + result['run_id'])
    run['applied'] = True
    if result.get('extraction_report'):
        run['extraction_report'] = result['extraction_report']
    records = {'room:' + room_id:room, 'run:' + result['run_id']:run}
    processed = result.get('last_processed_message_id')
    valid_ids = run.get('message_ids', [message['id'] for message in room['messages']])
    if processed is not None and processed in valid_ids:
        records['processed-message:' + room_id] = latest_processed(room['messages'], db.get('processed-message:' + room_id), processed)
        if result.get('extraction_report'):
            from backend.services.extraction import recovered_failures
            records['failed-extraction:' + room_id] = recovered_failures(db.get('failed-extraction:' + room_id) or {}, run['message_ids'], processed)
    db.put_many(records)
    db.observations[room_id] = observations
    publish_event(db, room_id, 'room.updated', {'changed':['items','constraints','questions','conflicts','current_plan','versions']})
    return True


def validate_questions(room, questions, observations=()):
    items = {item['id'] for item in room['items']}
    members = {member['user_id'] for member in room['members']}
    for question in questions:
        field = question['field']
        targets = items
        if field in ('origin','destination','lodging'):
            targets = {'anchor:' + field}
        elif field == 'constraint_value':
            targets = {c['id'] for c in room['constraints'] if c['owner_id'] == question['owner_id']}
        elif field == 'support_target':
            targets = items | {None}
        elif field == 'region':
            targets = {'config:region'}
        elif field in ('target_places','route_departure'):
            request = active_lookup(room, question.get('target_ref'), question.get('owner_id'))
            targets = {request['request_id']} if request else set()
            choices = question.get('place_choices', [])
            if not isinstance(choices, list) or not {c.get('place_ref') for c in choices} <= known_place_ids(observations):
                raise ValueError('Invalid observed lookup choices')
        elif field not in ('menu_selection','visit_duration'):
            raise ValueError('Unknown question field')
        if question['owner_id'] not in members | {None} or question['target_ref'] not in targets or not set(question['related_item_ids']) <= items:
            raise ValueError('Invalid question target')



def validate_plan_refs(room, draft, observations):
    selected = set(draft['selected_item_ids'])
    if not selected <= {item['id'] for item in room['items']}:
        raise ValueError('Unknown plan item')
    places = known_place_ids(observations)
    for day in draft['days']:
        for visit in day['visits']:
            if visit['item_id'] not in selected or visit['place_ref'] not in places:
                raise ValueError('Unknown plan visit reference')
    for item in draft.get('unplaced_items', []):
        if item.get('item_id') not in selected or item.get('place_ref') not in places | {None}:
            raise ValueError('Unknown unplaced visit reference')
