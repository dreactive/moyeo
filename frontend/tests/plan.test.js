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

test('a required condition awaiting its owner disables plan confirmation', () => {
  const room = structuredClone(fixture);
  room.current_plan.validation = 'ready';
  room.constraints[0].status = 'needs_owner_confirmation';
  const output = {};
  globalThis.document = {getElementById:id => ({set innerHTML(value) { output[id] = value; }})};
  plan.renderPlan(room);
  assert.match(output.plan,/data-plan="confirm" disabled/);
});

function renderConsensus(room) {
  const hosts = {plan:{},'confirmed-plan':{}};
  globalThis.document = {getElementById:id => hosts[id]};
  plan.renderPlan(room);
  return hosts.plan.innerHTML;
}

test('votes stop projecting as current when the room basis changes', () => {
  const room = structuredClone(fixture);
  room.confirmations = [{user_id:'u1',stance:'confirm',target:room.current_plan.confirmation_target}];
  room.versions.constraint_version++;
  assert.match(renderConsensus(room),/0\/4/);
});

test('unanimous votes wait for the official snapshot of the same target', () => {
  const room = structuredClone(fixture);
  room.confirmations = room.members.map(({user_id}) => ({
    user_id,stance:'confirm',target:room.current_plan.confirmation_target
  }));
  assert.match(renderConsensus(room),/4\/4.*모두 동의 · 확정 확인 중/);
  room.confirmed_plan = room.current_plan;
  assert.match(renderConsensus(room),/4\/4.*공식 확정/);
});

test('the consensus marks each traveler by their vote on the displayed plan', () => {
  const room = structuredClone(fixture);
  room.confirmations = [{user_id:'u1',stance:'confirm',target:room.current_plan.confirmation_target}];
  const output = renderConsensus(room);
  assert.match(output,/참가자1 · 동의/);
  assert.match(output,/참가자2 · 아직/);
});
