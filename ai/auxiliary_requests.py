"""Ground domain request targets to current evidence and unique room observations."""
import re
from ai.grounding import normalized, source_message


def observed_places(task):
    result, seen = [], set()
    room = task.get('room_id')
    for observation in task.get('observations', []):
        if observation.get('room_id') not in (None, room) or observation.get('tool_name') not in ('search_places', 'get_place_details'):
            continue
        value = observation.get('result', {})
        places = list(value.get('places', [])) + ([value['place']] if isinstance(value.get('place'), dict) else [])
        for place in places:
            ref, name = place.get('id') or place.get('place_ref'), place.get('name')
            if (not isinstance(ref, str) or not ref or not isinstance(name, str) or not name
                    or place.get('room_id') not in (None, room) or (ref, name) in seen):
                continue
            seen.add((ref, name))
            result.append(dict(place_ref=ref, name=name))
    return result


def request_needs_context(request, task):
    message = source_message(request['evidence'], task)
    if not message:
        return False
    names = request.get('target_names', []) + request.get('excluded_names', [])
    return not request.get('target_names') or any(normalized(name) not in normalized(request['evidence']['quote']) for name in names)


def request_context_records(task, requests):
    """For personal selection references, retrieve only that speaker's selection records."""
    names = [p['name'] for p in observed_places(task)]
    eligible = set()
    for request in requests:
        message = source_message(request['evidence'], task)
        if not message or not request_needs_context(request, task):
            continue
        for old in task.get('conversation_context', []):
            if old.get('author_id') != message['author_id']:
                continue
            count = sum(normalized(name) in normalized(old.get('text', '')) for name in names)
            if count and (count >= 2 or re.search(r'말고|하자|가자|선택|고른|골랐|대신|좋아|찬성|제외|빼자', old.get('text', ''))):
                eligible.add(old['id'])
    return eligible


def excluded_name(name, quote):
    return bool(re.search(re.escape(normalized(name)) + r'(?:은|는|이|가|을|를)?(?:말고|빼|제외|반대|싫)', normalized(quote)))


def name_evidence(name, current, evidence, contexts, records, excluded=False):
    """Use the latest cited occurrence and inspect its actual source tail beyond a cropped quote."""
    target = normalized(name)
    candidates = []
    ordering = {message_id: index for index, message_id in enumerate(records)}
    for fact in contexts:
        quote = normalized(fact['quote'])
        if target in quote:
            full = normalized(records[fact['message_id']]['text'])
            offset = full.rfind(quote) + quote.rfind(target)
            candidates.append((ordering[fact['message_id']], offset, full[offset:]))
    quote = normalized(evidence['quote'])
    if target in quote:
        full = normalized(current['text'])
        offset = full.rfind(quote) + quote.rfind(target)
        candidates.append((len(records), offset, full[offset:]))
    if not candidates:
        return False
    tail = max(candidates, key=lambda row: (row[0], row[1]))[2]
    return excluded_name(name, tail) is excluded


def _expected_count(quote):
    match = re.search(r'([한두세네]|[1-9])\s*곳', quote)
    return {'한': 1, '두': 2, '세': 3, '네': 4}.get(match[1], int(match[1]) if match[1].isdigit() else None) if match else None


def ground_requests(raw, task, supplied_context, reject):
    known = {}
    for place in observed_places(task):
        known.setdefault(normalized(place['name']), set()).add(place['place_ref'])
    requests, failed_source = [], False
    for request in raw:
        current = source_message(request['evidence'], task)
        if not current:
            reject(request['evidence'])
            failed_source = True
            continue
        prior = []
        for message in task.get('recent_messages', []):
            if message['id'] == current['id']:
                break
            prior.append(message)
        records = {m['id']: m for m in list(supplied_context) + prior}
        contexts, bad_context = [], False
        for evidence in request.get('context_evidence', []):
            record = records.get(evidence['message_id'])
            if (not record or record.get('author_id') != current['author_id'] or not evidence['quote']
                    or evidence['quote'] not in record.get('text', '')):
                bad_context = True
                continue
            fact = dict(evidence, author_id=record['author_id'])
            if fact not in contexts:
                contexts.append(fact)
        names = list(dict.fromkeys(request.get('target_names', [])))
        excluded = list(dict.fromkeys(request.get('excluded_names', [])))
        count = _expected_count(request['evidence']['quote'])
        valid = bool(names) and not bad_context and (count is None or count == len(names))
        valid &= not set(normalized(n) for n in names) & set(normalized(n) for n in excluded)
        target_refs, excluded_refs = [], []
        for name in names:
            refs = known.get(normalized(name), set())
            evidence = name_evidence(name, current, request['evidence'], contexts, records)
            if len(refs) != 1 or not evidence:
                valid = False
            else:
                target_refs.append(next(iter(refs)))
        for name in excluded:
            refs = known.get(normalized(name), set())
            if len(refs) != 1 or not name_evidence(name, current, request['evidence'], contexts, records, excluded=True):
                valid = False
            else:
                excluded_refs.append(next(iter(refs)))
        if len(target_refs) != len(set(target_refs)) or set(target_refs) & set(excluded_refs):
            valid = False
        status = 'resolved' if valid else 'needs_input' if supplied_context or bad_context or not request_needs_context(request, task) else 'needs_context'
        requests.append(dict(request_id='request:' + current['id'] + ':' + request['intent'], intent=request['intent'],
            owner_id=current['author_id'], source_message_id=current['id'], evidence=dict(request['evidence']),
            target_names=names, excluded_names=excluded, target_refs=target_refs if valid else [],
            excluded_refs=excluded_refs if valid else [], context_evidence=contexts, status=status))
    return requests, failed_source
