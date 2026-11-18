import test from 'node:test';
import assert from 'node:assert/strict';
import * as state from '../src/state.js';
test('personal day survives refresh but falls back when removed', () => {
  const plan = {item_snapshots:[],days:[{date:'2026-11-21'},{date:'2026-11-22'}]};
  state.applySnapshot({room_id:'day',current_plan:plan});
  state.setSelectedDay?.('2026-11-22');
  state.applySnapshot({room_id:'day',current_plan:plan});
  assert.equal(state.getSelectedDay?.(),'2026-11-22');
  state.applySnapshot({room_id:'day',current_plan:{...plan,days:[plan.days[0]]}});
  assert.equal(state.getSelectedDay?.(),'2026-11-21');
});
