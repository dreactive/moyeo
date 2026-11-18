import test from 'node:test';
import assert from 'node:assert/strict';
import {requestFixture,resetFixtureSession} from '../src/fixture-api.js';

test('fixture auth and room data require explicit login', async () => {
  resetFixtureSession();
  await assert.rejects(requestFixture('/api/auth/me'), {status:401});
  await assert.rejects(requestFixture('/api/rooms/room-fixture'), {status:401});
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

test('fixture login survives a document reload', async () => {
  let stored;
  globalThis.sessionStorage = {setItem: (_,value) => stored = value,getItem: () => stored};
  await requestFixture('/api/auth/login', {method:'POST'});
  const next = await import('../src/fixture-api.js?next-page');
  assert.equal((await next.requestFixture('/api/auth/me')).id,'u1');
});

test('created fixture room settings survive a new document', async () => {
  let stored;
  globalThis.sessionStorage = {setItem: (_,value) => stored = value,getItem: () => stored};
  await requestFixture('/api/auth/login', {method:'POST'});
  await requestFixture('/api/rooms', {method:'POST',body:{title:'새 여행방',region:'부산'}});
  const next = await import('../src/fixture-api.js?new-room');
  const room = await next.requestFixture('/api/rooms/room-fixture');
  assert.deepEqual([room.title,room.config.region], ['새 여행방','부산']);
});

test('an incompatible fixture record requires a fresh fixture login', async () => {
  const removed = [];
  globalThis.sessionStorage = {
    getItem: () => '{"authenticated":true}',
    removeItem: key => removed.push(key)
  };
  const next = await import('../src/fixture-api.js?incompatible');
  await assert.rejects(next.requestFixture('/api/auth/me'), {status:401});
  assert.deepEqual(removed,['trip-fixture-session-v1','trip-fixture-room']);
});

test('the saved fixture scenario also restores its place variants', async () => {
  let stored;
  globalThis.sessionStorage = {setItem: (_,value) => stored = value,getItem: () => stored};
  const {replayScenario} = await import('../src/fixture-api.js');
  const {resetFixturePlaces} = await import('../src/fixture-places.js');
  await requestFixture('/api/auth/login', {method:'POST'});
  replayScenario('no-menu');
  resetFixturePlaces();
  const next = await import('../src/fixture-api.js?no-menu');
  const place = await next.requestFixture('/api/rooms/room-fixture/places/fixture%3Aplace-a');
  assert.equal(place.menus.length,0);
  assert.equal(next.getFixtureScenario(),'no-menu');
});

test('the selected fixture user survives a new document', async () => {
  let stored;
  globalThis.sessionStorage = {setItem: (_,value) => stored = value,getItem: () => stored};
  const {setFixtureUser} = await import('../src/fixture-api.js');
  await requestFixture('/api/auth/login', {method:'POST'});
  setFixtureUser('u3');
  const next = await import('../src/fixture-api.js?selected-user');
  const user = await next.requestFixture('/api/auth/me');
  assert.equal(user.id,'u3');
});

test('fixture logout removes fixture data and preserves live room selection', async () => {
  const values = new Map([['trip-room','live-room'],['trip-fixture-room','room-fixture']]);
  globalThis.sessionStorage = {
    getItem: key => values.get(key),
    setItem: (key,value) => values.set(key,value),
    removeItem: key => values.delete(key)
  };
  await requestFixture('/api/auth/login', {method:'POST'});
  await requestFixture('/api/auth/logout', {method:'POST'});
  assert.deepEqual([...values], [['trip-room','live-room']]);
});

test('an unavailable fixture room returns an access status', async () => {
  await requestFixture('/api/auth/login', {method:'POST'});
  await assert.rejects(requestFixture('/api/rooms/missing'), {status:404});
});

test('fixture room changes remain in the saved snapshot', async () => {
  let stored;
  globalThis.sessionStorage = {setItem: (_,value) => stored = value,getItem: () => stored};
  const path = '/api/rooms/room-fixture/messages';
  await requestFixture('/api/auth/login', {method:'POST'});
  const message = await requestFixture(path, {method:'POST',body:{text:'새 대화'}});
  const next = await import('../src/fixture-api.js?messages');
  assert.equal((await next.requestFixture(path)).messages.at(-1).id,message.id);
});

test('a partial fixture snapshot cannot restore the session', async () => {
  const snapshot = {room_id:'room-fixture',config:{fixed_costs:[]}};
  const data = {authenticated:true,userId:'u1',scenario:'initial',snapshot};
  globalThis.sessionStorage = {getItem: () => JSON.stringify(data),removeItem() {}};
  const next = await import('../src/fixture-api.js?partial-snapshot');
  await assert.rejects(next.requestFixture('/api/auth/me'), {status:401});
});
