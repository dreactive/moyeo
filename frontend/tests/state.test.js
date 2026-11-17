import test from 'node:test';
import assert from 'node:assert/strict';
import * as state from '../src/state.js';
test('personal place selection disappears when absent from the replacement snapshot', () => {
  const room = {items:[], current_plan:{item_snapshots:[{place_ref:'p'}]}};
  state.applySnapshot(room);
  state.setSelectedPlace('p');
  assert.equal(state.getSelectedPlace(), 'p');
  state.applySnapshot({items:[],current_plan:null});
  assert.equal(state.getSelectedPlace(), null);
  assert.equal(room.selected_place, undefined);
});
test('snapshot subscribers stop receiving updates after unsubscribe', () => {
  let calls = 0;
  const stop = state.subscribeState(() => calls++);
  state.applySnapshot({current_plan:null});
  stop();
  state.applySnapshot({current_plan:null});
  assert.equal(calls, 1);
});
