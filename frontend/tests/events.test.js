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
import {openRoomEvents} from '../src/events.js';
test('the first SSE open and later reconnects both request snapshot recovery', () => {
  globalThis.location = {search:''};
  let source;
  globalThis.EventSource = class {
    constructor() { source = this; }
    addEventListener() {}
    close() {}
  };
  let recoveries = 0;
  const close = openRoomEvents('r',{onReconnect:() => recoveries++});
  source.onopen();
  assert.equal(recoveries,1);
  source.onopen();
  assert.equal(recoveries,2);
  close();
  source.onopen();
  assert.equal(recoveries,2);
});
