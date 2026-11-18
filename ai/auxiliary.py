"""Two bounded auxiliary passes; historical records never become new sources."""
import asyncio
from copy import deepcopy
import re
from time import perf_counter
from ai.auxiliary_client import ExternalAuxiliary, AuxiliaryConfigurationError
from ai.auxiliary_schema import AuxiliaryBatch, AuxiliaryAnalysis
from ai.auxiliary_grounding import ground_batch
from ai.auxiliary_requests import observed_places, request_needs_context, request_context_records


from ai.prepared_auxiliary import (
    PreparedAuxiliaryError, context_basis, explicit_request, literal_fallback, needs_fresh_context,
    message_provenance, prepared_scope, rebind_item_mentions, scope_identity, validate_sources,
)


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


async def _extract_raw(scope, auxiliary, *, complete_context=True):
    """Run the ordinary two bounded passes and retain their raw interpretations."""
    started = perf_counter()
    backend = getattr(auxiliary, 'backend', 'provided')
    minimalist = minimal_auxiliary_task(scope)

    def report(status, issues, attempts, context_calls=0, context=()):
        return dict(status=status, issue_codes=issues, attempts=attempts, backend=backend,
                    context_completion_calls=context_calls,
                    context_message_ids=[m['id'] for m in context],
                    duration_ms=round((perf_counter() - started) * 1000, 3))

    if obvious_noop(scope):
        return dict(first_batch=None, batch=None, context_messages=[], noop=True,
                    extraction_report=report('ok', [], 0))
    try:
        first = AuxiliaryBatch.model_validate(await asyncio.to_thread(auxiliary.extract, deepcopy(minimalist), stage=1))
    except AuxiliaryConfigurationError:
        issue = 'auxiliary_configuration_missing'
    except (ValueError, TypeError):
        issue = 'auxiliary_invalid_output'
    except Exception:
        issue = 'auxiliary_request_failed'
    else:
        raw = first.model_dump(mode='json')
        context = _completion_context(scope, raw)
        batch, issues = first, []
        if context and complete_context:
            enriched = dict(deepcopy(minimalist), conversation_context=deepcopy(context), first_pass=deepcopy(raw))
            try:
                second = AuxiliaryBatch.model_validate(await asyncio.to_thread(auxiliary.extract, enriched, stage=2))
                batch = _merge(first, second)
            except Exception:
                # Valid independent first-pass work survives a failed completion call.
                issues.append('auxiliary_context_completion_failed')
        if context and not complete_context:
            issues.append('auxiliary_context_completion_skipped')
        calls = int(bool(context) and complete_context)
        return dict(first_batch=raw, batch=batch.model_dump(mode='json'), context_messages=context,
                    extraction_report=report('filtered' if issues else 'ok', issues, 1 + calls, calls, context))
    return dict(first_batch=None, batch=None, context_messages=[],
                extraction_report=report('failed', [issue], 1))


def _completion_context(scope, raw):
    if raw is None:
        return []
    analysis = raw['analysis']
    requests = analysis['requests']
    if analysis['needs_context'] or any(request_needs_context(r, scope) for r in requests):
        return relevant_context(scope, analysis['context_queries'], requests)
    return []


