import test from 'node:test';
import assert from 'node:assert/strict';
import fixture from '../fixtures/room-snapshot.json' with {type:'json'};
import place from '../fixtures/place-details.json' with {type:'json'};
import {renderAgentBanner} from '../src/workspace-view.js';
import {renderRoutePanel} from '../src/route-view.js';
import {renderPlace} from '../src/place.js';
import {renderCost} from '../src/cost.js';
import {renderItems,renderQuestions,readDecisionValue} from '../src/items.js';
import {applySnapshot,getSelectedPlace,setSelectedPlace,setUser} from '../src/state.js';

function setup() {
  const output = {};
  globalThis.document = {getElementById:id => output[id] ??= {}};
  const room = structuredClone(fixture);
  return {output,room};
}

test('visits and place details show partial support and opposition on the current item version', () => {
  const {output,room} = setup();
  room.items[0].supporter_ids = ['u1','u2'];
  room.items[0].opponent_ids = ['u3'];
  applySnapshot(room);
  renderItems(room);
  renderRoutePanel(room,'2026-11-21');
  renderPlace(place);
  for (const id of ['items','route-summary','place']) {
    assert.match(output[id].innerHTML,/언급됨[^]*일부 지지 2\/4 · 반대 1명/);
  }
});

test('a frozen visit does not inherit agreement for a changed item version', () => {
  const {output,room} = setup();
  room.review_plan = structuredClone(room.current_plan);
  room.confirmed_plan = structuredClone(room.review_plan);
  room.items[0].item_version++;
  room.items[0].state = 'supported';
  room.items[0].supporter_ids = ['u1','u2','u3'];
  renderRoutePanel(room,'2026-11-21');
  const first = output['route-summary'].innerHTML.split('data-place="fixture:place-b"')[0];
  assert.match(first,/표시 항목의 동의 기록 미확인/);
  assert.doesNotMatch(first,/과반 지지|지지 3\/4|agreement-badge confirmed/);
});

test('a same-target confirmed visit displays a check and the confirmed plan revision', () => {
  const {output,room} = setup();
  room.confirmed_plan = structuredClone(room.current_plan);
  renderRoutePanel(room,'2026-11-21');
  assert.match(output['route-summary'].innerHTML,/여행안 v1 · 공식 확정/);
  assert.match(output['route-summary'].innerHTML,/agreement-badge confirmed[^>]*>✓ 확정 v1/);
});

test('request progress reports completed and pending targets independently and links to their sources', () => {
  const {output,room} = setup();
  room.agent_requests = [
    {request_id:'r1',intent:'place_lookup',owner_id:'u1',source_message_id:'m0',status:'pending',
      evidence:{quote:'식당과 공원 확인해줘'},completed_refs:['fixture:place-a'],
      pending_refs:['fixture:place-b'],result_refs:['fixture:place-a'],response:'식당의 주소를 찾았어요.'},
    {request_id:'r2',intent:'place_lookup',owner_id:'u1',source_message_id:'m0',status:'cancelled',
      evidence:{quote:'공원은 취소'},response:'공원 조회 요청을 취소했어요.'},
    {request_id:'r3',intent:'service_request',status:'unsupported',response:'지금 예약할 수 없어요.'},
    {request_id:'r4',intent:'place_lookup',status:'failed',error_code:'provider_error'}
  ];
  renderAgentBanner(room);
  const banner = output.agent.innerHTML;
  assert.match(banner,/조회 대기[^]*완료 1곳[^]*대기 1곳/);
  assert.match(banner,/data-place="fixture:place-a">가상 A식당/);
  assert.match(banner,/data-message="m0"[^]*2026-11-18T10:00:00\+09:00/);
  assert.match(banner,/식당의 주소를 찾았어요[.]/);
  assert.match(banner,/취소됨[^]*공원 조회 요청을 취소했어요[.]/);
  assert.match(banner,/지원하지 않는 요청[^]*지금 예약할 수 없어요[.]/);
  assert.match(banner,/조회 실패[^]*provider_error/);
});

test('the review stays visible while a separate run shows its unplaced items and data gaps', () => {
  const {output,room} = setup();
  room.review_plan = structuredClone(room.current_plan);
  room.current_plan.plan_revision = room.current_plan.confirmation_target.plan_revision = room.versions.plan_revision = 2;
  room.agent_results = {run_id:'run-latest',versions:{...room.versions},build_itinerary:{
    days:[],questions:[],conflicts:[],
    unplaced_items:[{item_id:'item-b',place_ref:'fixture:place-b',reason:'missing_route'}],
    missing_observations:[{field:'opening_hours',place_ref:'fixture:place-a'}]
  }};
  renderRoutePanel(room,'2026-11-21');
  const route = output['route-summary'].innerHTML;
  assert.match(route,/여행안 v1 · 검토 중[^]*11:30–12:30/);
  assert.match(route,/부분 일정[^]*run-latest[^]*미배치[^]*가상 B공원[^]*경로 미조회/);
  assert.match(route,/관측 미확인[^]*가상 A식당[^]*영업시간/);
});

