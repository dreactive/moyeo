
import test from 'node:test';
import assert from 'node:assert/strict';
import {renderCost} from '../src/cost.js';
import scenarios from '../fixtures/scenarios.json' with {type:'json'};

test('the cost disclosure identifies travelers by their room display names', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  const {members,current_plan} = scenarios.ready.snapshot;
  renderCost(current_plan.cost,'u1',members);
  assert.match(card.innerHTML,/<strong>참가자1<\/strong>/);
});

test('room cost composition uses known room subtotals and disappears when total cost is unknown', () => {
  const card = {};
  globalThis.document = {getElementById:() => card};
  renderCost(scenarios.ready.snapshot.current_plan.cost);
  assert.match(card.innerHTML,/방 전체 경비 구성[^]*숙박 320,000원/);
  renderCost(scenarios['unknown-cost'].snapshot.current_plan.cost);
  assert.doesNotMatch(card.innerHTML,/방 전체 경비 구성/);
});
