"""Ground domain request targets to current evidence and unique room observations."""
import hashlib
import re
from datetime import datetime
from ai.grounding import normalized, source_message
from ai.providers.live import detail_matches_place


LOOKUP_INTENTS = ('place_lookup', 'place_details')
ROUTE_INTENT = 'route_lookup'
CALCULATION_TOOLS = {'cost_estimate': 'calculate_costs', 'itinerary_plan': 'build_itinerary'}
CALCULATION_CUES = {
    'cost_estimate': re.compile(r'(?:여행\s*)?(?:비용|경비|예산|총액|합계)[^.!?;\n]{0,20}?(?:계산|합산|산출|견적)'),
    'itinerary_plan': re.compile(r'(?:일정|여행\s*계획)[^.!?;\n]{0,20}?(?:짜\s*줘|짜\s*주|작성|만들|세워|계획해|계산|편성|보여\s*(?:줘|주))'),
}
REQUEST_INTENTS = (*LOOKUP_INTENTS, ROUTE_INTENT, *CALCULATION_TOOLS, 'service_request')
FIELD_CUES = {
    'location': r'찾아|검색|위치|주소|어디',
    'details': r'상세|세부|정보|메뉴|시설',
    'price': r'가격|요금|금액|입장료|얼마|비용',
    'opening_hours': r'(?:영업|운영|개장|폐장|오픈|마감)\s*(?:시각|시간)?|몇\s*시에?\s*(?:열|닫)|휴무',
}
LOOKUP_CUE = re.compile('|'.join(FIELD_CUES.values()))
HISTORY_CUE = re.compile(r'아까|이전|지난번|말했|말한|고른|골랐|선택했던|선택한|거기|그\s*(?:곳|장소)')
SELECTION_CUE = re.compile(r'말고|하자|가자|선택|고른|골랐|대신|좋아|찬성|제외|빼자')
CANCEL_CUE = re.compile(r'취소|철회|그만|중단|(?:하|주|찾)지\s*마|안\s*해도\s*(?:돼|되)')
NON_CURRENT = re.compile(r'만약|라면|라고|했대|말했|["“”‘’`]')
EXCLUSION_CUE = re.compile(r'말고|제외하고|빼고')
ROUTE_CUE = re.compile(r'경로|길찾기|이동\s*시간|소요\s*시간|가는\s*(?:길|방법)')
ROUTE_CURRENT = re.compile(r'지금|현재|바로\s*출발')
NON_CAR = re.compile(r'(?:기차|열차|버스|지하철|대중교통|도보|자전거|비행기|항공)'
                     r'(?:로|으로|를\s*타|\s*타고|\s+(?:이동|경로|길찾기|길|가는)|\s*$)')
ANCHOR_NAMES = {'출발지': 'anchor:origin', '도착지': 'anchor:destination',
                '목적지': 'anchor:destination', '숙소': 'anchor:lodging'}


def place_observation_in_scope(task, observation, explicit_refs=()):
    room = task.get('room_id')
    result = observation.get('result', {})
    if observation.get('room_id') not in (None, room) or result.get('room_id') not in (None, room):
        return False
    if observation.get('tool_name') == 'get_place_details':
        place = result.get('place') or {}
        ref = place.get('id')
        if not ref or ref != observation.get('arguments', {}).get('place_ref') or place.get('room_id') not in (None, room):
            return False
        searches = [o for o in task.get('observations', []) if o.get('tool_name') == 'search_places'
                    and any(p.get('id') == ref and p.get('room_id') in (None, room)
                            for p in o.get('result', {}).get('places', []))]
        return any(place_observation_in_scope(task, o) and any(
            p.get('id') == ref and detail_matches_place(result, p) for p in o['result']['places'])
            for o in searches) or (not searches and ref in explicit_refs)
    if observation.get('tool_name') != 'search_places':
        return False
    observed_region = observation.get('arguments', {}).get('region')
    current_region = task.get('config', {}).get('region')
    return bool(observed_region and current_region and normalized(observed_region) == normalized(current_region))