test('unplaced visits and missing route segments stay visible even when no visit time was available', () => {
  const {output,room} = setup();
  room.current_plan.days = [{date:'2026-11-21',visits:[],route_legs:[]}];
  room.current_plan.unplaced_items = [{item_id:'item-a',place_ref:'fixture:place-a',reason:'missing_route'}];
  renderRoutePanel(room,'2026-11-21');
  assert.match(output['route-summary'].innerHTML,/미배치[^]*data-place="fixture:place-a">가상 A식당[^]*경로 미조회[^]*일부 지지 1\/4/);
});

test('a cost calculation stays unknown when its tool output has missing lines, even with a frozen review', () => {
  const {output,room} = setup();
  room.review_plan = structuredClone(room.current_plan);
  const historical = room.review_plan.cost;
  const result = {...historical,total_krw:null,known_total_krw:99000,unknown_line_count:1};
  room.agent_results = {run_id:'run-cost',versions:room.versions,calculate_costs:result};
  renderCost(historical,'u1',room.members,room);
  assert.match(output.cost.innerHTML,/여행안 v1 · 검토 중[^]*부분 비용 계산[^]*run-cost/);
  assert.match(output.cost.innerHTML,/부분 비용 계산[^]*전체 계획액 <strong>미확인<\/strong>[^]*알려진 소계 99,000원[^]*미확인 1건/);
});

test('partial cost and route output disappear from current panels when any room version changes', () => {
  const {output,room} = setup();
  const {days,cost} = room.current_plan;
  room.agent_results = {run_id:'prior-tool-run',versions:{...room.versions},build_itinerary:{days},calculate_costs:cost};
  room.current_plan = null;
  renderRoutePanel(room,null);
  renderCost(null,'u1',room.members,room);
  assert.match(output['route-summary'].innerHTML,/부분 일정[^]*11:30–12:30/);
  assert.match(output.cost.innerHTML,/부분 비용 계산[^]*방 전체 계획액/);
  for (const key of ['participant_version','constraint_version','evidence_version','plan_revision']) {
    const stale = {...room,versions:{...room.versions,[key]:room.versions[key]+1}};
    renderRoutePanel(stale,null);
    renderCost(null,'u1',room.members,stale);
    renderAgentBanner(stale);
    assert.doesNotMatch(output['route-summary'].innerHTML,/11:30–12:30|agent-itinerary/,key);
    assert.equal(output.cost.innerHTML,'경비 미확인',key);
    assert.match(output.agent.innerHTML,/이전 입력 기준[^]*참가자 v1[^]*조건 v1[^]*관측 v1[^]*여행안 v1/,key);
    assert.doesNotMatch(output.agent.innerHTML,/href="#agent-(?:itinerary|cost)"/,key);
  }
});

test('route evidence and anchor references never open a place details URL', () => {
  const {output,room} = setup();
  room.agent_requests = [{intent:'route_lookup',status:'completed',target_refs:['anchor:origin','fixture:place-a'],completed_refs:['anchor:origin','fixture:place-a'],
    result_refs:['anchor:origin','kakao:route:result-key','fixture:place-a']}];
  renderAgentBanner(room);
  assert.match(output.agent.innerHTML,/<code>anchor:origin<\/code> <code>kakao:route:result-key<\/code>/);
  assert.match(output.agent.innerHTML,/data-place="fixture:place-a"/);
});

test('request result places survive a room refresh without entering the displayed plan', () => {
  const {room} = setup();
  room.agent_requests = [{status:'completed',result_refs:['search-only']}];
  applySnapshot(room);
  setSelectedPlace('search-only');
  applySnapshot(structuredClone(room));
  assert.equal(getSelectedPlace(),'search-only');
});

test('unresolved requested names are visible even before a place ID exists', () => {
  const {output,room} = setup();
  room.agent_requests = [{status:'pending',completed_refs:['fixture:place-a'],pending_refs:[],
    unresolved_target_names:['중앙공원'],missing_fields:['opening_hours']}];
  renderAgentBanner(room);
  assert.match(output.agent.innerHTML,/완료 1곳 · 대기 1곳[^]*대상 미확인 중앙공원[^]*정보 미확인 영업시간/);
});

