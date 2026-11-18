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
