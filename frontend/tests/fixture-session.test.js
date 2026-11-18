import test from 'node:test';
import assert from 'node:assert/strict';
import {requestFixture} from '../src/fixture-api.js';

test('fixture auth requires explicit login before session lookup', async () => {
  await assert.rejects(requestFixture('/api/auth/me'), {status:401});
  await requestFixture('/api/auth/login', {method:'POST'});
  assert.equal((await requestFixture('/api/auth/me')).id,'u1');
});

test('fixture session storage includes only fixture state fields', async () => {
  let stored;
  globalThis.sessionStorage = {setItem: (_,value) => stored = value,getItem: () => stored};
  const {readFixtureSession,saveFixtureSession} = await import('../src/fixture-session.js');
  saveFixtureSession({authenticated:true,userId:'u1',password:'discard-me'});
  assert.deepEqual(readFixtureSession(), {authenticated:true,userId:'u1'});
});
