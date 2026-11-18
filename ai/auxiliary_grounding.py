"""Project structured facts through current-source, owner, target and value checks."""
import hashlib
import re
from ai.condition_grounding import condition_value
from ai.auxiliary_requests import (EXCLUSION_CUE, LOOKUP_INTENTS, ROUTE_INTENT, assign_request_ids, bind_batch_cancellations, cancel_requested, explicit_lookup_clauses,
                                  ground_requests, source_clauses)
from ai.grounding import normalized, project_item, source_message

GENERIC = {'점심', '저녁', '아침', '밥', '식사', '식당', '카페', '공원', '역', '여행'}
ACTION = re.compile(r'가자|말고|대신|찾아줘|검색해|좋아|찬성|반대|싫어|빼자|철회|먹자|어때')
STANCE = dict(support=r'가자|가보자|좋아|좋지|찬성|동의|가고\s*싶|가요|^(?:응|네|예)[.!\s]*$',
              oppose=r'말고|빼|제외|반대|싫어|안\s*가|가지\s*말|별로', withdraw=r'철회|취소|거둘|없던')


def title_in(text, item):
    title = normalized(item['title'])
    alias = normalized(item['title'].split()[-1])
    return bool(title and (title in normalized(text) or alias not in GENERIC and alias in normalized(text)))


def short_budget_value(key, text, owner, task):
    if key not in ('budget', 'budget_krw'):
        return None
    old = any(c.get('owner_id') == owner and c.get('key') in ('budget', 'budget_krw')
              and c.get('status') != 'superseded' for c in task.get('constraints', []))
    question = any(q.get('owner_id') == owner and q.get('field') in ('budget', 'budget_krw', 'constraint_value')
                   and q.get('status') == 'open' and ('예산' in q.get('text', '') or any(
                       c.get('id') == q.get('target_ref') and c.get('key') in ('budget', 'budget_krw')
                       and c.get('owner_id') == owner for c in task.get('constraints', []))) for q in task.get('questions', []))
    match = re.fullmatch(r'아니\s+(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(만원|만\s*원|원)[.!\s]*', text)
    return condition_value(key, '내 예산은 ' + match[1] + match[2]) if match and (old or question) else None


def ground_conditions(raw, task, reject):
    result = []
    for proposal in raw:
        evidence = proposal['evidence']
        message = source_message(evidence, task)
        if not message:
            reject(evidence)
            continue
        key, owner = proposal['key'], message['author_id']
        family = ('budget', 'budget_krw') if key in ('budget', 'budget_krw') else (key,)
        old = next((c for c in reversed(task.get('constraints', [])) if c.get('owner_id') == owner
                    and c.get('key') in family and c.get('status') != 'superseded'), None)
        replace = proposal.get('replaces_constraint_id')
        replaced = next((c for c in task.get('constraints', []) if c.get('id') == replace), None)
        if replace and (not replaced or replaced.get('owner_id') != owner or replaced.get('key') not in family):
            reject(evidence)
            continue
        value = condition_value(key, message['text'])
        if value is None:
            value = short_budget_value(key, message['text'], owner, task)
        quoted_value = condition_value(key, evidence['quote'])
        if quoted_value is None:
            quoted_value = short_budget_value(key, evidence['quote'], owner, task)
        if value is None or quoted_value != value or type(value) is not type(proposal['value']) or value != proposal['value']:
            reject(evidence)
            continue
        projected = dict(owner_id=owner, key=old['key'] if old else key, value=value, kind=proposal['kind'],
                         replaces_constraint_id=old['id'] if old else None, source_message_ids=[message['id']])
        if projected not in result:
            result.append(projected)
    return result


