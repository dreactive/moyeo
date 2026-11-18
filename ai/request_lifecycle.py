"""Derive request progress from actual observations, preserving unknown facts."""
from copy import deepcopy
import json
from ai.auxiliary_requests import CALCULATION_TOOLS


TERMINAL = {'completed', 'superseded', 'cancelled', 'unsupported'}


def _name(value):
    return ''.join(value.split()).casefold()


def call_key(candidate):
    return json.dumps([candidate.get('tool_name'), candidate.get('arguments')],
                      sort_keys=True, ensure_ascii=False, allow_nan=False)


def detail_response(detail):
    place = detail.get('place', {})
    fields = list(detail.get('missing_fields', []))
    lines = [place.get('name') or '장소', '조회 완료']
    if place.get('address'):
        lines.append(place['address'])
    for menu in detail.get('menus', []):
        price = menu.get('price_krw')
        if price is not None:
            lines.append(f"{menu.get('name', '이용료')} {price:,}원")
    if not detail.get('menus') and 'price' not in fields:
        fields.append('price')
    hours = detail.get('opening_hours') or {}
    raw_hours = str(hours.get('raw_text') or '').strip()
    hours_text = raw_hours if raw_hours not in ('', '[]', '{}', 'null') else hours.get('intervals')
    if hours_text and 'opening_hours' not in fields:
        lines.append('영업시간 ' + str(hours_text))
    elif 'opening_hours' not in fields:
        fields.append('opening_hours')
    if detail.get('match_status') in ('ambiguous', 'unmatched'):
        lines.append('세부정보의 동일 장소 매칭 미확인')
    if fields:
        labels = {'price':'가격', 'opening_hours':'영업시간', 'details':'상세 정보'}
        lines.append('·'.join(labels.get(field, field) for field in fields) + ' 미확인')
    return ' · '.join(lines), fields


def request_states(requests, observations, context=None):
    context = context or {}
    details = {o.get('arguments', {}).get('place_ref'):o['result'] for o in observations
               if o.get('tool_name') == 'get_place_details'
               and o.get('result', {}).get('place', {}).get('id') == o.get('arguments', {}).get('place_ref')}
    places = {p['id']:p for o in observations if o.get('tool_name')=='search_places'
              for p in o.get('result', {}).get('places', [])}
    places.update({ref:d['place'] for ref,d in details.items()})
    states = []
    for request in requests:
        value = deepcopy(request)
        if value.get('status') in TERMINAL | {'failed'}:
            if value.get('status') in TERMINAL:
                value['pending_refs'] = []
            states.append(value)
            continue
        if value.get('operation') == 'cancel' or value.get('intent') == 'service_request':
            states.append(value)
            continue
        fields = value.get('requested_fields') or (['details'] if value.get('intent')=='place_details' else ['location'])
        needs_details = any(field != 'location' for field in fields)
        refs = list(value.get('target_refs', []))
        excluded = set(value.get('excluded_refs', []))
        unresolved, names_done, responses = [], [], []
        for name in value.get('target_names', []):
            known = [ref for ref in refs if _name(places.get(ref, {}).get('name', ''))==_name(name)]
            search = next((o for o in reversed(observations) if o.get('tool_name')=='search_places'
                           and _name(o.get('arguments', {}).get('query', ''))==_name(name)
                           and (not context.get('config', {}).get('region') or
                                o.get('arguments', {}).get('region')==context['config']['region'])), None)
            found = [] if search is None else [p for p in search['result'].get('places', []) if p['id'] not in excluded]
            exact = [p for p in found if _name(p['name'])==_name(name)]
            unique = exact if exact else found
            if not known and len(unique)==1:
                refs.append(unique[0]['id'])
                known = [unique[0]['id']]
            if not needs_details and (known or search is not None):
                names_done.append(name)
                responses += [p['name'] + (' · '+p['address'] if p.get('address') else '') for p in found]
                if not found and not known:
                    responses.append(name+' · 검색 결과 없음')
            elif not known:
                if search is not None and not found:
                    names_done.append(name)
                    responses.append(name+' · 검색 결과 없음')
                else:
                    unresolved.append(name)
        refs = list(dict.fromkeys(ref for ref in refs if ref not in excluded))
        completed = set(value.get('completed_refs', []))
        completed.update(ref for ref in refs if ref in (details if needs_details else places))
        value.update(target_refs=refs, completed_refs=[ref for ref in refs if ref in completed],
                     pending_refs=[ref for ref in refs if ref not in completed],
                     unresolved_target_names=unresolved)
        gaps = []
        for ref in value['completed_refs']:
            if needs_details and ref in details:
                response, missing = detail_response(details[ref])
                responses.append(response)
                gaps.extend(missing)
            elif not responses and ref in places:
                p = places[ref]
                responses.append(p.get('name', ref)+(' · '+p['address'] if p.get('address') else ''))
        value['missing_fields'] = list(dict.fromkeys(gaps))
        value['result_refs'] = list(value['completed_refs'])
        if responses:
            value['response'] = '\n'.join(dict.fromkeys(responses))
        if refs or names_done:
            value['status'] = 'pending' if value['pending_refs'] or unresolved else 'completed'
        elif value.get('status') in ('resolved', 'pending'):
            value['status'] = 'pending' if unresolved else 'needs_input'
        states.append(value)
    return states


