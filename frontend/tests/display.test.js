import test from 'node:test';
import assert from 'node:assert/strict';
import {initMaps,renderRouteMap,renderPlaceMap} from '../src/map.js';
import {renderCost} from '../src/cost.js';
import {renderPlace} from '../src/place.js';
import scenarios from '../fixtures/scenarios.json' with {type:'json'};
test('personal map adapter does not mutate the route adapter', () => {
  const route={innerHTML:''},place={innerHTML:''};
  initMaps({routeElement:route,placeElement:place});
  renderRouteMap(scenarios.ready.snapshot.current_plan,new Map(),scenarios.ready.snapshot.config);
  const before=route.innerHTML;
  renderPlaceMap({name:'개인 장소',latitude:34.7,longitude:127.6});
  assert.equal(route.innerHTML,before);
  assert.match(place.innerHTML,/개인 장소/);
  assert.match(before,/서버 polyline/);
});
test('unknown costs and market prices keep unknown values and distinct budget labels', () => {
  const output={};
  globalThis.document={getElementById:id => ({set innerHTML(value){output[id]=value;}})};
  renderCost(scenarios['unknown-cost'].snapshot.current_plan.cost);
  assert.match(output.cost,/전체 계획액 <strong>미확인/);
  assert.match(output.cost,/120,000원/);
  assert.match(output.cost,/계획 반영 후 여유/);
  renderCost(scenarios.ready.snapshot.current_plan.cost);
  assert.match(output.cost,/50,000원/);
  renderPlace(scenarios.market.places[0]);
  assert.match(output.place,/시가 \(금액 미확인\)/);
  assert.match(output.place,/공급자 기준일 미확인/);
  assert.match(output.place,/ambiguous/);
  renderPlace(scenarios['no-menu'].places[0]);
  assert.match(output.place,/메뉴 미등록 · 가격 미확인/);
});
import {renderPlan} from '../src/plan.js';
import {renderItems,renderConstraints,renderConflicts,renderQuestions} from '../src/items.js';
test('every recorded room scenario renders all shared sections with coherent targets', () => {
  const output={};
  globalThis.document={getElementById:id => ({set innerHTML(value){output[id]=value;}})};
  for (const {snapshot} of Object.values(scenarios)) {
    [renderItems,renderConstraints,renderQuestions,renderConflicts,renderPlan].forEach(render => render(snapshot));
    renderCost((snapshot.review_plan ?? snapshot.current_plan)?.cost);
    assert.ok(output.plan.includes('확인'));
    if (snapshot.active_target) assert.deepEqual(snapshot.active_target,snapshot.review_plan.confirmation_target);
  }
});

test('the individual plan amount comes from the signed-in traveler', () => {
  const card = {innerHTML:''};
  globalThis.document = {getElementById:() => card};
  const cost = scenarios.ready.snapshot.current_plan.cost;
  renderCost({...cost,per_person_krw:{u1:null,u2:173400}},'u2');
  assert.match(card.innerHTML,/내 전체 계획액\s*<strong[^>]*>173,400원/);
  renderCost({...cost,per_person_krw:{u1:null,u2:173400}},'u1');
  assert.match(card.innerHTML,/내 전체 계획액\s*<strong[^>]*>미확인/);
});

test('personal budget figures distinguish spending now from the balance after planning', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  renderCost(scenarios.ready.snapshot.current_plan.cost,'u2');
  assert.match(card.innerHTML,/<dt>앞으로 쓸 수 있는 금액<\/dt><dd>120,000원/);
  assert.match(card.innerHTML,/<dt>계획 반영 후 여유<\/dt><dd>50,000원/);
});
