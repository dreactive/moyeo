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

test('a corrupt fixture session discards fixture keys only', async () => {
  const removed = [];
  globalThis.sessionStorage = {getItem: () => '{',removeItem: key => removed.push(key)};
  const {readFixtureSession} = await import('../src/fixture-session.js');
  assert.equal(readFixtureSession(), null);
  assert.deepEqual(removed, ['trip-fixture-session-v1','trip-fixture-room']);
});
