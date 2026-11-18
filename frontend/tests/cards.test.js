
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
