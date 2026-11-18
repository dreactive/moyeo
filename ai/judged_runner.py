"""External facts -> actual calls -> supplied Qwen judge -> registered execution."""
import asyncio
from copy import deepcopy
import math
import json
from time import perf_counter
from httpx import HTTPError

from ai.context import build_context
from ai.decision_candidates import build_decision_candidates, compact_decision_context
from ai.outcome import assemble_result
from ai.questions import valid_questions
from ai.result import empty_result
from ai.runner import execute_selected
from ai.selection import apply_selection
from ai.tools.context import build_tool_context
from ai.tools.validation import validate_arguments
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


def request_states(requests, observations):
    """Track referenced queries without replaying historical user preferences."""
    observed = {o.get('arguments', {}).get('place_ref') for o in observations
                if o.get('tool_name') == 'get_place_details'
                and o.get('result', {}).get('place', {}).get('id') == o.get('arguments', {}).get('place_ref')}
    states = []
    for request in requests:
        value = deepcopy(request)
        targets = value.get('target_refs', [])
        completed = observed | set(value.get('completed_refs', []))
        value['completed_refs'] = [ref for ref in targets if ref in completed]
        value['pending_refs'] = [ref for ref in targets if ref not in completed]
        if value.get('status') in ('superseded', 'cancelled'):
            value['pending_refs'] = []
        if value.get('status') in ('resolved', 'pending', 'completed'):
            value['status'] = 'pending' if value['pending_refs'] else 'completed' if targets else 'needs_input'
        states.append(value)
    return states


def superseded_requests(saved, current):
    retired = []
    for previous in saved:
        replacement = next((r for r in current if r.get('owner_id') == previous.get('owner_id')
            and r.get('intent') == previous.get('intent') and r.get('status') == 'resolved'
            and (set(r.get('excluded_refs', [])) & set(previous.get('target_refs', []))
                 or previous.get('status') in ('needs_input', 'needs_context'))), None)
        if replacement:
            retired.append(dict(deepcopy(previous), status='superseded', pending_refs=[],
                                superseded_by=replacement['request_id']))
    return retired


async def _report(sink, task, step, model, candidates, scores, index, **extra):
    await emit(sink, task, step, 'decision', None, dict(
        goal=task['goal'], candidates=candidates, scores=scores, selected_index=index,
        model_mode=getattr(model, 'mode', 'unknown'), base_versions=task['base_versions'],
        candidate_count=len(candidates), single_candidate=len(candidates) == 1, **extra))


async def run_judged_agent(task, model, tools, emit_trace, auxiliary, is_current=None, max_rounds=6):
    from ai.auxiliary import prepare_auxiliary

    task, selection_questions = apply_selection(build_context(task, []))
    result = empty_result(task)
    result['pending_item_ids'] = list(task.get('pending_item_ids', []))
    if selection_questions:
        result['questions'] = valid_questions(task, selection_questions)
        result['decision_report'] = dict(status='held', reason='selection_needs_input')
        return result
    saved = [dict(r, status='resolved' if r.get('target_refs') else r.get('status'))
             for r in task.get('pending_requests', []) if r.get('status') not in ('completed', 'superseded', 'cancelled')]
    if saved and not task['recent_messages']:
        output = dict(item_proposals=[], constraint_proposals=[], support_observations=[], questions=[],
            analysis=dict(requests=saved, summary='미처리 장소 조회를 계속합니다.'),
            extraction_report=dict(status='ok', issue_codes=[], attempts=0, backend='saved-request-state'))
    else:
        output = await prepare_auxiliary(task, auxiliary)
    analysis = output.pop('analysis', {})
    # Fresh user work owns this round. Saved work resumes only without a new
    # message; explicit same-owner corrections retire its previous scope.
    retired = superseded_requests(saved, analysis.get('requests', [])) if task['recent_messages'] else []
    result.update(output)
    # Backend replaces its open-question list with this result. Carry existing
    # unresolved questions as state, separately from the newly selected action.
    result['questions'] = deepcopy([q for q in task['questions'] if q.get('status') == 'open'])
    await _report(emit_trace, task, 0, model, [], [], None,
                  extraction_mode='external-structured', extraction_report=result['extraction_report'])
    if result['extraction_report']['status'] == 'failed':
        return result
    if analysis.get('requests') or retired:
        result['request_states'] = request_states(analysis.get('requests', []), task['observations']) + retired
    task = preview_proposals(task, result)
    result['pending_item_ids'] = list(task['_new_item_refs'])
    # Calculation arguments do not capture every room setting (e.g. day end).
    # Recompute them for this run; newly executed calculations still deduplicate.
    task['observations'] = [o for o in task['observations']
                            if o['tool_name'] not in ('build_itinerary', 'calculate_costs')]
    for step in range(1, max_rounds + 1):
        if not _current(is_current):
            result['decision_report'] = dict(status='stale', reason='request_changed')
            await _report(emit_trace, task, step, model, [], [], None, termination='stale_request')
            break
        if hasattr(tools, 'restore'):
            tools.restore(task)
        prepared = build_decision_candidates(task, analysis)
        candidates = prepared['candidates']
        result['candidates'] = candidates
        if not candidates:
            result['decision_report'] = dict(status='held', branch=prepared['branch'], reason='no_actual_candidates')
            if analysis.get('noop') and not result['questions'] and result['extraction_report']['status'] == 'ok':
                result['completion'] = 'done'
            if analysis.get('requests'):
                result['completion'] = 'done' if all(r['status'] in ('completed', 'superseded') for r in result['request_states']) else 'needs_input'
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
            break
        if selected['action'] in ('unsupported', 'direct'):
            result['response'] = selected['reason']
            result['completion'] = 'unsupported' if selected['action'] == 'unsupported' else 'done'
            break
        try:
            # Validate the exact scored value again at the execution boundary.
            validate_arguments(selected['tool_name'], selected['arguments'], build_tool_context(task))
            observation = await execute_selected(task, selected, tools, emit_trace, step,
                origin='qwen_judge' if getattr(model, 'mode', '') == 'local_qwen' else 'fixture_judge')
        except (ValueError, TypeError, KeyError, RuntimeError, OSError, HTTPError) as error:
            result['decision_report'] = dict(status='failed', reason='tool_failed', error_code=type(error).__name__)
            await emit(emit_trace, task, step, 'tool_result', f"{task['run_id']}:{step}",
                       dict(tool_name=selected['tool_name'], failed=True, error_code=type(error).__name__))
            break
        if not _current(is_current):
            result['decision_report'] = dict(status='stale', reason='request_changed_after_tool')
            break
        result['observations'].append(observation)
        task['observations'].append(deepcopy(observation))
        if analysis.get('requests'):
            result['request_states'] = request_states(analysis['requests'], task['observations']) + retired
            if all(r['status'] in ('completed', 'superseded') for r in result['request_states']):
                result['completion'] = 'done'
                await _report(emit_trace, task, step, model, [], [], None,
                              request_states=result['request_states'], termination='requests_completed')
                break
        # Assemble only newly executed calculations against the same grounded state.
        assembly_task = dict(task, observations=[o for o in task['observations'] if o not in result['observations']])
        calculated = {o['tool_name'] for o in result['observations']}
        if {'build_itinerary', 'calculate_costs'} <= calculated and assemble_result(assembly_task, result):
            represented = set((result.get('plan_draft') or {}).get('selected_item_ids', []))
            result['pending_item_ids'] = [ref for ref in result['pending_item_ids'] if ref not in represented]
            break
    else:
        result['decision_report'].update(status='held', reason='round_limit', round=max_rounds)
    return result
