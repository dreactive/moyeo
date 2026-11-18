"""Persist source-owned request outcomes without losing completed work."""
from copy import deepcopy

from backend.services.observations import known_place_ids


TERMINAL_REQUESTS = {'completed', 'unsupported', 'cancelled', 'superseded'}
REQUEST_STATUSES = TERMINAL_REQUESTS | {'resolved', 'pending', 'needs_context', 'needs_input', 'failed'}


def persist_requests(room, requests, observations):
    messages = {message['id']: message for message in room['messages']}
    places = known_place_ids(observations)
    places.update('anchor:'+name for name in ('origin','destination','lodging')
                  if isinstance(room['config'].get(name),dict)
                  and all(isinstance(room['config'][name].get(key),(int,float))
                          for key in ('latitude','longitude')))
    existing = {r['request_id']: deepcopy(r) for r in room.get('agent_requests', [])}
    for request in requests:
        source = messages.get(request.get('source_message_id'))
        identity = request.get('request_id')
        refs = request.get('target_refs', []) + request.get('excluded_refs', [])
        previous = existing.get(identity)
        evidence = request.get('evidence')
        if (not isinstance(identity, str) or not identity or not source
                or request.get('owner_id') != source['author_id']
                or request.get('status') not in REQUEST_STATUSES
                or not all(isinstance(ref, str) for ref in refs) or not set(refs) <= places
                or previous and (previous.get('owner_id'), previous.get('source_message_id')) !=
                    (request.get('owner_id'), request.get('source_message_id'))):
            raise ValueError('Invalid scoped request source or targets')
        if evidence is not None and (evidence.get('message_id') != source['id']
                or not isinstance(evidence.get('quote'), str) or not evidence['quote']
                or evidence['quote'] not in source['text']):
            raise ValueError('Invalid scoped request evidence')
        existing[identity] = deepcopy(request)
    room['agent_requests'] = list(existing.values())


def persist_partial_results(room, result):
    partial = result.get('partial_results')
    if partial is None:
        return
    if not isinstance(partial, dict) or not set(partial) <= {'build_itinerary', 'calculate_costs'}:
        raise ValueError('Invalid partial calculation outputs')
    for name, output in partial.items():
        if not any(o.get('tool_name') == name and o.get('result') == output
                   for o in result['observations']):
            raise ValueError('Partial output lacks its selected tool observation')
    room['agent_results'] = dict(run_id=result['run_id'], versions=deepcopy(room['versions']),
                                 **deepcopy(partial))


def active_lookup(room, request_id, owner_id):
    return next((r for r in room.get('agent_requests', []) if r['request_id'] == request_id
                 and r.get('owner_id') == owner_id and r.get('status') not in TERMINAL_REQUESTS), None)
