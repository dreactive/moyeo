import test from 'node:test';
import assert from 'node:assert/strict';
import fixture from '../fixtures/room-snapshot.json' with {type:'json'};
import {renderItems} from '../src/items.js';
test('old confirmed state cannot invent current majority support', () => {
  const room = structuredClone(fixture);
  room.confirmed_plan = structuredClone(room.current_plan);
  room.current_plan.confirmation_target.content_hash = 'new';
  room.items[0].state='confirmed'; room.items[0].supporter_ids=[];
  let output='';
  globalThis.document={getElementById:() => ({set innerHTML(value){output=value;}})};
  renderItems(room);
  assert.match(output,/새 안 · 미확정/);
  assert.doesNotMatch(output,/card confirmed/);
});
test('the official confirmed review projects green despite a newer draft support state', () => {
  const room = structuredClone(fixture);
  room.review_plan = structuredClone(room.current_plan);
  room.confirmed_plan = structuredClone(room.review_plan);
  room.active_target = structuredClone(room.review_plan.confirmation_target);
  room.current_plan.confirmation_target.content_hash = 'newer-draft';
  room.current_plan.confirmation_target.plan_revision = 2;
  room.current_plan.plan_revision = 2;
  room.versions.plan_revision = 2;
  room.items[0].state = 'supported';
  room.items[0].included_in_plan = false;
  room.items[1].state = 'mentioned';
  let output = '';
  globalThis.document = {getElementById:() => ({set innerHTML(value) { output = value; }})};
  renderItems(room);
  assert.equal((output.match(/class="card confirmed"/g) ?? []).length,2);
  room.items[0].item_version++;
  renderItems(room);
  assert.doesNotMatch(output,/class="card confirmed"><strong>가상 A식당/);
  assert.match(output,/가상 B공원 · 확정/);
});
for (const key of ['participant_version','constraint_version','evidence_version']) {
  test('official colors stop when the room basis changes: ' + key, () => {
    const room = structuredClone(fixture);
    room.confirmed_plan = structuredClone(room.current_plan);
    const history = structuredClone(room.confirmed_plan);
    room.versions[key]++;
    room.items.forEach(item => { item.state = 'mentioned'; });
    let output = '';
    globalThis.document = {getElementById:() => ({set innerHTML(value) { output = value; }})};
    renderItems(room);
    assert.doesNotMatch(output,/card confirmed/);
    assert.deepEqual(room.confirmed_plan,history);
  });
}

import * as decisions from '../src/items.js';

test('the typed decision reader preserves numeric fields in the submitted payload', () => {
  const form = {dataset:{valueMode:'fields'},elements:[
    {name:'menu_id',type:'text',value:'fixture:menu-a'},
    {name:'quantity',type:'number',value:'2',valueAsNumber:2},
    {name:'scope',type:'select-one',value:'shared'}
  ]};
  assert.deepEqual(decisions.readDecisionValue?.(form),{menu_id:'fixture:menu-a',quantity:2,scope:'shared'});
});

import scenarios from '../fixtures/scenarios.json' with {type:'json'};

test('anchor, stay and menu questions offer controls with DTO field names', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  decisions.renderQuestions(scenarios.questions.snapshot);
  assert.match(card.innerHTML,/name="latitude" type="number"/);
  assert.match(card.innerHTML,/name="stay_minutes" type="number"/);
  assert.match(card.innerHTML,/<select name="scope"/);
});

test('target questions offer only the items attached to the question', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  decisions.renderQuestions(scenarios.questions.snapshot);
  assert.match(card.innerHTML,/<select name="item_id"[^>]*>[\s\S]*<option value="item-a">가상 A식당/);
  assert.doesNotMatch(card.innerHTML,/<option value="item-b">/);
});

test('required budgets use a human label, won, and an owner verification status', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  decisions.renderConstraints(scenarios.ready.snapshot);
  assert.match(card.innerHTML,/1인 예산/);
  assert.match(card.innerHTML,/200,000원/);
  assert.match(card.innerHTML,/필수 · 본인 확인됨/);
});

test('condition questions offer a numeric field for a budget target', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  setUser({id:'u1'});
  decisions.renderQuestions(scenarios.questions.snapshot);
  setUser(null);
  assert.match(card.innerHTML,/data-question="q5" data-value-mode="fields">[^]*name="value" type="number"/);
});

test('editing a return deadline passes a scalar time to the existing condition route', () => {
  const form = {dataset:{valueMode:'scalar'},elements:{value:{type:'time',value:'16:00'}}};
  assert.doesNotThrow(() => decisions.readDecisionValue(form));
  assert.equal(decisions.readDecisionValue(form),'16:00');
});

import {setUser} from '../src/state.js';
test('condition rows name their owner and reserve verification for a pending owner decision', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  setUser({id:'u1'});
  decisions.renderConstraints(scenarios.conflict.snapshot);
  setUser(null);
  assert.match(card.innerHTML,/참가자4 · 필수 · 본인 확인됨/);
  assert.doesNotMatch(card.innerHTML,/data-constraint="return-time"|data-constraint-confirm=/);
});

test('superseded conditions can be read in history without an edit action', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  const room = structuredClone(scenarios.ready.snapshot);
  room.constraints[0].status = 'superseded';
  setUser({id:'u1'});
  decisions.renderConstraints(room);
  setUser(null);
  assert.match(card.innerHTML,/<summary>이전 조건 보기<\/summary>[^]*200,000원/);
  assert.doesNotMatch(card.innerHTML,/data-constraint=/);
});

test('another member can read a private question without an answer form', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  setUser({id:'u2'});
  decisions.renderQuestions(scenarios.questions.snapshot);
  setUser(null);
  assert.match(card.innerHTML,/constraint_value 입력 확인/);
  assert.doesNotMatch(card.innerHTML,/data-question="q5"/);
});