test('partial request failures identify the failed target and retain completed targets', () => {
  const {output,room} = setup();
  room.agent_requests = [{status:'failed', completed_target_names:['자산공원'], failed_targets:[
    {target_name:'오동도',error_code:'ReadTimeout'}], completed_refs:[], unresolved_target_names:['오동도']}];
  renderAgentBanner(room);
  assert.match(output.agent.innerHTML,/완료 1곳/);
  assert.match(output.agent.innerHTML,/오동도 · 조회 실패 · ReadTimeout/);
});

test('route gaps use the reported endpoints and departure time when visits could not be scheduled', () => {
  const {output,room} = setup();
  room.current_plan.days[0].route_legs = [];
  room.current_plan.days[0].visits = [];
  room.current_plan.unplaced_items = [{item_id:'item-a',place_ref:'fixture:place-a',reason:'missing_route'}];
  room.current_plan.missing_observations = [{field:'route',from_ref:'anchor:origin',to_ref:'fixture:place-a',
    date:'2026-11-21',departure_at:'2026-11-21T09:00:00+09:00'}];
  renderRoutePanel(room,'2026-11-21');
  assert.match(output['route-summary'].innerHTML,/예시 출발지 → 가상 A식당[^]*출발 기준 2026-11-21T09:00:00\+09:00/);
  assert.doesNotMatch(output['route-summary'].innerHTML,/예시 출발지 → 예시 숙소/);
});

test('partial itinerary places survive refresh without becoming members of the review', () => {
  const {room} = setup();
  room.review_plan = structuredClone(room.current_plan);
  room.agent_results = {run_id:'r3',versions:room.versions,build_itinerary:{
    days:[{date:'2026-11-21',visits:[{place_ref:'run-only'}]}]
  }};
  applySnapshot(room);
  setSelectedPlace('run-only');
  applySnapshot(structuredClone(room));
  assert.equal(getSelectedPlace(),'run-only');
});

test('a lookup question lets only its owner choose an observed location or enter place names', () => {
  const {output,room} = setup();
  room.questions = [{id:'target-1',field:'target_places',target_ref:'r1',owner_id:'u1',status:'open',
    text:'어느 장소인가요?',place_choices:[{place_ref:'park-1',name:'중앙공원',address:'동구'}]}];
  setUser({id:'u2'});
  renderQuestions(room);
  assert.doesNotMatch(output.questions.innerHTML,/data-question=/);
  setUser({id:'u1'});
  try {
    renderQuestions(room);
    assert.match(output.questions.innerHTML,/<option value="park-1">중앙공원 · 동구<\/option>/);
    assert.match(output.questions.innerHTML,/name="target_names"/);
    assert.deepEqual(readDecisionValue({dataset:{valueMode:'target-places'},elements:{
      target_names:{value:' 중앙공원, 수목원 '},place_ref:{value:''}
    }}),{target_names:['중앙공원','수목원']});
    assert.deepEqual(readDecisionValue({dataset:{valueMode:'target-places'},elements:{
      target_names:{value:''},place_ref:{value:'park-1'}
    }}),{target_names:[],place_ref:'park-1'});
  } finally {
    setUser(null);
  }
});

test('a region question accepts plain text and trims the submitted region', () => {
  const {output,room} = setup();
  room.questions = [{id:'region',field:'region',target_ref:'config:region',owner_id:null,status:'open',text:'어느 지역인가요?'}];
  renderQuestions(room);
  assert.match(output.questions.innerHTML,/data-question="region" data-value-mode="fields"[^]*name="value" type="text" required/);
  assert.deepEqual(readDecisionValue({dataset:{valueMode:'fields'},elements:[{name:'value',type:'text',value:' 여수 '}]}),{value:'여수'});
});

test('an owned departure question submits the entered Seoul wall time with an explicit offset', t => {
  t.mock.method(Date,'now',() => Date.parse('2026-11-20T12:00:00+09:00'));
  const {output,room} = setup();
  room.questions = [{id:'departure',field:'route_departure',target_ref:'r1',owner_id:'u1',status:'open',text:'언제 출발하나요?'}];
  setUser({id:'u2'});
  renderQuestions(room);
  assert.doesNotMatch(output.questions.innerHTML,/type="datetime-local"/);
  setUser({id:'u1'});
  try {
    renderQuestions(room);
    assert.match(output.questions.innerHTML,/출발 시각 \(한국 시간[^]*type="datetime-local" name="value" required/);
    assert.doesNotMatch(output.questions.innerHTML,/type="datetime-local"[^>]*\svalue=/);
    assert.deepEqual(readDecisionValue({dataset:{valueMode:'route-departure'},elements:{value:{value:'2026-11-21T09:00'}}}),
      {value:'2026-11-21T09:00:00+09:00'});
  } finally {
    setUser(null);
  }
});