def ground_items(raw, task, reject):
    items, aliases, grouped = [], {}, {}
    known = {i['id']: i for i in task.get('items', [])}
    for proposal in raw:
        evidence, title = proposal['evidence'], normalized(proposal['title'])
        message = source_message(evidence, task)
        supplied = proposal.get('existing_item_id')
        existing = known.get(supplied) if supplied else next((i for i in known.values()
                   if title in (normalized(i['title']), normalized(i['title'].split()[-1]))), None)
        if not message or supplied and (not existing or title not in (normalized(existing['title']), normalized(existing['title'].split()[-1]))):
            reject(evidence)
            continue
        if title in GENERIC or title == normalized(task.get('config', {}).get('region', '')) or ACTION.search(proposal['title']):
            reject(evidence)
            continue
        projected = project_item(proposal, task)
        if not projected:
            reject(evidence)
            continue
        if existing:
            ref = existing['id']
        else:
            if title not in grouped:
                digest = hashlib.sha256(title.encode('utf-8')).hexdigest()[:12]
                projected['client_ref'] = 'client:' + message['id'][:100] + ':' + digest
                grouped[title] = projected
                items.append(projected)
            canonical = grouped[title]
            canonical['source_message_ids'] = list(dict.fromkeys(canonical['source_message_ids'] + [message['id']]))
            ref = canonical['client_ref']
        aliases[proposal['title']] = ref
        if proposal.get('client_ref') and proposal['client_ref'] not in known:
            # An ambiguous model alias cannot bind an opinion to the wrong new item.
            alias = proposal['client_ref']
            aliases[alias] = ref if alias not in aliases or aliases[alias] == ref else None
    return items, aliases


def scoped_stance(quote):
    """Conservative polarity of one target span, used to validate rather than rewrite a claim."""
    if re.search(r'만약|라면|모르|철회하지|취소하지|않으면|않을', quote):
        return None
    affirmative = re.sub(r'(?:반대|싫어)(?:하)?지\s*않(?:아|아요|습니다|는다|음)?(?=$|[.!?\s])', ' 찬성 ', quote)
    scoped = re.sub(r'(?:좋아|찬성|동의)(?:하)?지\s*않(?:아|아요|습니다|는다|음)?(?=$|[.!?\s])', ' 반대 ', affirmative)
    scoped = re.sub(r'(?<!\w)안\s*(?:좋아|찬성|동의)', ' 반대 ', scoped)
    if re.search(STANCE['withdraw'], scoped):
        return 'withdraw'
    positive, negative = bool(re.search(STANCE['support'], scoped)), bool(re.search(STANCE['oppose'], scoped))
    return 'support' if positive and not negative else 'oppose' if negative and not positive else None


def reply_stance(reply, reference_texts):
    proposition = scoped_stance(reference_texts[-1]) if reference_texts else None
    if re.fullmatch(r'\s*(?:응|네|예)[.!?\s]*', reply):
        return proposition
    if re.fullmatch(r'\s*(?:아니|아니요)[.!?\s]*', reply):
        return {'support': 'oppose', 'oppose': 'support'}.get(proposition)
    return None


def contextual_target(proposal, item, context):
    ids = proposal.get('context_message_ids', [])
    records = [m for m in context if m['id'] in ids]
    if not ids or len(records) != len(set(ids)):
        return False
    # Only an unambiguous target in actually supplied read-only records resolves a reply.
    return any(title_in(m['text'], item) for m in records)


def third_party_opinion(message, item, task):
    prefix = re.match(r'\s*([가-힣]{2,10}?)(?:는|은|이가|가)\s+', message['text'])
    if not prefix:
        return False
    subject = normalized(prefix[1])
    own_names = {normalized(m.get('name', '')) for m in task.get('members', []) if m['user_id'] == message['author_id']}
    return subject not in {'우리', '본인', '거기', '여기', '저기', '그곳', '이곳', '저곳', '그것', '이것', '저것', '그거', '이거', '저거', normalized(item['title']), normalized(item['title'].split()[-1])} | own_names