def observed_places(task, explicit_refs=()):
    result, seen = [], set()
    room = task.get('room_id')
    for observation in task.get('observations', []):
        if not place_observation_in_scope(task, observation, explicit_refs):
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
    if not message or request['intent'] not in LOOKUP_INTENTS or request.get('operation') == 'cancel':
        return False
    names = request.get('target_names', []) + request.get('excluded_names', [])
    indirect = not request.get('target_names') or any(normalized(name) not in normalized(request['evidence']['quote']) for name in names)
    return indirect and bool(HISTORY_CUE.search(message['text']))


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
            text = old.get('text', '')
            count = sum(normalized(name) in normalized(text) for name in names)
            if count >= 2 or SELECTION_CUE.search(text) and not NON_CURRENT.search(text):
                eligible.add(old['id'])
    return eligible


def excluded_name(name, quote):
    return bool(re.search(re.escape(normalized(name)) + r'(?:은|는|이|가|을|를)?'
                          r'(?:(?:검색|조회|추천|선택)하지)?(?:말고|빼|제외|반대|싫)', normalized(quote)))


def name_evidence(name, current, evidence, contexts, records, excluded=False):
    """Require a citation and check later in-scope records for corrections."""
    target = normalized(name)
    candidates = []
    ordering = {message_id: index for index, message_id in enumerate(records)}
    historical = [fact for fact in contexts if target in normalized(fact['quote'])]
    if historical:
        earliest = min(ordering[fact['message_id']] for fact in historical)
        for index, record in enumerate(records.values()):
            if (index < earliest or record.get('author_id') != current['author_id']
                    or index > earliest and not SELECTION_CUE.search(record['text'])):
                continue
            full = normalized(record['text'])
            offset = full.rfind(target)
            if offset >= 0:
                candidates.append((index, offset, full[offset:]))
    quote = normalized(evidence['quote'])
    full = normalized(current['text'])
    if target in quote or historical and target in full:
        offset = full.rfind(target)
        candidates.append((len(records), offset, full[offset:]))
    if not candidates:
        return False
    tail = max(candidates, key=lambda row: (row[0], row[1]))[2]
    return excluded_name(name, tail) is excluded


def _expected_count(quote):
    match = re.search(r'([한두세네]|[1-9])\s*곳', quote)
    return {'한': 1, '두': 2, '세': 3, '네': 4}.get(match[1], int(match[1]) if match[1].isdigit() else None) if match else None


def source_clauses(text, quote):
    """Return full punctuation-delimited clauses intersecting a verbatim quote."""
    starts = [match.start() for match in re.finditer(re.escape(quote), text)]
    matches = re.finditer(r'[^.!?;\n]+?(?=[.!?;\n]|$|(?<=주고)\s|(?<=주시고)\s)', text)
    return [match.group() for match in matches
            if any(start < match.end() and start + len(quote) > match.start() for start in starts)]


def positive_lookup_clauses(text, quote):
    for clause in source_clauses(text, quote):
        if re.search(r'만약|라면|라고|했대|말했(?:대|어(?:요)?$)|["“”‘’`]', clause):
            continue
        positive = EXCLUSION_CUE.split(clause)[-1]
        if not CANCEL_CUE.search(positive):
            yield positive


def calculation_requested(intent, text, quote):
    cue = CALCULATION_CUES[intent]
    directive = re.compile(r'해\s*(?:줘|주|봐|줄|보자|볼까)|하자|하세요|해요|부탁|알려|(?:짜|만들어|세워|보여)\s*(?:줘|주|줄|봐)')
    if not cue.search(quote):
        return False
    other_topic = r'일정|여행\s*계획' if intent=='cost_estimate' else r'비용|경비|예산|총액|합계'
    for part in positive_lookup_clauses(text, quote):
        for scope in re.split(other_topic, part):
            match = cue.search(scope)
            if not match:
                continue
            scope = scope[match.start():]
            if re.search(r'끝났|마쳤|완료했|계산했|(?:계산|합산|산출|작성|편성|계획|만들|짜)'
                    r'[^.!?;\n]{0,8}(?:말|않|필요\s*없)|(?:안|못)\s*(?:계산|짜|만들)', scope):
                continue
            if directive.search(scope):
                return True
            # A serial imperative can share its ending, as in "비용 계산하고 일정도 보여줘".
            if (intent=='cost_estimate' and re.search(r'(?:계산|합산|산출)하고\s*(?:가능한\s*)?$', scope)
                    and re.search(r'(?:일정|여행\s*계획)(?:도|을|를)?\s*(?:보여|짜|만들어|세워)\s*(?:줘|주|줄)', part)):
                return True
    return False


