from backend.services.planning import substantive
from copy import deepcopy
from datetime import datetime, timezone
from fastapi import HTTPException
import json


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



async def fetch_place(db, port, room, place_ref, location_only=False):
    cached = observed_place(db, room['room_id'], place_ref)
    observations = get_observations(db, room['room_id'])
    if location_only:
        place = next((p for p,_ in regional_search_places(room, reversed(observations))
                      if p['id'] == place_ref), None)
        if place is None:
            # A displayed historical plan may explicitly reference another region's observed ID.
            place = next((p for o in reversed(observations) if o['tool_name']=='search_places'
                          and o.get('room_id') in (None,room['room_id'])
                          and o['result'].get('room_id') in (None,room['room_id'])
                          for p in o['result'].get('places', []) if p['id']==place_ref
                          and p.get('room_id') in (None,room['room_id'])), None)
        if place is None and cached:
            place = cached['place']
        if place is None:
            raise HTTPException(404, 'Place not observed in this room')
        return dict(place=deepcopy(place),menus=[],opening_hours=None,evidence=[],
                    missing_fields=['price','opening_hours'],match_status='matched')
    # A user explicitly opening details may reuse the executor's suitable live
    # cache; route coordinate rendering above never invokes an extra tool.
    if cached is not None and not any(e.get('mode')=='live' for e in cached.get('evidence', [])):
        return cached
    allowed = known_place_ids(observations)
    if place_ref not in allowed:
        raise HTTPException(404, 'Place not observed in this room')
    context = deepcopy(dict(room_id=room['room_id'], config=room['config'], observations=observations))
    result = await port.execute_tool('get_place_details', {'place_ref':place_ref}, context)
    if result['place']['id'] != place_ref:
        raise HTTPException(502, 'Tool returned a different place')
    project_observations(db, room['room_id'], [dict(tool_name='get_place_details', arguments={'place_ref':place_ref}, result=result, observed_at=datetime.now(timezone.utc).isoformat(), source_refs=[e['id'] for e in result['evidence']])])
    return result


def known_place_ids(observations):
    refs = set()
    for observation in observations:
        result = observation['result']
        if observation['tool_name'] == 'search_places':
            refs.update(place['id'] for place in result['places'])
        elif observation['tool_name'] == 'get_place_details':
            refs.add(result['place']['id'])
    return refs


def regional_search_places(room, observations):
    def normalized(text):
        return ''.join((text or '').split()).casefold()
    region = normalized(room['config'].get('region'))
    for obs in observations:
        result = obs.get('result', {})
        if (not region or obs.get('tool_name') != 'search_places'
                or obs.get('room_id') not in (None, room['room_id'])
                or result.get('room_id') not in (None, room['room_id'])
                or normalized(obs.get('arguments', {}).get('region')) != region):
            continue
        for place in result.get('places', []):
            if place.get('room_id') in (None, room['room_id']) and place.get('id') and place.get('name'):
                yield place, obs
