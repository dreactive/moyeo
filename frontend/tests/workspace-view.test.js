import test from 'node:test';
import assert from 'node:assert/strict';
const view = await import('../src/workspace-view.js').catch(() => ({}));
test('unchanged data does not redraw regions and deferred input gets another chance', () => {
  let calls=0;
  view.renderChanged?.('region',{n:1},() => { calls++; return false; });
  view.renderChanged?.('region',{n:1},() => { calls++; });
  view.renderChanged?.('region',{n:1},() => { calls++; });
  assert.equal(calls,2);
});
test('room summary uses the configured region and whole travel dates', () => {
  assert.equal(view.roomMeta?.({region:'여수',start_date:'2026-11-21',end_date:'2026-11-22'}),'2026-11-21 — 2026-11-22 · 1박 2일 · 여수');
});
test('route dependency ignores chat but follows day and plan changes', () => {
  const room={room_id:'r',current_plan:{confirmation_target:{plan_revision:1}},config:{},messages:[]};
  assert.equal(view.routeKey?.(room,'a'),view.routeKey?.({...room,messages:[{id:'m'}]},'a'));
  assert.notEqual(view.routeKey?.(room,'a'),view.routeKey?.(room,'b'));
});
test('a repeated place keeps the currently selected visit day', () => {
  const plan={days:[{date:'a',visits:[{place_ref:'p'}]},{date:'b',visits:[{place_ref:'p'}]}]};
  assert.equal(view.placeVisitDay?.(plan,'p','b')?.date,'b');
});
test('message sequence changes do not invalidate shared card data', () => {
  const before={room_id:'r',seq:1,messages:[],agent_status:{state:'idle'},constraints:[]};
  const after={...before,seq:2,messages:[{id:'m'}],agent_status:{state:'running'}};
  assert.deepEqual(view.sharedRenderData?.(before) ?? before,view.sharedRenderData?.(after) ?? after);
});
