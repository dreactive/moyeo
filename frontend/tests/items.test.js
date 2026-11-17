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
