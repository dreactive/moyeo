import hashlib
import json
from copy import deepcopy
from fastapi import HTTPException


HASH_FIELDS = ('selected_item_ids','item_snapshots','days','cost','evidence')
IGNORED_TIMES = {'retrieved_at','observed_at','provider_updated_at'}


def substantive(value):
    if isinstance(value, dict):
        return {key:substantive(item) for key,item in value.items() if key not in IGNORED_TIMES}
    if isinstance(value, list):
        return [substantive(item) for item in value]
    return value


def semantic_plan_hash(snapshot):
    content = substantive({key:snapshot.get(key) for key in HASH_FIELDS})
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

from fastapi import HTTPException
from copy import deepcopy


def freeze_review(room, target):
    plan = room['review_plan'] or room['current_plan']
    if plan is None or target != plan['confirmation_target']:
        raise HTTPException(409, 'Confirmation target changed')
    for key in ('participant_version','constraint_version','evidence_version'):
        if target[key] != room['versions'][key]:
            raise HTTPException(409, 'Review inputs changed')
    if room['review_plan'] is None:
        room['review_plan'] = deepcopy(plan)
        room['active_target'] = deepcopy(target)
    return room['review_plan']

from datetime import datetime, timezone


def record_confirmation(room, actor_id, target, stance):
    if actor_id not in [member['user_id'] for member in room['members']]:
        raise HTTPException(403, 'Room membership required')
    freeze_review(room, target)
    room['confirmations'] = [vote for vote in room['confirmations'] if vote['user_id'] != actor_id]
    room['confirmations'].append(dict(user_id=actor_id, target=deepcopy(target), stance=stance, created_at=datetime.now(timezone.utc).isoformat()))


def ready_to_confirm(room, plan):
    if plan['validation'] != 'ready' or plan['blocking_conflict_ids']:
        return False
    if any(conflict['blocking'] and conflict['status'] == 'open' for conflict in room['conflicts']):
        return False
    return not any(condition['kind'] == 'hard' and condition['status'] == 'needs_owner_confirmation' for condition in room['constraints'])


def finalize_plan(room):
    plan = room['review_plan']
    members = {member['user_id'] for member in room['members']}
    voters = {vote['user_id'] for vote in room['confirmations'] if vote['stance'] == 'confirm' and vote['target'] == room['active_target']}
    if plan is None or voters != members or not ready_to_confirm(room, plan):
        return False
    if room['confirmed_plan'] == plan:
        return False
    room['confirmed_plan'] = deepcopy(plan)
    return True


def activate_plan(room, plan_revision):
    plan = room['current_plan']
    if plan is None or plan['plan_revision'] != plan_revision:
        raise HTTPException(409, 'Draft revision changed')
    room.update(review_plan=None, active_target=None, confirmations=[])
    freeze_review(room, plan['confirmation_target'])
