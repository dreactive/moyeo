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
