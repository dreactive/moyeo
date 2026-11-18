"""Two bounded auxiliary passes; historical records never become new sources."""
import asyncio
from copy import deepcopy
import re
from time import perf_counter
from ai.auxiliary_client import ExternalAuxiliary, AuxiliaryConfigurationError, AuxiliaryServiceError
from ai.auxiliary_schema import AuxiliaryBatch, AuxiliaryAnalysis
from ai.auxiliary_grounding import ground_batch
from ai.auxiliary_requests import observed_places, request_needs_context, request_context_records


def create_auxiliary(config: dict):
    backend = config.get('auxiliary_backend', 'external')
    if backend == 'external':
        return ExternalAuxiliary(config)
    if backend == 'fixture':
        from ai.auxiliary_fixture import FixtureAuxiliary
        return FixtureAuxiliary()
    raise ValueError('Unknown auxiliary backend')


def minimal_auxiliary_task(task):
    config = task.get('config', {})
    return dict(room_id=task.get('room_id'), observed_places=observed_places(task)[-40:],
                recent_messages=[{k: m[k] for k in ('id', 'author_id', 'text', 'seq', 'reply_to_message_id') if k in m}
                                 for m in task.get('recent_messages', [])[-20:]],
                members=[{k: m[k] for k in ('user_id', 'name') if k in m} for m in task.get('members', [])],
                config={k: config[k] for k in ('region', 'start_date', 'end_date', 'transport', 'day_start_time', 'day_end_time') if k in config},
                items=[{k: i[k] for k in ('id', 'item_version', 'title', 'state', 'source_message_ids') if k in i}
                       for i in task.get('items', [])[-40:]],
                constraints=[{k: c[k] for k in ('id', 'owner_id', 'key', 'value', 'status') if k in c}
                             for c in task.get('constraints', []) if c.get('status') != 'superseded'][-40:],
                questions=[{k: q[k] for k in ('id', 'owner_id', 'field', 'target_ref', 'text', 'status', 'answer', 'answered_by') if k in q}
                           for q in task.get('questions', []) if q.get('status') in ('open', 'answered')][-20:])


def relevant_context(task, queries, requests=()):
    """Select full records by explicit reference/keyword, with fixed count and byte-like character bounds."""
    requested = any(request_needs_context(r, task) for r in requests)
    if not queries and not requested:
        return []
    eligible = request_context_records(task, requests) if requested else None
    expanded = list(queries) + ([p['name'] for p in observed_places(task)] if requested else [])
    for record in task.get('items', []) + task.get('questions', []) + task.get('constraints', []):
        if record.get('id') in queries:
            expanded += [str(record.get(k, '')) for k in ('title', 'text', 'key')]
    terms = {term.casefold() for query in expanded for term in re.findall(r'[\w가-힣]+', query) if len(term) >= 2}
    current = {m['id'] for m in task.get('recent_messages', [])}
    ranked = []
    for index, message in enumerate(task.get('conversation_context', [])):
        if message.get('id') in current or not isinstance(message.get('text'), str) or eligible is not None and message.get('id') not in eligible:
            continue
        haystack = message['text'].casefold()
        score = sum(len(term) for term in terms if term in haystack)
        if message.get('id') in queries:
            score += 100
        if eligible is not None and message['id'] in eligible:
            score += 1
        if score:
            ranked.append((score, index, message))
    chosen, remaining = [], 12000
    for _, index, message in sorted(ranked, key=lambda row: (row[0], row[1]), reverse=True):
        if len(chosen) >= 8:
            break
        if len(message['text']) > remaining:
            continue
        remaining -= len(message['text'])
        chosen.append((index, {k: message[k] for k in ('id', 'author_id', 'text', 'seq', 'reply_to_message_id') if k in message}))
    return [message for _, message in sorted(chosen, key=lambda pair: pair[0])]


def _merge(first, second):
    raw = first.model_dump()
    following = second.model_dump()
    identities = dict(item_proposals=lambda p: (p['evidence']['message_id'], p['title'], p.get('client_ref')),
                      constraint_proposals=lambda p: (p['evidence']['message_id'], p['key']),
                      support_observations=lambda p: (p['evidence']['message_id'], p['item_id']))
    for key, identity in identities.items():
        grouped = {identity(p): p for p in raw[key]}
        grouped.update({identity(p): p for p in following[key]})
        raw[key] = list(grouped.values())
    def request_key(request):
        evidence = request['evidence']
        return (evidence['message_id'], evidence['quote'], request['intent'], request['operation'],
                tuple(sorted(request['requested_fields'])))

    requests = list(raw['analysis']['requests'])
    for request in following['analysis']['requests']:
        matching = [index for index, previous in enumerate(requests) if request_key(previous) == request_key(request)
                    and (not previous['target_names'] or set(previous['target_names']) <= set(request['target_names']))]
        if len(matching) == 1:
            requests[matching[0]] = request
        elif request not in requests:
            requests.append(request)
    missing = {}
    for field in raw['analysis']['missing_fields'] + following['analysis']['missing_fields']:
        key = (field['field'], field['target_ref'], field['owner_id'], field['stance'], tuple(field['source_message_ids']))
        missing[key] = field
    raw['analysis'] = dict(following['analysis'], requests=requests[:20], missing_fields=list(missing.values())[:20])
    return AuxiliaryBatch.model_validate(raw)


