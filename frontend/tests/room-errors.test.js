import test from 'node:test';
import assert from 'node:assert/strict';
const errors = await import('../src/room-errors.js').catch(() => ({}));
test('only an expired session stops protected room work', async () => {
  const events=[];
  for (const status of [401,503]) await errors.runRoomTask?.(() => { throw Object.assign(new Error('request'),{status}); },{showError:error => events.push(error.status),expired:() => events.push('expired')});
  assert.deepEqual(events,[401,'expired',503]);
});
