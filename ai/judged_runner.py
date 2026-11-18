"""External facts -> actual calls -> supplied Qwen judge -> registered execution."""
import asyncio
from copy import deepcopy
import math
import json
from time import perf_counter
from httpx import HTTPError

from ai.context import build_context
from ai.auxiliary_requests import cancellation_options, observed_places
from ai.cost_inputs import build_cost_inputs
from ai.planning import itinerary_arguments
from ai.decision_candidates import build_decision_candidates, compact_decision_context
from ai.outcome import assemble_result
from ai.questions import valid_questions
from ai.result import empty_result
from ai.runner import execute_selected, StaleExecution
from ai.request_lifecycle import request_states, superseded_requests, complete_candidate, fail_candidate, call_key, TERMINAL
from ai.selection import apply_selection
from ai.tools.context import build_tool_context
from ai.tools.validation import same_arguments, validate_arguments
from ai.trace import emit


def preview_proposals(task, output):
    """Project grounded proposals locally, retaining backend-owned IDs and confirmation."""
    task = deepcopy(task)
    aliases = {}
    planned = set((task.get('current_plan') or {}).get('selected_item_ids', []))
    new_refs = [ref for ref in task.get('pending_item_ids', []) if ref not in planned]
    for proposal in output.get('item_proposals', []):
        item = next((i for i in task['items'] if i['id'] == proposal.get('existing_item_id')), None)
        if item is None:
            item = next((i for i in task['items'] if i.get('kind') == proposal.get('kind')
                         and i.get('title') == proposal.get('title')), None)
        if item is None:
            item = dict(proposal, id=proposal['client_ref'], item_version=1, state='mentioned',
                        supporter_ids=[], opponent_ids=[])
            task['items'].append(item)
        if item['id'] not in planned and item['id'] not in new_refs:
            new_refs.append(item['id'])
        item['source_message_ids'] = list(dict.fromkeys(item.get('source_message_ids', [])
                                                      + proposal.get('source_message_ids', [])))
        aliases[proposal['client_ref']] = item['id']
    for opinion in output.get('support_observations', []):
        target = aliases.get(opinion.get('item_id'), opinion.get('item_id'))
        item = next((i for i in task['items'] if i['id'] == target), None)
        author = opinion.get('author_id')
        if item is None or not author:
            continue
        for field, stance in (('supporter_ids', 'support'), ('opponent_ids', 'oppose')):
            voters = set(item.get(field, [])) - {author}
            if opinion['stance'] == stance:
                voters.add(author)
            item[field] = sorted(voters)
        threshold = len(task['members']) // 2 + 1
        item['support_threshold'] = threshold
        item['state'] = 'supported' if len(item['supporter_ids']) >= threshold else 'mentioned'
    # New constraints stay in result proposals until Backend assigns real IDs.
    # hard_proposals_pending blocks readiness without changing canonical inputs.
    effect = (task.get('user_selection') or {}).get('effect', {})
    excluded = effect.get('item_id') if effect.get('kind') == 'drop_visit' else None
    task['_new_item_refs'] = [ref for ref in new_refs if ref != excluded]
    return task


def _current(is_current):
    return is_current is None or bool(is_current())


async def _report(sink, task, step, model, candidates, scores, index, **extra):
    await emit(sink, task, step, 'decision', None, dict(
        goal=task['goal'], candidates=candidates, scores=scores, selected_index=index,
        model_mode=getattr(model, 'mode', 'unknown'), base_versions=task['base_versions'],
        candidate_count=len(candidates), single_candidate=len(candidates) == 1, **extra))


_UNPREPARED = object()