def obvious_noop(task):
    messages = task.get('recent_messages', [])
    members = {m['user_id'] for m in task.get('members', [])}
    return (task.get('goal') not in ('manual_replan', 'replan', 'confirm') and bool(messages)
            and all(m.get('author_id') in members and re.fullmatch(
                r'\s*(?:안녕|안녕하세요|좋은\s*아침|ㅋㅋ+|ㅎㅎ+|고마워|감사합니다)[.!?~\s]*', m['text']) for m in messages))


def _empty_analysis():
    return AuxiliaryAnalysis(summary='', needs_context=False, context_queries=[], missing_fields=[], unsupported=False,
                             unsupported_reason='', direct_text='', noop=False).model_dump()


def _failure(task, backend, code, attempts, elapsed):
    return dict(item_proposals=[], constraint_proposals=[], support_observations=[], questions=[], analysis=_empty_analysis(),
                extraction_report=dict(status='failed', issue_codes=[code], rejected_message_ids=[m['id'] for m in task.get('recent_messages', [])],
                                       attempts=attempts, context_completion_calls=0, backend=backend, duration_ms=elapsed),
                completion='needs_input', last_processed_message_id=None)


async def prepare_auxiliary(task: dict, auxiliary) -> dict:
    started = perf_counter()
    backend = getattr(auxiliary, 'backend', 'provided')
    minimal = minimal_auxiliary_task(task)
    scope = dict(task, recent_messages=deepcopy(task['recent_messages'][-20:]))
    elapsed = lambda: round((perf_counter() - started) * 1000, 3)
    if obvious_noop(scope):
        analysis = dict(_empty_analysis(), summary='인사', noop=True, source_message_ids=[m['id'] for m in minimal['recent_messages']])
        return dict(item_proposals=[], constraint_proposals=[], support_observations=[], questions=[], analysis=analysis,
                    extraction_report=dict(status='ok', issue_codes=[], rejected_message_ids=[], attempts=0,
                                           context_completion_calls=0, context_message_ids=[], backend=backend, duration_ms=elapsed()))
    try:
        first = AuxiliaryBatch.model_validate(await asyncio.to_thread(auxiliary.extract, deepcopy(minimal), stage=1))
    except AuxiliaryConfigurationError:
        return _failure(scope, backend, 'auxiliary_configuration_missing', 1, elapsed())
    except (ValueError, TypeError):
        return _failure(scope, backend, 'auxiliary_invalid_output', 1, elapsed())
    except Exception:
        return _failure(scope, backend, 'auxiliary_request_failed', 1, elapsed())
    domain_requests = first.model_dump()['analysis']['requests']
    needs_context = first.analysis.needs_context or any(request_needs_context(r, scope) for r in domain_requests)
    context = relevant_context(task, first.analysis.context_queries, domain_requests) if needs_context else []
    batch, completion_calls, issues = first, 0, []
    if context:
        completion_calls = 1
        enriched = dict(deepcopy(minimal), conversation_context=deepcopy(context), first_pass=first.model_dump())
        try:
            second = AuxiliaryBatch.model_validate(await asyncio.to_thread(auxiliary.extract, enriched, stage=2))
            batch = _merge(first, second)
        except Exception:
            # Valid independent first-pass work is retained; unresolved context is explicit.
            issues.append('auxiliary_context_completion_failed')
    transient = 'auxiliary_context_completion_failed' in issues
    output, rejected = ground_batch(batch, scope, [] if transient else context)
    if 'auxiliary_context_completion_failed' not in issues:
        for request in output['analysis']['requests']:
            if request['status'] == 'needs_context':
                request['status'] = 'needs_input'
        unresolved = [f for f in output['analysis']['missing_fields'] if f.get('source') == 'history']
        for field in unresolved:
            field['source'] = 'user'
        if unresolved and not any(r['status'] == 'needs_context' for r in output['analysis']['requests']):
            output['analysis']['needs_context'] = False
            output['analysis']['context_queries'] = []
    if rejected:
        issues.append('ungrounded_proposal')
    if output['analysis'].get('request_grounding_failed'):
        issues.append('ungrounded_request')
    status = 'failed' if output['analysis'].get('request_grounding_failed') else 'filtered' if issues else 'ok'
    output['extraction_report'] = dict(status=status, issue_codes=issues,
        rejected_message_ids=rejected, attempts=1 + completion_calls, context_completion_calls=completion_calls,
        context_message_ids=[m['id'] for m in context], backend=backend, duration_ms=elapsed())
    repairs = output['analysis'].pop('source_repairs', [])
    if repairs:
        output['extraction_report']['repairs'] = repairs
    return output
