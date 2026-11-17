from copy import deepcopy


def get_observations(db, room_id):
    return deepcopy(db.observations.get(room_id, []))


def project_observations(db, room_id, observations):
    current = get_observations(db, room_id)
    for observation in observations:
        current = [old for old in current if (old['tool_name'],old['arguments']) != (observation['tool_name'],observation['arguments'])]
        current.append(deepcopy(observation))
    db.observations[room_id] = current


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