def _apply_historical_cancellation(order, saved, requests, request, control):
    # Acknowledgment may have preceded recovery of all eligible earlier
    # requests. Evaluate the batch as a whole before retiring any one target.
    scope = dict(_request_source_order=order, recent_messages=[],
                 _cancel_scopes=[r for r in requests if r.get('operation') == 'request'])
    names = control.get('target_names', [])
    options = cancellation_options(scope, control['owner_id'], names, control['source_message_id'])
    if request['request_id'] not in options:
        return False
    active = next((r for r in saved if r['request_id'] == control['request_id']), None)
    if control['status'] == 'completed':
        if not names and control.get('cancelled_request_ids'):
            return False  # The generic control already acted on a specific request.
        if len(options) == 1:
            request.update(status='cancelled', pending_refs=[], cancelled_by=control['request_id'])
            return True
        if active is None:
            active = dict(deepcopy(control), status='needs_input', cancelled_request_ids=[])
            active.pop('response', None)
            saved.append(active)
    if active is not None and 'prior_request_ids' in active:
        active['prior_request_ids'] = list(dict.fromkeys(active['prior_request_ids'] + options))
    return False


def reconcile_request_order(task, saved, requests):
    """Bind a recovered source to later controls already reflected in room state."""
    order = task.get('_request_source_order')
    if not order:
        return superseded_requests(saved, requests)
    retired = {}
    history = task.get('request_history', [])
    for request in requests:
        position = order[request['source_message_id']]
        earlier = [r for r in saved if order.get(r['source_message_id'], position) < position]
        for old in superseded_requests(earlier, [request]):
            retired[old['request_id']] = old
        if request.get('operation') != 'request':
            continue
        later = sorted((r for r in history if r['owner_id'] == request['owner_id']
                        and order.get(r['source_message_id'], -1) > position),
                       key=lambda r: order[r['source_message_id']])
        for control in later:
            if control.get('operation') == 'cancel':
                if _apply_historical_cancellation(order, saved, requests, request, control):
                    break
            elif control['status'] in ('pending', 'resolved', 'completed'):
                replacements = superseded_requests([request], [dict(control, status='resolved')])
                if replacements:
                    request.update(replacements[0])
                    break
    return list(retired.values())


