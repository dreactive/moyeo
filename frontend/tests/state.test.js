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
test('SSE room sequence prevents an older refresh from losing a saved message', () => {
  state.applySnapshot({room_id:'r',seq:1,current_plan:null,messages:[]});
  state.appendMessage({id:'m',room_id:'r',seq:1},3);
  state.applyRoomResponse({room_id:'r',seq:2,current_plan:null,messages:[]},'r');
  assert.equal(state.getSnapshot().messages.length,1);
  assert.equal(state.getSnapshot().seq,3);
});
test('duplicate SSE delivery still advances the room sequence', () => {
  state.applySnapshot({room_id:'r',seq:1,current_plan:null,messages:[]});
  const message={id:'m',room_id:'r',seq:1};
  state.appendMessage(message);
  state.appendMessage(message,3);
  assert.equal(state.getSnapshot().seq,3);
  assert.equal(state.getSnapshot().messages.length,1);
});

test('same-room refresh retains older loaded messages and deduplicates later deliveries', () => {
  const messages = Array.from({length:61}, (_, index) => ({id:'m' + index,seq:index + 1,room_id:'r'}));
  state.applySnapshot({room_id:'r',seq:60,messages:messages.slice(0,60)});
  state.applyRoomResponse({room_id:'r',seq:61,messages:messages.slice(-50)},'r');
  state.appendMessage(messages.at(-1));
  state.appendMessage(messages.at(-1),61);
  assert.deepEqual(state.getSnapshot().messages,messages);
});

test('a partial-only place loses selection when any input basis changes or the current result removes it', () => {
  const versions={participant_version:1,constraint_version:1,evidence_version:1,plan_revision:1};
  for (const key of Object.keys(versions)) {
    const room={room_id:'partial-selection-' + key,versions,current_plan:null,
      agent_results:{run_id:'partial',versions:{...versions},build_itinerary:{days:[{visits:[{place_ref:'partial-only'}]}]}}};
    state.applySnapshot(room);
    state.setSelectedPlace('partial-only');
    state.applySnapshot(structuredClone(room));
    assert.equal(state.getSelectedPlace(),'partial-only');
    state.applySnapshot({...room,versions:{...versions,[key]:2}});
    assert.equal(state.getSelectedPlace(),null,key);
  }
  const room={room_id:'partial-selection-replaced',versions,current_plan:null,
    agent_results:{run_id:'partial',versions,build_itinerary:{unplaced_items:[{place_ref:'partial-only'}]}}};
  state.applySnapshot(room);
  state.setSelectedPlace('partial-only');
  state.applySnapshot({...room,agent_results:{...room.agent_results,build_itinerary:{days:[]}}});
  assert.equal(state.getSelectedPlace(),null);
});

test('a stale partial result does not remove a place independently present in the displayed plan or request results', () => {
  const versions={participant_version:1,constraint_version:1,evidence_version:1,plan_revision:1};
  for (const source of [{current_plan:{item_snapshots:[{place_ref:'known-place'}]}},
    {agent_requests:[{result_refs:['known-place']}]}]) {
    const room={room_id:'independent-selection',versions,...source,
      agent_results:{run_id:'stale',versions:{...versions,evidence_version:0},
        build_itinerary:{days:[{visits:[{place_ref:'known-place'}]}]}}};
    state.applySnapshot(room);
    state.setSelectedPlace('known-place');
    state.applySnapshot(structuredClone(room));
    assert.equal(state.getSelectedPlace(),'known-place');
  }
});
