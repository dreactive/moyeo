import test from 'node:test';
import assert from 'node:assert/strict';
import {subscribeFixture,emitFixture} from '../src/fixture-api.js';
test('closed and different-room fixture subscriptions never receive events', () => {
  let calls = 0;
  const stop = subscribeFixture('r',{onMessage:() => calls++});
  emitFixture('onMessage',{room_id:'other'});
  emitFixture('onMessage',{room_id:'r'});
  stop();
  emitFixture('onMessage',{room_id:'r'});
  assert.equal(calls,1);
});
