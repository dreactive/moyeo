import test from 'node:test';
import assert from 'node:assert/strict';
import * as plan from '../src/plan.js';
test('review stays fixed when a new draft arrives; every target field matters', () => {
  const a = {participant_version:1,constraint_version:1,evidence_version:1,plan_revision:1,content_hash:'a'};
  const review = {confirmation_target:a};
  assert.equal(plan.displayPlan({review_plan:review,current_plan:{}}),review);
  assert.equal(plan.sameTarget(a,{...a}),true);
  for (const key of Object.keys(a)) assert.equal(plan.sameTarget(a,{...a,[key]:'changed'}),false);
});
import fixture from '../fixtures/room-snapshot.json' with {type:'json'};
for (const key of ['participant_version','constraint_version','evidence_version']) {
  test('confirmation is disabled for an obsolete room basis: ' + key, () => {
    const room = structuredClone(fixture);
    room.current_plan.validation = 'ready';
    room.versions[key]++;
    const output = {};
    globalThis.document = {getElementById:id => ({set innerHTML(value) { output[id] = value; }})};
    plan.renderPlan(room);
    assert.match(output.plan,/data-plan="confirm" disabled/);
  });
}
test('a newer draft revision keeps the unchanged pinned review confirmable', () => {
  const room = structuredClone(fixture);
  room.current_plan.validation = 'ready';
  room.review_plan = structuredClone(room.current_plan);
  room.active_target = structuredClone(room.review_plan.confirmation_target);
  room.current_plan.plan_revision = room.versions.plan_revision = 2;
  room.current_plan.confirmation_target.plan_revision = 2;
  const output = {};
  globalThis.document = {getElementById:id => ({set innerHTML(value) { output[id] = value; }})};
  plan.renderPlan(room);
  assert.doesNotMatch(output.plan.match(/<button data-plan="confirm"[^>]*>/)[0],/disabled/);
});