def superseded_requests(saved, current):
    retired = []
    for previous in saved:
        replacement = next((r for r in current if r.get('owner_id') == previous.get('owner_id')
            and r.get('operation', 'request') == 'request' and r.get('intent') == previous.get('intent')
            and r.get('status') in ('resolved', 'pending')
            and (set(r.get('excluded_refs', [])) & set(previous.get('target_refs', []))
                 or {_name(n) for n in r.get('excluded_names', [])}
                 & {_name(n) for n in previous.get('target_names', [])})), None)
        if replacement:
            retired.append(dict(deepcopy(previous), status='superseded', pending_refs=[],
                                superseded_by=replacement['request_id']))
    return retired


def update_request_status(request):
    finished = {_name(n) for n in request.get('completed_target_names', [])}
    failed = {_name(f['target_name']) for f in request.get('failed_targets', []) if f.get('target_name')}
    remaining = {_name(n) for n in request.get('target_names', [])} - finished
    if request.get('failed_targets') and not remaining - failed:
        request['status'] = 'failed'
    else:
        request['status'] = 'pending' if remaining or request.get('pending_refs') else 'completed'


def fail_candidate(requests, selected, error_code):
    for request in requests:
        for target in selected.get('request_targets', []):
            if target['request_id'] != request['request_id']:
                continue
            reason = dict(target_name=target['target_name'], target_ref=target['target_ref'],
                          tool_name=selected['tool_name'], error_code=error_code)
            request.setdefault('failed_targets', []).append(reason)
            request['error_code'] = error_code
            update_request_status(request)
            if not target['target_name']:
                request['status'] = 'failed'


