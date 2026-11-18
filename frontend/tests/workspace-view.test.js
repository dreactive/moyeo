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