def quoted_target_stance(message, quote, item, known):
    """Use adjacent source text to reject a quote clipped before negation or correction."""
    others = {other['title'] for other in known.values() if other['id'] != item['id']}
    boundary = re.compile(r'[.!?;\n]' + ''.join('|' + re.escape(title) for title in sorted(others)))
    occurrences = re.finditer(re.escape(quote), message)
    scopes = []
    for match in occurrences:
        suffix = message[match.end():]
        stop = boundary.search(suffix)
        prefix = re.search(r'안\s*$', message[:match.start()])
        scopes.append((prefix.group() if prefix else '') + quote + (suffix[:stop.start()] if stop else suffix))
    if not scopes or not all(scoped_stance(scope) == scoped_stance(quote) for scope in scopes):
        return None
    return scoped_stance(quote)


def omitted_direct_opinions(raw, task, known, aliases):
    supplied = {(p['evidence']['message_id'], aliases.get(p['item_id'],p['item_id'])) for p in raw}
    for message in task['recent_messages']:
        if message.get('room_id') not in (None,task.get('room_id')) or re.search(
                r'만약|라면|다들|모두|했대|라고|라더|말했|["“”‘’\'`]',message['text']):
            continue
        claims = {}
        for clause in re.finditer(r'(?:^|(?<=[.!;\n]))\s*([^.!?;\n]+?)(?=\s*(?:[.!;\n]|$))',message['text']):
            quote = clause[1].strip()
            matches = [item for item in known.values() if re.fullmatch(
                r'(?:(?:나는|난|저는|우리)\s+)?' + re.escape(item['title']) +
                r'(?:은|는|이|가|을|를)?\s+(?:가자|가보자|좋아(?:요)?|안\s*좋아(?:요)?|좋아하지\s*않아(?:요)?|싫어(?:요)?|찬성|반대)',quote)]
            if len(matches)!=1:
                continue
            item = matches[0]
            if (message['id'],item['id']) in supplied:
                continue
            stance = scoped_stance(quote)
            if stance:
                claims.setdefault(item['id'], {})[stance] = dict(item_id=item['id'],item_version=item['item_version'],
                    stance=stance,evidence=dict(message_id=message['id'],quote=quote))
        for stances in claims.values():
            if len(stances)==1:
                yield next(iter(stances.values()))


def ground_opinions(raw, task, items, aliases, context, reject, repairs):
    result = []
    known = {i['id']: i for i in task.get('items', [])}
    known.update({i['client_ref']: dict(i, id=i['client_ref'], item_version=1) for i in items})
    recovered = list(omitted_direct_opinions(raw, task, known, aliases))
    for proposal in raw + recovered:
        evidence = proposal['evidence']
        message = source_message(evidence, task)
        ref = aliases.get(proposal['item_id'], proposal['item_id'])
        item = known.get(ref)
        stance, quote = proposal['stance'], evidence['quote']
        if (not message or not item or proposal['item_version'] != item['item_version'] or stance == 'unclear'
                or third_party_opinion(message, item, task)
                or re.search(r'다들|모두|했대|라고|라더|말했|["“”‘’`]', message['text'])):
            reject(evidence)
            continue
        indirect = not title_in(quote, item)
        question = next((q for q in task.get('questions', []) if q.get('id') == proposal.get('question_id')
                         and q.get('status') == 'open' and q.get('field') == 'support_target'
                         and q.get('target_ref') == item['id'] and q.get('owner_id') in (None, message['author_id'])
                         and q.get('item_version', item['item_version']) == item['item_version'] and title_in(q.get('text', ''), item)), None)
        prior = []
        for current in task.get('recent_messages', []):
            if current['id'] == message['id']:
                break
            prior.append(current)
        references = list(context) + prior
        if indirect and not question:
            matching = {other['id'] for other in known.values() if any(title_in(m['text'], other)
                        for m in references if m['id'] in proposal.get('context_message_ids', []))}
            if matching != {item['id']} or not contextual_target(proposal, item, references):
                reject(evidence)
                continue
        short_reply = indirect and re.fullmatch(r'\s*(?:응|네|예|아니|아니요)[.!?\s]*', quote)
        reference_texts = [question['text']] if question else [m['text'] for m in references
                           if m['id'] in proposal.get('context_message_ids', []) and title_in(m['text'], item)]
        supported = (reply_stance(quote, reference_texts) if short_reply and message['text'].strip() == quote.strip()
                     else quoted_target_stance(message['text'], quote, item, known))
        if supported != stance:
            reject(evidence)
            continue
        claim = dict(item_id=ref, item_version=item['item_version'], author_id=message['author_id'], stance=stance,
                     source_message_id=message['id'], source_quote=quote)
        if question:
            claim['question_id'] = question['id']
        if claim not in result:
            result.append(claim)
            if proposal in recovered:
                repairs.append('opinion_completed_from_source')
    return result


