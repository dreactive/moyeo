def valid_result_base(db, result):
    run = db.get('run:' + result['run_id'])
    room = db.get('room:' + result['room_id'])
    return bool(
        run and room and not run.get('applied')
        and run['room_id'] == result['room_id']
        and run['base_versions'] == result['base_versions'] == room['versions']
    )

from backend.domain import apply_item_proposals, resolve_refs, add_constraint_proposal
from backend.services.consensus import apply_support


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

from copy import deepcopy


def apply_questions(room, proposals):
    answered = [q for q in room['questions'] if q['status'] == 'answered']
    members = {member['user_id'] for member in room['members']}
    for proposal in proposals:
        if proposal['owner_id'] is not None and proposal['owner_id'] not in members:
            raise ValueError('Unknown question owner')
        if any(q['id'] == proposal['id'] for q in answered):
            continue
        question = deepcopy(proposal)
        question.update(status='open', answer=None, answered_by=None)
        answered.append(question)
    room['questions'] = answered