def complete_candidate(requests, candidate, observation=None):
    """Advance only work actually selected by Qwen, not every cached target."""
    ids = set(candidate.get('request_ids', []))
    targets = candidate.get('request_targets', [])
    for request in requests:
        if request['request_id'] not in ids:
            continue
        if candidate['action']=='unsupported' or request.get('operation')=='cancel':
            request.update(status='unsupported' if candidate['action']=='unsupported' else 'completed',
                           response=candidate['reason'], pending_refs=[], result_refs=candidate.get('result_refs', []))
            continue
        if request.get('intent') in CALCULATION_TOOLS:
            tool = CALCULATION_TOOLS[request['intent']]
            if observation and candidate.get('tool_name') == tool:
                value = observation['result']
                if tool == 'calculate_costs':
                    response = f"확인된 비용 {value['known_total_krw']:,}원 · 미확인 항목 {value['unknown_line_count']}개"
                else:
                    visits = sum(len(day['visits']) for day in value['days'])
                    response = f"일정에 배치한 방문 {visits}곳 · 미배치 {len(value.get('unplaced_items', []))}곳"
                request.update(status='completed', response=response, pending_refs=[],
                               result_refs=observation.get('source_refs', []), result_tool=tool)
            elif candidate['action']=='direct':
                request.update(status='needs_input', response=candidate['reason'])
            continue
        if request.get('intent')=='route_lookup' and candidate['action']=='direct':
            request.update(status='completed', response=candidate['reason'], pending_refs=[],
                           completed_target_names=list(request.get('target_names', [])),
                           completed_refs=list(request.get('target_refs', [])),
                           result_refs=candidate.get('result_refs', []))
            continue
        rows = [target for target in targets if target['request_id']==request['request_id']]
        completed_names = list(request.get('completed_target_names', []))
        completed_refs = list(request.get('completed_refs', []))
        result_refs = list(request.get('result_refs', []))
        refs = list(request.get('target_refs', []))
        responses = []
        if candidate['action']=='direct':
            responses.append(candidate['reason'])
            result_refs += candidate.get('result_refs', [])
            for row in rows:
                if row.get('target_name'):
                    completed_names.append(row['target_name'])
                if row.get('target_ref'):
                    completed_refs.append(row['target_ref'])
        elif observation and candidate.get('tool_name')=='search_places':
            found = observation['result'].get('places', [])
            fields = request.get('requested_fields') or (['details'] if request.get('intent')=='place_details' else ['location'])
            for row in rows:
                name = row.get('target_name') or candidate['arguments']['query']
                exact = [p for p in found if _name(p['name'])==_name(name)]
                if len(exact)==1:
                    refs.append(exact[0]['id'])
                if request.get('intent')!='route_lookup' and (fields==['location'] or not found):
                    completed_names.append(name)
                    completed_refs += [p['id'] for p in found]
                    result_refs += [p['id'] for p in found]
                    responses += [p['name']+(' · '+p['address'] if p.get('address') else '') for p in found]
                    if not found:
                        responses.append(name+' · 검색 결과 없음')
                        request['missing_fields'] = list(dict.fromkeys(request.get('missing_fields', [])+['location']))
        elif observation and candidate.get('tool_name')=='get_place_details':
            ref = candidate['arguments']['place_ref']
            refs.append(ref)
            completed_refs.append(ref)
            result_refs.append(ref)
            for row in rows:
                if row.get('target_name'):
                    completed_names.append(row['target_name'])
            response, gaps = detail_response(observation['result'])
            responses.append(response)
            request['missing_fields'] = list(dict.fromkeys(request.get('missing_fields', [])+gaps))
        elif observation and candidate.get('tool_name')=='get_car_route':
            route=observation['result']
            completed_refs += [candidate['arguments']['from_ref'],candidate['arguments']['to_ref']]
            completed_names += request.get('target_names', [])
            result_refs += [route['evidence_id']]
            responses.append(f"자동차 경로 조회 완료 · {route['distance_m']:,}m · {route['duration_seconds']:,}초")
        request['target_refs'] = list(dict.fromkeys(refs))
        request['completed_refs'] = list(dict.fromkeys(completed_refs))
        request['completed_target_names'] = list(dict.fromkeys(completed_names))
        request['result_refs'] = list(dict.fromkeys(result_refs))
        request['pending_refs'] = [ref for ref in request['target_refs'] if ref not in request['completed_refs']]
        names_left = [name for name in request.get('target_names', [])
                      if _name(name) not in {_name(n) for n in completed_names}]
        request['unresolved_target_names'] = [name for name in request.get('unresolved_target_names', []) if name in names_left]
        update_request_status(request)
        if responses:
            previous = request.get('response', '')
            request['response'] = '\n'.join(dict.fromkeys(([previous] if previous else [])+responses))