UNSUPPORTED_REASONS = {
    'transaction': '예약·결제·구매·예매를 직접 처리하는 기능은 제공하지 않습니다.',
    'non_car_route': '현재 경로 조회는 자동차 이동만 지원합니다.',
}
REQUEST = r'(?:해\s*줘(?:요)?|해\s*주세요|해주세요|해줄래|해줄\s*수\s*있어|부탁해|진행해\s*줘|처리해\s*줘)(?=$|[.!?\s,])'
TRANSACTION_REQUEST = re.compile(r'(?:예약|결제|구매|예매)(?:을|를|도)?\s*' + REQUEST)
NON_CAR_MODE = re.compile(r'(?:기차|열차|버스|지하철|대중교통|도보|자전거|비행기|항공)(?:로|으로|를\s*타|\s*타고|\s+(?:이동|경로|길찾기|길|가는))')
ROUTE_TOPIC = re.compile(r'경로|길찾기|이동\s*시간|소요\s*시간|가는\s*(?:길|방법|법)')
ROUTE_REQUEST = re.compile(r'알려\s*줘|알려주세요|알려줄래|찾아\s*줘|찾아주세요|검색해|조회해|계산해|안내해|해\s*줘|해주세요')
NON_CAR_TRANSPORTS = {'walk', 'walking', 'transit', 'public', 'public_transport', 'train', 'bus', 'bicycle', 'bike', 'flight'}


def unsupported_clauses(text):
    for clause in re.split(r'[.!?;\n]', text):
        clause = EXCLUSION_CUE.split(clause)[-1].strip()
        if re.search(r'만약|라면|라고|했대|말했|["“”‘’`]', clause) or cancel_requested(clause):
            continue
        code = None
        if TRANSACTION_REQUEST.search(clause) or re.search(r'(?:표|티켓)\s*(?:좀\s*)?(?:사\s*줘|사주세요|끊어\s*줘|끊어주세요)(?=$|\s)', clause):
            code = 'transaction'
        elif NON_CAR_MODE.search(clause) and ROUTE_TOPIC.search(clause) and ROUTE_REQUEST.search(clause):
            code = 'non_car_route'
        if code:
            yield clause, code


def unsupported_requests(task):
    members = {m['user_id'] for m in task.get('members', [])}
    for message in task.get('recent_messages', []):
        if message.get('author_id') not in members:
            continue
        for clause, code in unsupported_clauses(message.get('text', '')):
            yield dict(request_id='request:' + message['id'] + ':service_request',
                       intent='service_request', operation='request', requested_fields=[],
                       owner_id=message['author_id'], source_message_id=message['id'],
                       evidence=dict(message_id=message['id'], quote=clause),
                       target_names=[], excluded_names=[], target_refs=[], excluded_refs=[], unresolved_target_names=[],
                       context_evidence=[], status='resolved', unsupported_code=code, unsupported_reason=UNSUPPORTED_REASONS[code])


def canonical_unsupported(task):
    """Only clear current unsupported requests receive code-owned service reasons."""
    request = next(unsupported_requests(task), None)
    if request:
        return dict(unsupported=True, unsupported_reason=request['unsupported_reason'], unsupported_code=request['unsupported_code'],
                    source_message_ids=[request['source_message_id']], source_refs=[])
    if (not task.get('recent_messages') and task.get('goal') in ('manual_replan', 'replan')
            and task.get('config', {}).get('transport') in NON_CAR_TRANSPORTS):
        return dict(unsupported=True, unsupported_reason=UNSUPPORTED_REASONS['non_car_route'], unsupported_code='non_car_route',
                    source_message_ids=[], source_refs=['config:transport'])
    return dict(unsupported=False, unsupported_reason='', unsupported_code='', source_message_ids=[], source_refs=[])


