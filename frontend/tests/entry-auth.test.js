import test from 'node:test';
import assert from 'node:assert/strict';
import * as auth from '../src/auth-page.js';

test('login succeeds directly into room selection', async () => {
  globalThis.location = {search:'',assign: path => assert.equal(path,'/rooms.html')};
  globalThis.fetch = async () => Response.json({id:'u1'});
  await auth.submitAuth('login', {email:'test@example.test',password:'example-password'});
});
