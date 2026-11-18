from backend.domain import project_items
from backend.services.observations import get_observations, regional_search_places
from copy import deepcopy
from fastapi import HTTPException
import secrets


EMPTY_ROOM = {
    'seq': 0, 'messages': [], 'items': [], 'constraints': [],
    'versions': {'participant_version': 1, 'constraint_version': 0, 'evidence_version': 0, 'plan_revision': 0},
    'current_plan': None, 'review_plan': None, 'active_target': None,
    'confirmed_plan': None, 'confirmations': [], 'conflicts': [], 'questions': [],
    'agent_status': {'run_id': None, 'state': 'idle', 'label': '대기'},
}


def new_room(user, body):
    room = deepcopy(EMPTY_ROOM)
    room.update(room_id=secrets.token_hex(16), title=body['title'], invite_code=secrets.token_urlsafe(8), config={k: v for k, v in body.items() if k != 'title'}, members=[{'user_id': user['id'], 'name': user['name']}])
    return room


def require_room(db, room_id, viewer_id):
    room = db.get('room:' + room_id)
    if room is None:
        raise HTTPException(404, 'Room not found')
    if viewer_id not in [member['user_id'] for member in room['members']]:
        raise HTTPException(403, 'Room membership required')
    return room



def get_room_snapshot(db, room_id, viewer_id):
    room = project_items(require_room(db, room_id, viewer_id))
    project_item_places(room, get_observations(db, room_id))
    room['messages'] = room['messages'][-50:]
    room['owner_id'] = room_owner_id(room)
    return room


def project_item_places(room, observations):
    region = room['config'].get('region')
    if not region:
        return
    by_name = {}
    def normalize(text):
        return ''.join(text.split()).casefold()
    for place, obs in regional_search_places(room, observations):
        refs = by_name.setdefault(normalize(place['name']), {}).setdefault(place['id'], [])
        proof = [obs.get('observation_id'), obs.get('id'), *obs.get('source_refs', []), place.get('source_ref')]
        refs.extend(source for source in proof if source and source not in refs)
    for item in room['items']:
        matches = by_name.get(normalize(item['title']), {}) if item['kind']=='place' else {}
        if len(matches)==1:
            ref, proof = next(iter(matches.items()))
            item.update(place_ref=ref, place_source_refs=proof or [ref], place_region=region)


def room_owner_id(room):
    """Creator owns the room; rooms made before owner_id existed fall back to the first member."""
    return room.get('owner_id') or (room['members'][0]['user_id'] if room['members'] else None)


def delete_room(db, room_id, actor_id):
    from fastapi import HTTPException
    from backend.services.events import publish_event
    with db.lock:
        room = require_room(db, room_id, actor_id)
        if room_owner_id(room) != actor_id:
            raise HTTPException(403, 'Only the room owner may delete')
        publish_event(db, room_id, 'room.deleted', {'room_id': room_id})
        db.put('events:' + room_id, db.get('events:' + room_id)[-1:])
        runs = [key for key, run in db.scan('run:') if run.get('room_id') == room_id]
        db.delete_many(['room:' + room_id, 'invite:' + room['invite_code'], 'processed-message:' + room_id, 'failed-extraction:' + room_id, 'confirmed-history:' + room_id] + runs)
        db.observations.pop(room_id, None)
        for run_id, trace in list(db.traces.items()):
            if trace['room_id'] == room_id:
                del db.traces[run_id]


def room_summary(room, viewer_id):
    names = {member['user_id']: member['name'] for member in room['members']}
    last = room['messages'][-1] if room['messages'] else None
    plan = room.get('review_plan') or room.get('current_plan')
    target = plan.get('confirmation_target') if plan else None
    basis_current = target and all(room['versions'][key] == target[key] for key in ('participant_version','constraint_version','evidence_version'))
    official = basis_current and (room.get('confirmed_plan') or {}).get('confirmation_target') == target
    stage = 'confirmed' if official else 'draft' if plan else 'empty'
    config = room.get('config', {})
    return {
        'room_id': room['room_id'], 'title': room['title'], 'invite_code': room['invite_code'],
        'owner_id': room_owner_id(room), 'is_owner': room_owner_id(room) == viewer_id,
        'region': config.get('region'), 'start_date': config.get('start_date'), 'end_date': config.get('end_date'),
        'members': [{'user_id': member['user_id'], 'name': member['name']} for member in room['members']],
        'last_message': {'author_name': names.get(last['author_id'], '알 수 없음'), 'text': last['text'][:120], 'created_at': last['created_at'], 'mine': last['author_id'] == viewer_id} if last else None,
        'plan_stage': stage, 'plan_revision': plan['plan_revision'] if plan else None,
        'agent_state': room.get('agent_status', {}).get('state', 'idle'),
        'updated_at': (last or {}).get('created_at') or room.get('created_at'),
    }


def list_rooms(db, viewer_id):
    rooms = [room for key, room in db.scan('room:') if isinstance(room, dict) and any(member['user_id'] == viewer_id for member in room.get('members', []))]
    summaries = [room_summary(room, viewer_id) for room in rooms]
    return sorted(summaries, key=lambda room: room['updated_at'] or '', reverse=True)


def add_member(db, room_id, user):
    """Add a user to the room once; returns True when membership changed."""
    from backend.services.events import publish_event
    with db.lock:
        room = db.get('room:' + room_id)
        if room is None:
            raise HTTPException(404, 'Room not found')
        if user['id'] in [member['user_id'] for member in room['members']]:
            return False
        room['members'].append({'user_id': user['id'], 'name': user['name']})
        room['versions']['participant_version'] += 1
        room.update(active_target=None, review_plan=None, confirmations=[])
        db.put('room:' + room_id, room)
        publish_event(db, room_id, 'room.updated', {'changed': ['members', 'versions', 'confirmations']})
        return True
