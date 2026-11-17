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
