"""Provenance and context checks for the raw auxiliary handoff."""
from copy import deepcopy
import hashlib
import json
import re

from ai.auxiliary_requests import LOOKUP_INTENTS
from ai.condition_grounding import condition_value
from ai.grounding import normalized, source_message
from ai.request_lifecycle import TERMINAL


MESSAGE_FIELDS = ('id', 'author_id', 'text', 'seq', 'reply_to_message_id', 'room_id')
DEICTIC_REPLY = re.compile(
    r'^\s*(?:응|네|예|좋아|아니|아니요|맞아|그대로)[.!?\s]*$'
    r'|(?:^|[.!?;\s])(?:거기(?:는|를)?|거긴|거길|그건|그걸|그\s*(?:곳|장소|요청|거))'
    r'|(?:^|[.!?;\s])아니\s+\d')


class PreparedAuxiliaryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def message_provenance(messages):
    return [{key: message[key] for key in MESSAGE_FIELDS if key in message} for message in messages]


def retry_scope(task, saved):
    retry_owners = {(r['source_message_id'], r['owner_id']) for r in saved
                    if r.get('status') == 'needs_context'}
    history = task.get('conversation_context', [])
    originals = [m for m in history if (m['id'], m.get('author_id')) in retry_owners
                 and m.get('room_id') in (None, task.get('room_id'))][-20:]
    first = next((index for index, m in enumerate(history)
                  if originals and m['id'] == originals[0]['id']), len(history))
    context = [m for m in history[:first] if m.get('room_id') in (None, task.get('room_id'))]
    return dict(task, recent_messages=originals, conversation_context=context)


def prepared_scope(task):
    if task.get('_selection_only'):
        return 'selection_only', task
    messages = task.get('recent_messages', [])[-20:]
    scope = dict(task, recent_messages=messages)
    if not messages:
        saved = [r for r in task.get('pending_requests', []) if r.get('status') not in TERMINAL]
        if saved or task.get('pending_item_ids'):
            retry = retry_scope(task, saved)
            return ('saved_context_retry', retry) if retry['recent_messages'] else ('saved_state', scope)
    if messages and isinstance(messages[0].get('seq'), int):
        boundary = messages[0]['seq']
        scope['conversation_context'] = [m for m in task.get('conversation_context', [])
            if not isinstance(m.get('seq'), int) or m['seq'] < boundary]
    scope['conversation_context'] = [m for m in scope.get('conversation_context', [])
        if m.get('room_id') in (None, task.get('room_id'))]
    return 'current', scope


def validate_sources(scope):
    sources = scope['recent_messages']
    members = {m['user_id'] for m in scope.get('members', [])}
    ids = [m.get('id') for m in sources]
    sequences = [m.get('seq') for m in sources if 'seq' in m]
    if (len(set(ids)) != len(ids)
            or any(not m.get('id') or m.get('author_id') not in members
                   or not isinstance(m.get('text'), str)
                   or m.get('room_id') not in (None, scope.get('room_id')) for m in sources)
            or any(type(seq) is not int or seq < 1 for seq in sequences)
            or sequences != sorted(set(sequences))):
        raise PreparedAuxiliaryError('prepared_source_invalid')


def scope_identity(mode, scope):
    return dict(room_id=scope.get('room_id'), run_id=scope.get('run_id'), goal=scope.get('goal'),
                source_mode=mode, source_messages=message_provenance(scope['recent_messages']))


def context_basis(minimal, context, scope):
    # Save the prompt basis, including state that affects indirect reference selection.
    state = {key: value for key, value in minimal.items() if key != 'recent_messages'}
    state['pending_requests'] = scope.get('pending_requests', [])
    state['history'] = message_provenance(context)
    encoded = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return dict(digest=hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
                items={i['id']: i['title'] for i in minimal['items']})


def explicit_request(request):
    names = request['target_names'] + request['excluded_names']
    return (not request['context_evidence']
            and (request['intent'] not in LOOKUP_INTENTS or bool(names))
            and (request['operation'] != 'cancel' or bool(names))
            and all(normalized(name) in normalized(request['evidence']['quote']) for name in names))


def explicit_opinion(opinion, batch, items):
    if opinion['question_id'] or opinion['context_message_ids']:
        return False
    titles = {i['id']: i['title'] for i in items}
    titles.update({p['client_ref']: p['title'] for p in batch['item_proposals']
                   if p['client_ref'] and p['client_ref'] not in titles})
    title = titles.get(opinion['item_id'])
    return bool(title and normalized(title) in normalized(opinion['evidence']['quote']))


def explicit_condition(condition):
    return condition_value(condition['key'], condition['evidence']['quote']) is not None


def needs_fresh_context(batch, minimal):
    analysis = batch['analysis']
    return bool(
        analysis['needs_context'] or analysis['context_queries'] or analysis['direct_text']
        or any(m['source'] != 'user' or m['field'] == 'support_target' for m in analysis['missing_fields'])
        or any(not explicit_request(r) for r in analysis['requests'])
        or any(not explicit_condition(c) for c in batch['constraint_proposals'])
        or any(not explicit_opinion(o, batch, minimal['items']) for o in batch['support_observations'])
        or any(DEICTIC_REPLY.search(m['text']) for m in minimal['recent_messages']))


def literal_fallback(first, scope):
    """Keep independently quotable first-pass work and ask about unresolved intent."""
    raw = deepcopy(first)
    analysis = raw['analysis']
    analysis.update(summary='', needs_context=False, context_queries=[], source_refs=[], direct_text='', noop=False)
    analysis['missing_fields'] = [f for f in analysis['missing_fields']
        if f['source'] == 'user' and not f['target_ref'] and f['field'] != 'support_target']
    raw['constraint_proposals'] = [dict(c, replaces_constraint_id=None, context_message_ids=[])
                                   for c in raw['constraint_proposals'] if explicit_condition(c)]
    items = scope.get('items', [])
    opinions = [o for o in raw['support_observations'] if explicit_opinion(o, raw, items)]
    for opinion in raw['support_observations']:
        source = source_message(opinion['evidence'], scope)
        if not source or opinion in opinions:
            continue
        question = dict(field='support_target', target_ref=None, text='어느 장소에 대한 의견인가요?',
                        owner_id=source['author_id'], source_message_ids=[source['id']], source='user')
        if question not in analysis['missing_fields']:
            analysis['missing_fields'].append(question)
    raw['support_observations'] = opinions
    analysis['missing_fields'] = analysis['missing_fields'][:20]
    analysis['requests'] = [r if explicit_request(r) else dict(r, target_names=[], excluded_names=[],
                            context_evidence=[]) for r in analysis['requests']]
    return raw


def rebind_item_mentions(raw, scope, basis):
    known = {i['id']: i['title'] for i in scope['items']}
    for proposal in raw['item_proposals']:
        supplied = proposal['existing_item_id']
        prior = basis['items'].get(supplied)
        if (not prior or normalized(prior) != normalized(proposal['title'])
                or supplied in known and normalized(known[supplied]) == normalized(prior)):
            continue
        exact = [ref for ref, title in known.items() if normalized(title) == normalized(prior)]
        if len(exact) == 1:
            proposal['existing_item_id'] = exact[0]
    return raw
