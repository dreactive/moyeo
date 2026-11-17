import hashlib
import json
from copy import deepcopy
from fastapi import HTTPException


HASH_FIELDS = ('selected_item_ids','item_snapshots','days','cost','evidence','validation','blocking_conflict_ids')
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
    if stance == 'withdraw' and room['active_target'] != target:
        raise HTTPException(409, 'No active confirmation to withdraw')
    freeze_review(room, target)
    room['confirmations'] = [vote for vote in room['confirmations'] if vote['user_id'] != actor_id]
    room['confirmations'].append(dict(user_id=actor_id, target=deepcopy(target), stance=stance, created_at=datetime.now(timezone.utc).isoformat()))


def ready_to_confirm(room, plan):
    if plan['validation'] != 'ready' or plan['blocking_conflict_ids']:
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


def select_conflict_option(room, conflict_id, option_id, actor_id):
    conflict = next((c for c in room['conflicts'] if c['id'] == conflict_id), None)
    if conflict is None or conflict['base_versions'] != room['versions']:
        raise HTTPException(409, 'Conflict inputs changed')
    option = next((o for o in conflict['options'] if o['id'] == option_id), None)
    if option is None:
        raise HTTPException(404, 'Option not found')
    if option.get('requires_owner_id') not in (None, actor_id):
        raise HTTPException(403, 'Owner selection required')
    return deepcopy(dict(conflict_id=conflict_id, option_id=option_id, effect=option['effect'], base_versions=conflict['base_versions']))


def item_snapshots(room, draft):
    items = {item['id']:item for item in room['items']}
    places = {visit['item_id']:visit['place_ref'] for day in draft['days'] for visit in day['visits']}
    snapshots = []
    for item_id in draft['selected_item_ids']:
        item = items[item_id]
        snapshot = {key:deepcopy(item[key]) for key in ('id','item_version','kind','title','source_message_ids')}
        snapshot['place_ref'] = places.get(item_id)
        snapshots.append(snapshot)
    return snapshots

DRAFT_FIELDS = ('selected_item_ids','days','cost','validation','blocking_conflict_ids')


def build_plan(room, draft, evidence):
    plan = {key:deepcopy(draft[key]) for key in DRAFT_FIELDS}
    plan['item_snapshots'] = item_snapshots(room, plan)
    plan['content_hash'] = semantic_plan_hash(dict(plan, evidence=evidence))
    current = room['current_plan']
    unchanged = current and current['content_hash'] == plan['content_hash']
    unchanged = unchanged and all(current[key] == room['versions'][key] for key in ('participant_version','constraint_version','evidence_version'))
    if unchanged:
        return deepcopy(current)
    room['versions']['plan_revision'] += 1
    plan.update(room['versions'])
    plan['confirmation_target'] = dict(room['versions'], content_hash=plan['content_hash'])
    return plan