def _validate_envelope(task, scope, mode, prepared):
    validate_sources(scope)
    if (not isinstance(prepared, dict) or prepared.get('schema_version') != 1
            or any(prepared.get(key) != scope.get(key) for key in ('room_id', 'run_id', 'goal'))
            or prepared.get('source_mode') not in ('current', 'saved_context_retry', 'saved_state', 'selection_only')
            or not isinstance(prepared.get('source_messages'), list)
            or any(not isinstance(m, dict) or not isinstance(m.get('id'), str) for m in prepared['source_messages'])
            or type(prepared.get('refresh_count')) is not int or prepared['refresh_count'] not in (0, 1)
            or not isinstance(prepared.get('context_messages'), list)
            or not isinstance(prepared.get('context_basis'), dict)
            or not isinstance(prepared['context_basis'].get('items'), dict)
            or not isinstance(prepared.get('extraction_report'), dict)):
        raise PreparedAuxiliaryError('prepared_source_invalid')
    validate_sources(dict(scope, recent_messages=prepared['source_messages']))
    identity = scope_identity(mode, scope)
    same_sources = all(prepared.get(key) == value for key, value in identity.items())
    if not same_sources:
        # A job with a reserved chat range must never change sources. Jobs
        # without live sources may observe updated pending work at execution.
        prior_mode = prepared['source_mode']
        if (task['recent_messages'] or prior_mode != 'saved_context_retry' and prepared['source_messages']
                or 'selection_only' in (mode, prior_mode)):
            raise PreparedAuxiliaryError('prepared_source_invalid')
        history = {m['id']: m for m in message_provenance(task.get('conversation_context', []))}
        if any(m['id'] in history and m != history[m['id']] for m in prepared['source_messages']):
            raise PreparedAuxiliaryError('prepared_source_invalid')
    report = prepared['extraction_report']
    if (report.get('status') not in ('ok', 'filtered', 'failed')
            or not isinstance(report.get('issue_codes'), list)
            or report['status'] == 'failed' and not report['issue_codes']
            or not isinstance(report.get('duration_ms'), (float, int))
            or type(report.get('attempts')) is not int or not isinstance(report.get('backend'), str)):
        raise PreparedAuxiliaryError('prepared_source_invalid')
    batches = []
    for field in ('first_batch', 'batch'):
        raw = prepared.get(field)
        if isinstance(raw, dict):
            try:
                raw = AuxiliaryBatch.model_validate(raw).model_dump(mode='json')
            except (ValueError, TypeError):
                raise PreparedAuxiliaryError('prepared_source_invalid') from None
        elif raw is not None:
            raise PreparedAuxiliaryError('prepared_source_invalid')
        batches.append(raw)
    if None in batches and not (batches == [None, None] and
            (prepared.get('noop') is True or report['status'] == 'failed' or prepared['source_mode'] in ('saved_state', 'selection_only'))):
        raise PreparedAuxiliaryError('prepared_source_invalid')
    if same_sources and prepared.get('noop') is True and not obvious_noop(scope):
        raise PreparedAuxiliaryError('prepared_source_invalid')
    return batches[0], batches[1], same_sources


def _envelope(scope, mode, extracted, refresh_count=0):
    minimal = minimal_auxiliary_task(scope)
    batches = (extracted['first_batch'], extracted['batch'])
    return dict(scope_identity(mode, scope), schema_version=1, refresh_count=refresh_count,
                context_basis=context_basis(minimal, extracted['context_messages'], scope),
                context_dependent=any(raw and needs_fresh_context(raw, minimal) for raw in batches),
                **extracted)


async def _refresh_raw(scope, previous, first, auxiliary):
    """Use one fresh completion call when a queued interpretation's basis changed."""
    started = perf_counter()
    minimal = minimal_auxiliary_task(scope)
    context = _completion_context(scope, first)
    basis = context_basis(minimal, context, scope)
    if first is None or basis == previous['context_basis'] and context == previous['context_messages']:
        return dict(previous, refresh_count=1)
    literal = literal_fallback(first, scope)
    call = deepcopy(minimal)
    if context:
        hints = deepcopy(literal)
        hints['analysis'].update(needs_context=first['analysis']['needs_context'],
                                 context_queries=first['analysis']['context_queries'])
        call.update(conversation_context=deepcopy(context), first_pass=hints)
    issues = []
    try:
        response = AuxiliaryBatch.model_validate(await asyncio.to_thread(auxiliary.extract, call, stage=2 if context else 1))
        explicit = deepcopy(literal)
        explicit['analysis']['requests'] = [r for r in first['analysis']['requests'] if explicit_request(r)]
        refreshed = _merge(AuxiliaryBatch.model_validate(explicit), response).model_dump(mode='json')
    except Exception:
        refreshed = literal
        issues.append('auxiliary_context_revalidation_failed')
    report = deepcopy(previous['extraction_report'])
    report.update(status='filtered' if issues else 'ok', issue_codes=issues, attempts=report['attempts'] + 1,
                  revalidation_calls=1, context_message_ids=[m['id'] for m in context],
                  duration_ms=report['duration_ms'] + round((perf_counter() - started) * 1000, 3))
    return _envelope(scope, previous['source_mode'], dict(first_batch=first, batch=refreshed, context_messages=context,
                    extraction_report=report), refresh_count=1)


def _saved_state_extraction():
    return dict(first_batch=None, batch=None, context_messages=[],
                extraction_report=dict(status='ok', issue_codes=[], attempts=0, context_completion_calls=0,
                                       context_message_ids=[], backend='saved-request-state', duration_ms=0))