def explicit_calculations(task, requests):
    members = {m['user_id'] for m in task['members']}
    for message in task['recent_messages']:
        if message.get('author_id') not in members:
            continue
        for clause in source_clauses(message['text'], message['text']):
            quote = clause.strip()
            for intent in CALCULATION_TOOLS:
                if calculation_requested(intent, message['text'], quote) and not any(
                        r['intent'] == intent and r['evidence']['message_id'] == message['id']
                        and calculation_requested(intent, message['text'], r['evidence']['quote']) for r in requests):
                    yield dict(intent=intent, evidence=dict(message_id=message['id'], quote=quote))


def lookup_fields(request, text):
    """Verify the lookup direction against full clauses, even when the quote is clipped."""
    quote = request['evidence']['quote']
    if request.get('operation') == 'cancel':
        return [] if any(cancel_requested(clause) for clause in source_clauses(text, quote)) else None
    positive = list(positive_lookup_clauses(text, quote))
    if not LOOKUP_CUE.search(quote) or not any(LOOKUP_CUE.search(part) for part in positive):
        return None
    fields = request.get('requested_fields') or ['details' if request['intent'] == 'place_details' else 'location']
    if not isinstance(fields, list) or any(field not in FIELD_CUES for field in fields):
        return None
    return list(dict.fromkeys(fields)) if all(
        any(re.search(FIELD_CUES[field], part) for part in positive) for field in fields) else None


def lookup_target_evidence(name, current, evidence, contexts, records, fields=()):
    """Bind an explicit name to the lookup clause, or a personal reference to selection history."""
    if not name_evidence(name, current, evidence, contexts, records):
        return False
    target = normalized(name)
    positive = [part for part in positive_lookup_clauses(current['text'], evidence['quote']) if LOOKUP_CUE.search(part)]
    for part in positive:
        if not whole_lookup_name(name, part):
            continue
        if fields:
            scopes = named_lookup_fields(part.strip())
            if scopes and name in scopes and not set(fields) <= set(scopes[name]):
                continue
            if len(scopes)>1 and name not in scopes:
                continue
        return True
    return (any(HISTORY_CUE.search(part) for part in positive)
            and any(target in normalized(fact['quote']) for fact in contexts))


def route_evidence(request, text):
    """Read explicit route direction and timing without inventing a departure."""
    clauses = []
    for clause in source_clauses(text, request['evidence']['quote']):
        positive = list(positive_lookup_clauses(clause, clause))
        if not positive or not ROUTE_CUE.search(positive[0]) or NON_CAR.search(positive[0]):
            continue
        segments = EXCLUSION_CUE.split(clause)
        # A common directional prefix still applies when the exclusion changes only the transport mode.
        shared_direction = len(segments) == 2 and NON_CAR.search(segments[0]) and not re.search(
            r'(?:에서|부터).*(?:까지|으로|로)', segments[1])
        clauses.append(clause if shared_direction else positive[0])
    if not clauses:
        return None
    names = request.get('target_names', [])
    direction = []
    quote = normalized(request['evidence']['quote'])
    if len(names) == 2 and len(set(map(normalized, names))) == 2:
        start, end = [re.escape(normalized(name)) for name in names]
        directed = re.compile(start + r'(?:에서|부터).*?' + end + r'(?:까지|으로|로)')
        direction = [clause for clause in clauses if directed.search(normalized(clause))
                     and all(normalized(name) in quote for name in names)]
    if any(ROUTE_CURRENT.search(clause) for clause in direction):
        return bool(direction), 'current', None
    departure = request.get('departure_at')
    if direction and isinstance(departure, str) and departure in request['evidence']['quote']:
        try:
            parsed = datetime.fromisoformat(departure)
        except ValueError:
            parsed = None
        if parsed is not None and parsed.utcoffset() is not None and any(departure in clause for clause in direction):
            return True, 'scheduled', departure
    return bool(direction), 'needs_input', None


def cancel_requested(clause):
    return bool(CANCEL_CUE.search(clause) and not re.search(
        r'만약|라면|라고|했대|["“”‘’`]|(?:취소|철회|중단)(?:하)?지\s*(?:말|않)|취소\s*말고|중단\s*말고|취소(?:가|는)?\s*아니', clause))


