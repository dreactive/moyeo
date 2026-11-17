import test from 'node:test';
import assert from 'node:assert/strict';
import {requestFixture,replayScenario,setFixtureUser} from '../src/fixture-api.js';
test('fixture confirmation preserves activated target and rejects stale targets', async () => {
  const room = replayScenario('activated');
  setFixtureUser('u1');
  const path='/api/rooms/room-fixture/plan/confirm';
  await assert.rejects(requestFixture(path,{method:'POST',body:{target:{...room.active_target,content_hash:'stale'}}}));
  const result=await requestFixture(path,{method:'POST',body:{target:room.active_target}});
  assert.equal(result.review_plan.plan_revision,2);
  assert.equal(result.confirmations.length,1);
});
test('market and missing-menu fixture variants reset on the next scenario', async () => {
  const path='/api/rooms/room-fixture/places/fixture%3Aplace-a';
  replayScenario('no-menu');
  assert.equal((await requestFixture(path)).menus.length,0);
  replayScenario('ready');
  assert.equal((await requestFixture(path)).menus[0].price_krw,10000);
});
test('fixture input echoes keep history immutable and owner questions cannot create another support', async () => {
  const room=replayScenario('confirm-u4');
  const history=structuredClone(room.confirmed_plan);
  const result=await requestFixture('/api/rooms/room-fixture/trip',{method:'PATCH',body:{per_person_budget_krw:250000}});
  assert.equal(result.config.per_person_budget_krw,250000);
  assert.deepEqual(result.confirmed_plan,history);
  replayScenario('questions');setFixtureUser('u1');
  await assert.rejects(requestFixture('/api/rooms/room-fixture/questions/q5/answer',{method:'POST',body:{value:{value:0}}}),/소유자/);
  const answered=await requestFixture('/api/rooms/room-fixture/questions/q6/answer',{method:'POST',body:{value:{item_id:'item-a'}}});
  assert.deepEqual(answered.items[0].supporter_ids,['u1']);
  assert.equal(answered.questions[6].target_ref,'item-a');
});
test('recorded end-to-end scenario keeps three approvals unconfirmed then confirms one exact target', async () => {
  const initial=replayScenario('initial');
  assert.equal(initial.items[0].state,'mentioned');
  const conflict=replayScenario('conflict');
  assert.equal(conflict.items[1].state,'supported');
  assert.deepEqual(conflict.items[1].conflict_ids,['c1']);
  await requestFixture('/api/rooms/room-fixture/conflicts/c1/select',{method:'POST',body:{option_id:'drop'}});
  let room=replayScenario('ready');
  for (const id of ['u1','u2','u3']) {
    setFixtureUser(id);
    room=await requestFixture('/api/rooms/room-fixture/plan/confirm',{method:'POST',body:{target:room.current_plan.confirmation_target}});
  }
  assert.equal(room.confirmed_plan,null);
  assert.equal(room.confirmations.length,3);
  setFixtureUser('u4');
  room=await requestFixture('/api/rooms/room-fixture/plan/confirm',{method:'POST',body:{target:room.review_plan.confirmation_target}});
  assert.equal(room.confirmed_plan.plan_revision,1);
  assert.ok(room.items.every(item => item.state==='confirmed'));
});
