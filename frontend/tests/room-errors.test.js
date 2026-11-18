import test from 'node:test';
import assert from 'node:assert/strict';
const errors = await import('../src/room-errors.js').catch(() => ({}));
test('only an expired session stops protected room work', async () => {
  const events=[];
  for (const status of [401,503]) await errors.runRoomTask?.(() => { throw Object.assign(new Error('request'),{status}); },{showError:error => events.push(error.status),expired:() => events.push('expired')});
  assert.deepEqual(events,[401,'expired',503]);
});
test('stale target failures request a refresh without repeating the original action', async () => {
  let actions=0,refreshes=0;
  await errors.runRoomTask?.(() => { actions++; throw Object.assign(new Error('changed'),{status:409}); },{showError:() => {},stale:async () => { refreshes++; }});
  assert.equal(actions,1); assert.equal(refreshes,1);
});
test('only missing access selects another entry page', () => {
  assert.equal(errors.roomLoadRedirect?.({status:403}),'/rooms.html?reason=room-access');
  assert.equal(errors.roomLoadRedirect?.({status:404}),'/rooms.html?reason=room-access');
  assert.equal(errors.roomLoadRedirect?.({status:503}),null);
});