def cancellable_requests(task, owner, source_id):
    scopes = task.get('_cancel_scopes', task.get('pending_requests', []))
    order = task.get('_request_source_order') or {m['id']: i for i,m in enumerate(task.get('recent_messages', []))}
    control = next((r for r in scopes if r.get('source_message_id')==source_id
                    and r.get('owner_id')==owner and r.get('operation')=='cancel'), {})
    eligible = control.get('prior_request_ids')
    return [request for request in scopes
            if request.get('owner_id') == owner and request.get('source_message_id') != source_id
            and (eligible is None or request['request_id'] in eligible)
            and (request.get('source_message_id') not in order or
                 source_id in order and order[request['source_message_id']] < order[source_id])
            and request.get('operation', 'request') == 'request'
            and request.get('status') not in ('completed', 'cancelled', 'superseded', 'unsupported')]


def bind_batch_cancellations(task, requests):
    # Request IDs are stable only after compound requests have been disambiguated.
    scopes = {r['request_id']: r for r in [*task.get('pending_requests', []), *requests]}
    context = dict(task, _cancel_scopes=list(scopes.values()))
    for control in requests:
        if control.get('operation') != 'cancel':
            continue
        owner, source = control['owner_id'], control['source_message_id']
        control['prior_request_ids'] = [r['request_id'] for r in cancellable_requests(context, owner, source)]
        if control.pop('_valid_control', False):
            matches = cancellation_matches(context, owner, control['target_names'], source)
            control.update(cancelled_request_ids=matches, status='resolved' if matches else 'needs_input')


def cancellation_options(task, owner, names, source_id):
    targets = {normalized(name) for name in names}
    active = cancellable_requests(task, owner, source_id)
    return [request['request_id'] for request in active if not targets or targets == {
        normalized(name) for name in request.get('target_names', [])}]


def cancellation_matches(task, owner, names, source_id):
    """A named cancellation must name the whole request; generic ones need a unique request."""
    options = cancellation_options(task, owner, names, source_id)
    return options if len(options) == 1 else []


def explicit_cancellations(task, requests):
    """Keep a standalone cancellation when the auxiliary omits it."""
    classified = {r['evidence']['message_id'] for r in requests if r.get('operation') == 'cancel'}
    members = {m['user_id'] for m in task['members']}
    action = r'(?:취소|철회|중단)(?:해\s*줘(?:요)?|해\s*주세요|할게|해|요)?'
    generic = re.compile(r'(?:(?:아니|아까|방금)\s*)*(?:(?:내|그)\s*)?'
                         r'(?:(?:거|건|요청|조회|검색)(?:을|를|은|는)?\s*)?' + action)
    named = re.compile(r'(.+?)\s+(?:(?:위치|상세|영업시간|가격)\s*)?(?:검색|조회)(?:을|를|은|는)?\s*' + action)
    stop_lookup = re.compile(r'(.+?)\s+(?:찾아주|찾|검색하|조회하)지\s*마(?:세요)?')
    for message in task.get('recent_messages', []):
        if message['id'] in classified or message['author_id'] not in members:
            continue
        for clause in re.split(r'[.!?;\n]', message['text']):
            quote = clause.strip()
            if not cancel_requested(quote):
                continue
            names = []
            if not generic.fullmatch(quote):
                scope = named.fullmatch(quote) or stop_lookup.fullmatch(quote)
                if not scope:
                    continue
                names = [re.sub(r'(?:을|를|은|는)$', '', part.strip())
                         for part in re.split(r'(?:하고|이랑|랑|와|과|,)\s+', scope[1])]
                if not all(_plausible_name(name, task) and whole_lookup_name(name, quote) for name in names):
                    continue
            yield dict(intent='place_lookup', operation='cancel', target_names=names,
                       evidence=dict(message_id=message['id'], quote=quote))


def _plausible_name(name, task):
    key = normalized(name)
    return bool(key and key not in {'여행', '식당', '카페', '공원', '장소', '상세정보', normalized(task.get('config', {}).get('region') or '')}
                and not re.search(r'[.!?;\n]|찾아|검색|알려|보여|말고|대신|취소|해줘|어디|가자', name))


def _distinct_names(names):
    distinct = {}
    for name in names:
        distinct.setdefault(normalized(name), name)
    return list(distinct.values())


