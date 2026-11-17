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