async def run_judged_agent(task, model, tools, emit_trace, auxiliary, is_current=None, max_rounds=6, *,
                           prepared=_UNPREPARED):
    from ai.auxiliary import ground_auxiliary, prepare_auxiliary

    task, selection_questions = apply_selection(build_context(task, []))
    grounded = None
    if prepared is not _UNPREPARED:
        grounded = ground_auxiliary(dict(task, _selection_only=bool(selection_questions)), prepared)
    result = empty_result(task)
    result['pending_item_ids'] = list(task.get('pending_item_ids', []))
    if selection_questions:
        result['questions'] = valid_questions(task, selection_questions)
        result['decision_report'] = dict(status='held', reason='selection_needs_input')
        return result
    cancellation_scopes = task.get('_cancel_scopes', [])
    saved = [deepcopy(r) for r in task.get('pending_requests', []) if r.get('status') not in TERMINAL]
    if task.get('goal') == 'manual_replan':
        for r in saved:
            if r.get('status') == 'failed' or r.get('failed_targets'):
                r.update(status='pending', failed_targets=[])
                r.pop('error_code', None)
    if (saved or task.get('pending_item_ids')) and not task['recent_messages']:
        output = dict(item_proposals=[], constraint_proposals=[], support_observations=[], questions=[],
            analysis=dict(requests=saved, summary='미처리 장소 조회를 계속합니다.'),
            extraction_report=dict(status='ok', issue_codes=[], attempts=0, backend='saved-request-state'))
        if prepared is _UNPREPARED:
            retry_ids = {r['source_message_id'] for r in saved if r.get('status') == 'needs_context'}
            history = task.get('conversation_context', [])
            originals = [m for m in history if m['id'] in retry_ids]
            recovered = await prepare_auxiliary(dict(task, recent_messages=originals,
                conversation_context=[m for m in history if m['id'] not in retry_ids]), auxiliary) if originals else None
        else:
            originals = prepared['source_messages'] if prepared['source_mode'] == 'saved_context_retry' else []
            recovered = grounded if originals else None
        if recovered is not None:
            refreshed = {r['request_id']: r for r in recovered['analysis'].get('requests', [])}
            output['analysis']['requests'] = [refreshed.get(r['request_id'], r) if r.get('status') == 'needs_context'
                                              else r for r in saved]
            output['extraction_report'] = recovered['extraction_report']
        for request in output['analysis']['requests']:
            if request.get('status') == 'needs_context' and request['source_message_id'] not in {m['id'] for m in originals}:
                request['status'] = 'needs_input'
    else:
        output = await prepare_auxiliary(task, auxiliary) if grounded is None else grounded
    analysis = output.pop('analysis', {})
    # Fresh user work owns this round. Saved work resumes only without a new
    # message; explicit same-owner corrections retire its previous scope.
    retired = reconcile_request_order(task, saved, analysis.get('requests', [])) if task['recent_messages'] else []
    result.update(output)
    # Backend replaces its open-question list with this result. Carry existing
    # unresolved questions as state, separately from the newly selected action.
    result['questions'] = deepcopy([q for q in task['questions'] if q.get('status') == 'open'])
    await _report(emit_trace, task, 0, model, [], [], None,
                  extraction_mode='external-structured', extraction_report=result['extraction_report'])
    if result['extraction_report']['status'] == 'failed':
        return result
    current_requests = deepcopy(analysis.get('requests', []))
    known_ids = {r['request_id'] for r in current_requests}
    current_requests.extend(deepcopy(r) for r in saved if r.get('operation')=='cancel' and r['request_id'] not in known_ids)
    legacy_refs = {ref for r in saved if r.get('intent')=='place_details' and not r.get('requested_fields')
                   for ref in r.get('target_refs', [])}
    names_by_ref = {p['place_ref']: p['name'] for p in observed_places(task, legacy_refs)}
    for request in current_requests:
        request.setdefault('completed_refs', [])
        request.setdefault('completed_target_names', [])
        if request.get('intent') == 'place_details' and not request.get('requested_fields'):
            for ref in request['completed_refs']:
                name = names_by_ref.get(ref)
                if name in request.get('target_names', []) and name not in request['completed_target_names']:
                    request['completed_target_names'].append(name)
        request.setdefault('pending_refs', [ref for ref in request.get('target_refs', [])
                                           if ref not in request['completed_refs']])
    analysis['requests'] = current_requests
    task['_active_requests'] = current_requests
    if current_requests or retired:
        result['request_states'] = current_requests + retired
    task = preview_proposals(task, result)
    result['pending_item_ids'] = list(task['_new_item_refs'])
    if task.get('_defer_execution'):
        if not _current(is_current):
            stale = empty_result(task)
            stale.update(last_processed_message_id=None,
                         decision_report=dict(status='stale', reason='request_changed'))
            return stale
        result['decision_report'] = dict(status='held', reason='newer_messages_pending')
        return result
    # Calculation arguments do not capture every room setting (e.g. day end).
    # Recompute them for this run; newly executed calculations still deduplicate.
    task['observations'] = [o for o in task['observations']
                            if o['tool_name'] not in ('build_itinerary', 'calculate_costs')]
    failed_calls, handled_responses = set(), set()
    chosen_calculations = {}
    persisted_failures = set() if task.get('goal')=='manual_replan' else {
        call_key(failure) for failure in task.get('tool_failures', [])}
    new_request_ids = {r['request_id'] for r in current_requests
                       if r.get('source_message_id') in {m['id'] for m in task['recent_messages']}}
    for step in range(1, max_rounds + 1):
        if not _current(is_current):
            result['decision_report'] = dict(status='stale', reason='request_changed')
            await _report(emit_trace, task, step, model, [], [], None, termination='stale_request')
            break
        if hasattr(tools, 'restore'):
            tools.restore(task)
        analysis['requests'] = [r for r in current_requests if r.get('status') not in TERMINAL | {'failed'}]
        task['_active_requests'] = current_requests
        # Saved requests and explicit question answers remain authoritative when
        # the source message has left the bounded conversation window.
        known_requests = {r['request_id']:r for r in cancellation_scopes + saved + current_requests + retired}
        task['pending_requests'] = deepcopy(list(known_requests.values()))
        task['_cancel_scopes'] = list(known_requests.values())
        task['_blocked_request_ids'] = set()
        for control in analysis['requests']:
            if control.get('operation') == 'cancel':
                options = cancellation_options(task, control['owner_id'], control.get('target_names', []), control['source_message_id'])
                task['_blocked_request_ids'].update(options)
        if current_requests and not analysis['requests']:
            result['completion'] = 'needs_input' if any(r.get('status')=='failed' for r in current_requests) else 'done'
            break
        prepared = build_decision_candidates(task, analysis)
        offered = prepared['candidates'] + prepared.get('deferred_candidates', [])
        candidates = []
        for candidate in offered:
            if candidate.get('action') == 'tool':
                key = call_key(candidate)
                fresh_scope = bool(set(candidate.get('request_ids', [])) & new_request_ids)
                if key in failed_calls or key in persisted_failures and not fresh_scope:
                    continue
            elif candidate.get('candidate_id') in handled_responses:
                continue
            if candidate not in candidates:
                candidates.append(candidate)
        limited, tool_count = [], 0
        for candidate in candidates:
            if candidate.get('action')=='tool':
                if tool_count >= 3:
                    continue
                tool_count += 1
            if len(limited) < 4:
                limited.append(candidate)
        candidates = limited
        result['candidates'] = candidates
        if not candidates:
            result['decision_report'] = dict(status='held', branch=prepared['branch'], reason='no_actual_candidates')
            if analysis.get('noop') and not result['questions'] and result['extraction_report']['status'] == 'ok':
                result['completion'] = 'done'
            if analysis.get('requests'):
                result['completion'] = 'done' if all(r['status'] in TERMINAL for r in result['request_states']) else 'needs_input'
            await _report(emit_trace, task, step, model, [], [], None, branch=prepared['branch'],
                          request_states=result.get('request_states', []), termination='no_actual_candidates')
            break
        context = compact_decision_context(task, analysis, candidates)
        started = perf_counter()
        try:
            scores = await asyncio.to_thread(model.score_candidates, context, deepcopy(candidates))
            scores = [float(score) for score in scores]
            if len(scores) != len(candidates) or not all(math.isfinite(score) for score in scores):
                raise ValueError('Invalid judge scores')
            index = max(range(len(scores)), key=scores.__getitem__)
        except (ValueError, TypeError, RuntimeError, OSError, KeyError) as error:
            result['decision_report'] = dict(status='failed', reason=type(error).__name__)
            await _report(emit_trace, task, step, model, candidates, [], None,
                          branch=prepared['branch'], termination='judge_failed', error_code=type(error).__name__)
            break
        selected = deepcopy(candidates[index])
        await _report(emit_trace, task, step, model, candidates, scores, index,
                      branch=prepared['branch'], duration_ms=round((perf_counter() - started) * 1000, 3),
                      input_chars=len(json.dumps(context, ensure_ascii=False)),
                      request_states=result.get('request_states', []),
                      deferred_candidates=prepared.get('deferred_candidates', []),
                      decision_context=context, selection_origin='qwen_judge' if getattr(model, 'mode', '') == 'local_qwen' else 'fixture_judge')
        result['decision_report'] = dict(status='selected', action=selected['action'],
                                          candidate_id=selected.get('candidate_id'), round=step)
        if not _current(is_current):
            result['decision_report'] = dict(status='stale', reason='request_changed')
            break
        if selected['action'] == 'ask':
            result['questions'] = valid_questions(task, result['questions'] + [selected['question']], result['item_proposals'])
            ids = set(selected.get('request_ids', []))
            for request in current_requests:
                if request['request_id'] in ids or selected['question'].get('target_ref')==request['request_id']:
                    request['status'] = 'needs_input'
            break
        if selected['action'] in ('unsupported', 'direct'):
            result['response'] = selected['reason']
            handled_responses.add(selected.get('candidate_id'))
            complete_candidate(current_requests, selected)
            for rid in selected.get('cancelled_request_ids', []):
                original = known_requests[rid]
                control = next(r for r in current_requests if r['request_id'] in selected['request_ids']
                               and r.get('operation')=='cancel' and cancellation_options(task, r['owner_id'],
                                   r.get('target_names', []), r['source_message_id']) == [rid])
                original.update(status='cancelled', pending_refs=[], cancelled_by=control['request_id'])
                if original not in current_requests:
                    retired.append(original)
            if not current_requests:
                result['completion'] = 'unsupported' if selected['action'] == 'unsupported' else 'done'
                break
            continue
        try:
            # Validate the exact scored value again at the execution boundary.
            validate_arguments(selected['tool_name'], selected['arguments'], build_tool_context(task))
            observation = await execute_selected(task, selected, tools, emit_trace, step,
                origin='qwen_judge' if getattr(model, 'mode', '') == 'local_qwen' else 'fixture_judge',
                is_current=is_current)
        except StaleExecution:
            result['decision_report'] = dict(status='stale', reason='request_changed_before_dispatch')
            break
        except (ValueError, TypeError, KeyError, RuntimeError, OSError, HTTPError) as error:
            result['decision_report'] = dict(status='failed', reason='tool_failed', error_code=type(error).__name__)
            await emit(emit_trace, task, step, 'tool_result', f"{task['run_id']}:{step}",
                       dict(tool_name=selected['tool_name'], failed=True, error_code=type(error).__name__))
            failure = dict(tool_name=selected['tool_name'], arguments=deepcopy(selected['arguments']),
                           error_code=type(error).__name__, request_ids=selected.get('request_ids', []))
            result.setdefault('tool_failures', []).append(failure)
            failed_calls.add(call_key(selected))
            fail_candidate(current_requests, selected, type(error).__name__)
            continue
        if not _current(is_current):
            result['decision_report'] = dict(status='stale', reason='request_changed_after_tool')
            break
        result['observations'].append(observation)
        task['observations'].append(deepcopy(observation))
        if current_requests:
            complete_candidate(current_requests, selected, observation)
            if selected['tool_name'] in ('build_itinerary','calculate_costs'):
                chosen_calculations[selected['tool_name']] = selected['arguments']
            elif chosen_calculations:
                context = build_tool_context(task)
                for request in current_requests:
                    tool = request.get('result_tool')
                    if tool not in chosen_calculations or request['status']!='completed':
                        continue
                    current = itinerary_arguments(context) if tool=='build_itinerary' else build_cost_inputs(context)[0]
                    if not same_arguments(chosen_calculations[tool], current):
                        request.update(status='pending', result_refs=[])
                        request.pop('response', None)
                        request.pop('result_tool')
            result['request_states'] = current_requests + retired
            if all(r['status'] in TERMINAL for r in result['request_states']):
                result['completion'] = 'done'
                await _report(emit_trace, task, step, model, [], [], None,
                              request_states=result['request_states'], termination='requests_completed')
                break
    else:
        result['decision_report'].update(status='held', reason='round_limit', round=max_rounds)
    if current_requests or retired:
        result['request_states'] = current_requests + retired
    assembly_task = dict(task, observations=[o for o in task['observations'] if o not in result['observations']])
    if result.get('decision_report', {}).get('status') != 'stale':
        assemble_result(assembly_task, result)
        represented = set((result.get('plan_draft') or {}).get('selected_item_ids', []))
        result['pending_item_ids'] = [ref for ref in result['pending_item_ids'] if ref not in represented]
    return result