def whole_lookup_name(name, text):
    return bool(re.search(r'(?:(?<!\w)|(?<=하고)|(?<=이랑)|(?<=랑)|(?<=와)|(?<=과))'
        + re.escape(name) + r'(?=(?:하고|이랑|랑|과|와|은|는|을|를|의|도|이|가|에서|에|으로|로)?(?:\s|$|[,.!?;]))', text))


LOOKUP_DIRECTIVE = re.compile(r'(?:찾아|검색해|조회해|알려|보여)\s*(?:줘(?:요)?|주(?:세요|시고|고)|줄래(?:요)?)$')
LOOKUP_ATTRIBUTE = re.compile(r'(?:(?P<name>.+?)(?:의)?\s+)?(?P<label>위치|주소|입장료|가격|요금|'
                              r'영업\s*시간|운영\s*시간|상세\s*정보|상세|정보|메뉴)(?:을|를|도)?$')


def named_lookup_fields(clause):
    """Recognize a coordinated list of noun phrases with explicit, locally attached fields."""
    directive = LOOKUP_DIRECTIVE.search(clause)
    if not directive or HISTORY_CUE.search(clause) or EXCLUSION_CUE.search(clause):
        return {}
    phrases = re.split(r'(?:하고|이랑|랑|와|과|,)\s+', clause[:directive.start()].strip())
    result, names, fields = {}, [], []
    for phrase in phrases:
        attribute = LOOKUP_ATTRIBUTE.fullmatch(phrase)
        name = attribute['name'] if attribute else re.sub(r'(?:을|를)$', '', phrase)
        if name:
            name = re.sub(r'\s+(?:한|두|세|네|[1-9])\s*곳$', '', name)
            if not re.fullmatch(r'[\w-]+(?:\s+[\w-]+)*', name):
                return {}
            if fields:
                result.update((n, list(fields)) for n in names)
                names, fields = [], []
            names.append(name)
        if attribute:
            if not names:
                return {}
            label = attribute['label']
            field = next((f for f,cue in FIELD_CUES.items() if re.fullmatch(cue,label)), None)
            if not field:
                field = 'details' if re.fullmatch(r'상세\s*정보',label) else None
            if not field:
                return {}
            fields.append(field)
    if not fields and not re.match(r'찾아|검색해|조회해', directive[0]):
        return {}
    result.update((n, fields or ['location']) for n in names)
    return result


def explicit_lookup_clauses(message):
    """Identify complete, current lookup directives eligible for source-only recovery."""
    text = message['text']
    if re.search(r'["“”‘’`]|만약|라면|가정하면|라고\s*(?:말|했)|달라고', text):
        return []
    clauses = []
    for clause in source_clauses(text, text):
        clause = clause.strip()
        directive = LOOKUP_DIRECTIVE.search(clause)
        if (not directive or not clause[:directive.start()].strip() or not LOOKUP_CUE.search(clause)
                or CANCEL_CUE.search(clause) or ROUTE_CUE.search(clause)
                or any(cue.search(clause) for cue in CALCULATION_CUES.values())
                or not list(positive_lookup_clauses(text, clause))):
            continue
        clauses.append(clause)
    return clauses


def align_lookup(request, message, clauses):
    """Use an actual source span only when it independently grounds the requested targets and fields."""
    if (request['intent'] not in LOOKUP_INTENTS or request.get('operation','request') != 'request'
            or request.get('context_evidence') or not request.get('target_names')):
        return request
    quote = request['evidence']['quote']
    cited = {clause.strip() for clause in source_clauses(message['text'],quote)} if quote in message['text'] else None
    matches = []
    for clause in clauses:
        if cited is not None and clause not in cited:
            continue
        evidence = dict(message_id=message['id'], quote=clause)
        if any(not whole_lookup_name(name,clause) for name in request['target_names'] + request.get('excluded_names', [])):
            continue
        if not all(lookup_target_evidence(n, message, evidence, [], {}) for n in request['target_names']):
            continue
        if not all(name_evidence(n, message, evidence, [], {}, excluded=True) for n in request.get('excluded_names', [])):
            continue
        positive = list(positive_lookup_clauses(message['text'], clause))
        supported = [field for field,cue in FIELD_CUES.items() if any(re.search(cue,s) for s in positive)]
        requested = request.get('requested_fields') or ['details' if request['intent']=='place_details' else 'location']
        scopes = named_lookup_fields(clause)
        local_fields = scopes and all(n in scopes for n in request['target_names'])
        if local_fields:
            supported = [f for f in FIELD_CUES if all(f in scopes[n] for n in request['target_names'])]
        elif len(scopes)>1:
            matches.append(dict(request, evidence=evidence, target_names=[], requested_fields=requested))
            continue
        elif cited is None:
            continue
        fields = [f for f in requested if f in supported]
        if not fields and local_fields:
            fields = supported
        if fields:
            if cited is not None and fields==requested and lookup_fields(request, message['text']) is not None:
                return request
            matches.append(dict(request, evidence=evidence, requested_fields=fields))
        elif scopes:
            # The source requests these fields, but attaches them to a different noun phrase.
            matches.append(dict(request, evidence=evidence, target_names=[], requested_fields=requested))
    return matches[0] if len(matches)==1 else request