def ground_analysis(raw, task, aliases, has_effects):
    result = dict(raw)
    ids = {m['id'] for m in task.get('recent_messages', []) if m.get('author_id') in {p['user_id'] for p in task.get('members', [])}}
    result['source_message_ids'] = [m for m in raw.get('source_message_ids', []) if m in ids] or list(
        dict.fromkeys(m['id'] for m in task.get('recent_messages', []) if m['id'] in ids))
    known = {i['id'] for i in task.get('items', [])} | {c['id'] for c in task.get('constraints', [])}
    known |= {ref for observation in task.get('observations', []) for ref in observation.get('source_refs', [])}
    known |= {'config.' + k for k in task.get('config', {})}
    result['source_refs'] = [ref for ref in raw.get('source_refs', []) if ref in known]
    owners = {p['user_id'] for p in task.get('members', [])}
    missing = []
    for field in result['missing_fields']:
        if field['owner_id'] is not None and field['owner_id'] not in owners:
            continue
        field = dict(field, target_ref=aliases.get(field['target_ref'], field['target_ref']))
        if field['target_ref'] is None and field['field'] in ('origin', 'destination', 'lodging'):
            field['target_ref'] = 'anchor:' + field['field']
        if field['target_ref'] is None and field['field'] in ('region', 'start_date', 'end_date', 'travel_date', 'transport'):
            field['target_ref'] = 'config:' + field['field']
        field['source_message_ids'] = [m for m in field.get('source_message_ids', []) if m in ids] or result['source_message_ids']
        source_authors = {m['author_id'] for m in task.get('recent_messages', []) if m['id'] in field['source_message_ids']}
        if field['field'] == 'support_target' and field['owner_id'] not in source_authors:
            continue
        if field not in missing:
            missing.append(field)
    result['missing_fields'] = missing
    # Direct responses are exact confirmed values/quotes; paraphrases need a separate validated response boundary.
    confirmed = {v for v in task.get('config', {}).values() if isinstance(v, str)}
    confirmed |= {str(c['value']) for c in task.get('constraints', []) if c.get('status') == 'confirmed' and c.get('value') is not None}
    confirmed |= {i['title'] for i in task.get('items', [])}
    if result['direct_text'] not in confirmed:
        result['direct_text'] = ''
    unsupported = canonical_unsupported(task)
    result['unsupported'] = unsupported['unsupported']
    result['unsupported_reason'] = unsupported['unsupported_reason']
    result['unsupported_code'] = unsupported['unsupported_code']
    result['unsupported_source_message_ids'] = unsupported['source_message_ids']
    result['unsupported_source_refs'] = unsupported['source_refs']
    actionable = any(re.search(r'가자|찾아|검색|알려|해줘|계산|예산|철회|반대|말고|빼자|아니|^(?:응|네|예)[.!?\s]*$', m['text'])
                     or any(title_in(m['text'], i) for i in task.get('items', [])) for m in task.get('recent_messages', []))
    result['noop'] = bool(result['noop'] and not (has_effects or missing or actionable or result['needs_context'] or result['unsupported']))
    return result


