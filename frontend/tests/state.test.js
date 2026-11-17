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
test('POST and SSE copies of a person message appear only once', () => {
  state.applySnapshot({room_id:'r',current_plan:null,messages:[]});
  state.appendMessage({id:'m',room_id:'r',text:'hi'});
  state.appendMessage({id:'m',room_id:'r',text:'hi'});
  state.appendMessage({id:'other',room_id:'different'});
  assert.equal(state.getSnapshot().messages.length,1);
});
test('personal selection follows the displayed review while a draft removes the place', () => {
  const review = {item_snapshots:[{place_ref:'p'}]};
  state.applySnapshot({current_plan:review,review_plan:review});
  state.setSelectedPlace('p');
  state.applySnapshot({current_plan:{item_snapshots:[]},review_plan:review});
  assert.equal(state.getSelectedPlace(),'p');
});
test('late room responses cannot replace another room or a newer sequence', () => {
  state.applySnapshot({room_id:'b',seq:10,current_plan:null});
  state.applyRoomResponse({room_id:'a',seq:20,current_plan:null},'a');
  state.applyRoomResponse({room_id:'b',seq:9,current_plan:null},'b');
  assert.equal(state.getSnapshot().room_id,'b');
  assert.equal(state.getSnapshot().seq,10);
});