def ground_requests(raw, task, supplied_context, reject, repairs):
    known = {}
    for place in observed_places(task):
        known.setdefault(normalized(place['name']), set()).add(place['place_ref'])
    requests, failed_source = [], False
    members = {m['user_id'] for m in task['members']}
    sources = {m['id']:m for m in task['recent_messages'] if m.get('author_id') in members
               and m.get('room_id') in (None,task.get('room_id'))}
    clauses = {mid:explicit_lookup_clauses(m) for mid,m in sources.items()}
    proposed = []
    for request in raw:
        mid = request['evidence']['message_id']
        aligned = align_lookup(request, sources[mid], clauses[mid]) if mid in sources else request
        if aligned != request:
            repairs.append('lookup_aligned_to_source')
        proposed.append(aligned)
    calculations = list(explicit_calculations(task, raw))
    if calculations:
        repairs.append('calculation_completed_from_source')
    for request in proposed + list(explicit_cancellations(task, raw)) + calculations:
        current = source_message(request['evidence'], task)
        if not current or current.get('room_id') not in (None, task.get('room_id')):
            reject(request['evidence'])
            failed_source = True
            continue
        quote = request['evidence']['quote']
        operation = request.get('operation', 'request')
        intent = request['intent']
        if intent in CALCULATION_TOOLS and operation == 'request':
            if not calculation_requested(intent, current['text'], quote):
                reject(request['evidence'])
                continue
            requests.append(dict(request_id='request:'+current['id']+':'+intent, intent=intent,
                owner_id=current['author_id'], source_message_id=current['id'], evidence=dict(request['evidence']),
                target_names=[], excluded_names=[], target_refs=[], excluded_refs=[], context_evidence=[],
                requested_fields=[], operation=operation, status='resolved'))
            continue
        if intent == 'service_request' and operation != 'cancel':
            # Service actions are generated from the validated current unsupported clauses.
            continue
        route = route_evidence(request, current['text']) if intent == ROUTE_INTENT and operation != 'cancel' else None
        fields = ([] if route else None) if intent == ROUTE_INTENT and operation != 'cancel' else lookup_fields(request, current['text'])
        if fields is None:
            reject(request['evidence'])
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
                    or record.get('room_id') not in (None, task.get('room_id'))
                    or evidence['quote'] not in record.get('text', '')):
                bad_context = True
                continue
            fact = dict(evidence, author_id=record['author_id'])
            if fact not in contexts:
                contexts.append(fact)
        names = _distinct_names(request.get('target_names', []))
        excluded = _distinct_names(request.get('excluded_names', []))
        count = _expected_count(quote)
        valid = not bad_context and (count is None or count == len(names))
        valid = valid and not set(map(normalized, names)) & set(map(normalized, excluded))
        name_validator = name_evidence if operation == 'cancel' else lookup_target_evidence
        valid = valid and all(_plausible_name(name, task) and (
            route[0] if route else name_validator(name, current, request['evidence'], contexts, records)) for name in names)
        valid = valid and all(_plausible_name(name, task) and name_evidence(
            name, current, request['evidence'], contexts, records, excluded=True) for name in excluded)
        target_refs, excluded_refs = [], []
        unresolved = []
        if valid:
            for name in names:
                anchor = ANCHOR_NAMES.get(normalized(name)) if route else None
                refs = ({anchor} if anchor and task.get('config', {}).get(anchor.split(':')[1])
                        else known.get(normalized(name), set()))
                if len(refs) == 1:
                    target_refs.append(next(iter(refs)))
                else:
                    unresolved.append(name)
            excluded_refs = [ref for name in excluded for ref in sorted(known.get(normalized(name), ()))]
            valid = len(target_refs) == len(set(target_refs)) and not set(target_refs) & set(excluded_refs)
        cancel_ids = cancellation_matches(task, current['author_id'], names, current['id']) if valid and operation == 'cancel' else []
        if operation == 'cancel':
            status = 'resolved' if cancel_ids else 'needs_input'
        elif valid and names:
            status = 'pending' if unresolved else 'resolved'
        elif not supplied_context and not bad_context and request_needs_context(request, task):
            status = 'needs_context'
        else:
            status = 'needs_input'
        value = dict(request_id='request:' + current['id'] + ':' + intent, intent=intent,
            owner_id=current['author_id'], source_message_id=current['id'], evidence=dict(request['evidence']),
            target_names=names if valid else [], excluded_names=excluded if valid else [],
            target_refs=target_refs if valid else [], excluded_refs=excluded_refs if valid else [],
            unresolved_target_names=unresolved if valid else [], context_evidence=contexts,
            requested_fields=fields, operation=operation, cancelled_request_ids=cancel_ids, status=status)
        if route:
            value.update(route_timing=route[1], departure_at=route[2])
        if operation == 'cancel':
            value['_valid_control'] = valid
        requests.append(value)
    for mid, directives in clauses.items():
        for clause in directives:
            covered = [r for r in requests if r['source_message_id']==mid and r['intent'] in LOOKUP_INTENTS
                       and r['operation']=='request' and (r['evidence']['quote'] in clause or clause in r['evidence']['quote'])]
            if covered:
                scopes = named_lookup_fields(clause)
                names = {n for r in covered for n in r['target_names']}
                if (not names or not names <= scopes.keys() or not all(
                        whole_lookup_name(n, clause) and _plausible_name(n, task) for n in scopes)):
                    continue
                for missing, source_fields in scopes.items():
                    already = {f for r in covered if missing in r['target_names'] for f in r['requested_fields']}
                    missing_fields = [f for f in source_fields if f not in already]
                    if not missing_fields:
                        continue
                    refs = known.get(normalized(missing), set())
                    requests.append(dict(request_id='request:'+mid+':place_lookup', intent='place_lookup',
                        owner_id=sources[mid]['author_id'], source_message_id=mid, evidence=dict(message_id=mid,quote=clause),
                        target_names=[missing], excluded_names=[], target_refs=list(refs) if len(refs)==1 else [],
                        excluded_refs=[], unresolved_target_names=[] if len(refs)==1 else [missing],
                        context_evidence=[], requested_fields=missing_fields, operation='request',
                        status='resolved' if len(refs)==1 else 'pending'))
                    repairs.append('lookup_target_completed_from_source')
                continue
            fields = [field for field,cue in FIELD_CUES.items() if re.search(cue,clause)]
            requests.append(dict(request_id='request:'+mid+':place_lookup', intent='place_lookup',
                owner_id=sources[mid]['author_id'], source_message_id=mid, evidence=dict(message_id=mid,quote=clause),
                target_names=[], excluded_names=[], target_refs=[], excluded_refs=[], unresolved_target_names=[],
                context_evidence=[], requested_fields=fields, operation='request', status='needs_input'))
            repairs.append('lookup_target_needs_input')
    return requests, failed_source


def assign_request_ids(requests):
    """Keep the legacy key for one request and avoid collisions within compound messages."""
    requests = [request for index, request in enumerate(requests) if request not in requests[:index]]
    bases = [request['request_id'] for request in requests]
    for request, base in zip(requests, bases):
        if bases.count(base) == 1:
            continue
        normalized_targets = list(map(normalized, request['target_names']))
        meaning = (request['operation'], request['evidence']['quote'],
                   normalized_targets if request['intent'] == ROUTE_INTENT else sorted(normalized_targets),
                   sorted(map(normalized, request['excluded_names'])), sorted(request['requested_fields']),
                   request.get('unsupported_code'), request.get('departure_at'))
        digest = hashlib.sha256(repr(meaning).encode('utf-8')).hexdigest()[:12]
        request['request_id'] = base + ':' + digest
    return requests
