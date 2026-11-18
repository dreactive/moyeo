import test from 'node:test';
import assert from 'node:assert/strict';
import * as ui from '../src/ui.js';
test('a pending control suppresses duplicate actions and becomes usable after failure', async () => {
  const button={disabled:false}; let reject;
  const first=ui.withPending?.(button,() => new Promise((a,b) => { reject=b; }));
  assert.equal(button.disabled,true);
  assert.equal(await ui.withPending?.(button,() => 2),undefined);
  reject(new Error('offline'));
  await assert.rejects(first,/offline/);
  assert.equal(button.disabled,false);
});