def ground_batch(batch, task, context=()):
    raw = batch.model_dump()
    rejected = []
    def reject(evidence):
        if evidence['message_id'] not in rejected:
            rejected.append(evidence['message_id'])
    repairs = []
    domain_requests = list(raw['analysis'].get('requests', []))
    for proposal in raw['item_proposals']:
        message = source_message(proposal['evidence'], task)
        if not message or not project_item(proposal, task) or any(
            r['evidence']['message_id']==message['id'] and r['intent'] in LOOKUP_INTENTS for r in domain_requests):
            continue
        title = proposal['title']
        for clause in explicit_lookup_clauses(message):
            if re.fullmatch(re.escape(title) + r'(?:을|를)?\s*(?:찾아|검색해)\s*(?:줘(?:요)?|주세요)', clause):
                domain_requests.append(dict(intent='place_lookup', target_names=[title], requested_fields=['location'],
                    evidence=dict(message_id=message['id'], quote=clause)))
                repairs.append('lookup_aligned_to_source')
    requests, invalid_source = ground_requests(domain_requests, task, context, reject, repairs)
    requests = assign_request_ids(requests + list(unsupported_requests(task)))
    bind_batch_cancellations(task, requests)
    lookup_intents = (*LOOKUP_INTENTS, ROUTE_INTENT)
    lookup_sources = {r['source_message_id'] for r in requests if r['intent'] in lookup_intents}
    proposals = []
    for proposal in raw['item_proposals']:
        evidence = proposal['evidence']
        message = source_message(evidence, task)
        if message and message['id'] in lookup_sources and not any(
                title_in(clause, proposal) and scoped_stance(clause) in ('support', 'oppose')
                for clause in source_clauses(message['text'], evidence['quote'])):
            reject(evidence)
            continue
        proposals.append(proposal)
    items, aliases = ground_items(proposals, task, reject)
    conditions = list(raw['constraint_proposals'])
    for message in task['recent_messages']:
        if (not re.search(r'(?:^|[.!?;\n])\s*(?:내|제|나의|저의|저는|나는|난)\s*(?:개인\s*)?예산',message['text'])
                or any(c['key'] in ('budget','budget_krw') and c['evidence']['message_id']==message['id']
                       for c in conditions)):
            continue
        value = condition_value('budget_krw',message['text'])
        evidence = dict(message_id=message['id'],quote=message['text'])
        if value is not None and source_message(evidence,task) and message.get('room_id') in (None,task.get('room_id')):
            conditions.append(dict(key='budget_krw',value=value,kind='hard',evidence=evidence))
            repairs.append('budget_completed_from_source')
    constraints = ground_conditions(conditions, task, reject)
    opinions = ground_opinions(raw['support_observations'], task, items, aliases, context, reject, repairs)
    analysis = ground_analysis(raw['analysis'], task, aliases, bool(items or constraints or opinions or requests))
    analysis['requests'] = requests
    analysis['lookup_scope_rejected'] = not requests and any(
        r['intent'] in lookup_intents for r in raw['analysis'].get('requests', []))
    analysis['request_grounding_failed'] = invalid_source
    analysis['source_repairs'] = list(dict.fromkeys(repairs))
    resolved_support = {(o['author_id'], o['source_message_id'], o['stance']) for o in opinions}
    analysis['missing_fields'] = [f for f in analysis['missing_fields']
        if f['field'] != 'support_target' or not any(
            (f['owner_id'], source, f['stance']) in resolved_support for source in f['source_message_ids'])]
    lookup_requests = [r for r in requests if r['intent'] in lookup_intents or r['operation'] == 'cancel']
    analysis['missing_fields'] = [f for f in analysis['missing_fields']
        if f['field'] != 'target_places' or not any(r['owner_id'] == f['owner_id']
            and r['source_message_id'] in f['source_message_ids']
            and f['target_ref'] in (None, r['request_id']) for r in lookup_requests)]
    for request in lookup_requests:
        if request['status'] in ('needs_context', 'needs_input'):
            text = '어떤 요청을 취소할까요?' if request['operation'] == 'cancel' else '어느 장소를 조회할까요?'
            analysis['missing_fields'].append(dict(field='target_places', target_ref=request['request_id'], text=text,
                owner_id=request['owner_id'], source_message_ids=[request['source_message_id']],
                source='history' if request['status'] == 'needs_context' else 'user', stance=None))
    if any(r['status'] == 'needs_context' for r in requests):
        analysis['needs_context'] = True
    elif requests and not any(f.get('source') == 'history' for f in analysis['missing_fields']):
        analysis['needs_context'], analysis['context_queries'] = False, []
    return dict(item_proposals=items, constraint_proposals=constraints, support_observations=opinions, questions=[],
                analysis=analysis), rejected
