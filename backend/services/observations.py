from copy import deepcopy


def get_observations(db, room_id):
    return deepcopy(db.observations.get(room_id, []))


def project_observations(db, room_id, observations):
    db.observations[room_id] = merge_observations(get_observations(db, room_id), observations)


def merge_observations(current, observations):
    current = deepcopy(current)
    for observation in observations:
        current = [old for old in current if (old['tool_name'],old['arguments']) != (observation['tool_name'],observation['arguments'])]
        current.append(deepcopy(observation))
    return current


def observed_place(db, room_id, place_ref):
    for observation in reversed(get_observations(db, room_id)):
        if observation['tool_name'] == 'get_place_details' and observation['result']['place']['id'] == place_ref:
            return observation['result']
    return None

import json
from backend.services.planning import substantive


def relevant_evidence(plan, observations):
    if plan is None:
        return []
    places = {visit['place_ref'] for day in plan['days'] for visit in day['visits']}
    routes = {leg['evidence_id'] for day in plan['days'] for leg in day['route_legs']}
    results = []
    for observation in observations:
        result = observation['result']
        if result.get('place', {}).get('id') in places or result.get('evidence_id') in routes:
            results.append(substantive(result))
    return sorted(results, key=lambda value:json.dumps(value, sort_keys=True))

from datetime import datetime, timezone
from fastapi import HTTPException


async def fetch_place(db, port, room, place_ref):
    cached = observed_place(db, room['room_id'], place_ref)
    if cached is not None:
        return cached
    observations = get_observations(db, room['room_id'])
    allowed = {place['id'] for observation in observations if observation['tool_name'] == 'search_places' for place in observation['result']['places']}
    if place_ref not in allowed:
        raise HTTPException(404, 'Place not observed in this room')
    context = deepcopy(dict(room_id=room['room_id'], config=room['config'], observations=observations))
    result = await port.execute_tool('get_place_details', {'place_ref':place_ref}, context)
    if result['place']['id'] != place_ref:
        raise HTTPException(502, 'Tool returned a different place')
    project_observations(db, room['room_id'], [dict(tool_name='get_place_details', arguments={'place_ref':place_ref}, result=result, observed_at=datetime.now(timezone.utc).isoformat(), source_refs=[e['id'] for e in result['evidence']])])
    return result