async def extract_auxiliary(task: dict, auxiliary, *, previous=None) -> dict:
    """Return JSON-serializable model interpretations with source and context provenance."""
    mode, scope = prepared_scope(task)
    if previous is not None:
        first, _, same_sources = _validate_envelope(task, scope, mode, previous)
        if previous['refresh_count'] == 1:
            return deepcopy(previous)
        if not same_sources:
            if mode != 'saved_context_retry':
                return dict(previous, refresh_count=1)
            extracted = await _extract_raw(scope, auxiliary, complete_context=False)
            report = extracted['extraction_report']
            report['revalidation_calls'] = report['attempts']
            report['attempts'] += previous['extraction_report']['attempts']
            return _envelope(scope, mode, extracted, refresh_count=1)
        return await _refresh_raw(scope, previous, first, auxiliary)
    validate_sources(scope)
    extracted = (_saved_state_extraction() if mode in ('saved_state', 'selection_only')
                 else await _extract_raw(scope, auxiliary))
    return _envelope(scope, mode, extracted)

def _ground_output(scope, extracted, raw, context):
    report = deepcopy(extracted['extraction_report'])
    issues = report['issue_codes']
    if report['status'] == 'failed':
        return _failure(scope, report['backend'], issues[0], report['attempts'], report['duration_ms'])
    if raw is None:
        analysis = _empty_analysis()
        if extracted.get('noop'):
            analysis.update(summary='인사', noop=True, source_message_ids=[m['id'] for m in scope['recent_messages']])
        return dict(item_proposals=[], constraint_proposals=[], support_observations=[], questions=[], analysis=analysis,
                    extraction_report=dict(report, rejected_message_ids=[]))
    transient = 'auxiliary_context_completion_failed' in issues
    no_context = transient or 'auxiliary_context_completion_skipped' in issues
    output, rejected = ground_batch(AuxiliaryBatch.model_validate(raw), scope, [] if no_context else context)
    if {'auxiliary_context_revalidation_failed', 'auxiliary_context_revalidation_stale'} & set(issues):
        for request in output['analysis']['requests']:
            if request['operation'] == 'cancel' and not request['target_names']:
                request.update(status='needs_input', cancelled_request_ids=[])
    if not transient:
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
    output['extraction_report'] = dict(report, status=status, rejected_message_ids=rejected)
    repairs = output['analysis'].pop('source_repairs', [])
    if repairs:
        output['extraction_report']['repairs'] = repairs
    return output


def ground_auxiliary(task: dict, prepared: dict) -> dict:
    """Ground a prepared interpretation locally against the latest authoritative room state."""
    mode, scope = prepared_scope(task)
    first, raw, same_sources = _validate_envelope(task, scope, mode, prepared)
    if not same_sources:
        if mode == 'saved_context_retry' and not prepared['refresh_count']:
            raise PreparedAuxiliaryError('prepared_context_stale')
        return _ground_output(scope, _saved_state_extraction(), None, [])
    context = _completion_context(scope, first)
    minimal = minimal_auxiliary_task(scope)
    basis = context_basis(minimal, context, scope)
    dependent = bool(context or prepared['context_messages']) or any(
        batch and needs_fresh_context(batch, minimal) for batch in (first, raw))
    dependent |= prepared.get('context_dependent') is True
    if (dependent and (basis != prepared['context_basis'] or context != prepared['context_messages'])):
        if not prepared['refresh_count']:
            raise PreparedAuxiliaryError('prepared_context_stale')
        raw = literal_fallback(first, scope)
        report = dict(prepared['extraction_report'], status='filtered',
                      issue_codes=['auxiliary_context_revalidation_stale'])
        prepared = dict(prepared, extraction_report=report)
        context = []
    if raw is not None:
        raw = rebind_item_mentions(raw, scope, prepared['context_basis'])
    return _ground_output(scope, prepared, raw, context)


async def prepare_auxiliary(task: dict, auxiliary) -> dict:
    """Preserve the single-call API for callers outside the prepared queue."""
    scope = dict(task, recent_messages=deepcopy(task['recent_messages'][-20:]))
    extracted = await _extract_raw(scope, auxiliary)
    return _ground_output(scope, extracted, extracted['batch'], extracted['context_messages'])
