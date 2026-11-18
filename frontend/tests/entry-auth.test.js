import test from 'node:test';
import assert from 'node:assert/strict';
import * as auth from '../src/auth-page.js';

test('login succeeds directly into room selection', async () => {
  let visited;
  globalThis.location = {search:'',assign: path => visited = path};
  globalThis.fetch = async () => Response.json({id:'u1'});
  await auth.submitAuth('login', {email:'test@example.test',password:'example-password'});
  assert.equal(visited,'/rooms.html');
});

test('signup refuses mismatched passwords before sending a request', async () => {
  globalThis.fetch = () => assert.fail('signup should stay on the form');
  await assert.rejects(auth.submitAuth('register', {password:'long-enough',password_confirmation:'different'}), RangeError);
});
