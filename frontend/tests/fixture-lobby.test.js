import test, {beforeEach} from 'node:test';
import assert from 'node:assert/strict';
import {requestFixture,resetFixtureSession,setFixtureUser,fixtureRoom} from '../src/fixture-api.js';

beforeEach(async () => {
  delete globalThis.sessionStorage;
  resetFixtureSession();
  await requestFixture('/api/auth/login', {method:'POST'});
});

test('fixture lobby lists the selected scenario and supports empty room creation', async () => {
  const {rooms} = await requestFixture('/api/rooms');
  assert.equal(rooms[0].room_id, 'room-fixture');
  assert.equal(rooms[0].is_owner, true);
  const room = await requestFixture('/api/rooms', {method:'POST',body:{}});
  assert.equal(room.room_id, rooms[0].room_id);
  assert.ok(room.title);
});

test('fixture invitation distinguishes registered fixture participants', async () => {
  const path = '/api/rooms/room-fixture/members';
  assert.equal((await requestFixture(path, {method:'POST',body:{email:'U2@fixture.test'}})).user_id, 'u2');
  await assert.rejects(requestFixture(path, {method:'POST',body:{email:'missing@example.test'}}), {status:404});
});

test('fixture deletion enforces owner and makes deleted room inaccessible until recreated', async () => {
  const path = '/api/rooms/room-fixture';
  setFixtureUser('u2');
  await assert.rejects(requestFixture(path, {method:'DELETE'}), {status:403});
  setFixtureUser('u1');
  await requestFixture(path, {method:'DELETE'});
  assert.deepEqual((await requestFixture('/api/rooms')).rooms, []);
  await assert.rejects(requestFixture(path), {status:404});
  await requestFixture('/api/rooms', {method:'POST',body:{}});
  assert.equal((await requestFixture(path)).room_id, 'room-fixture');
});

test('fixture lobby treats an archived plan as unconfirmed after membership changes', async () => {
  fixtureRoom.confirmed_plan = structuredClone(fixtureRoom.current_plan);
  const target = fixtureRoom.current_plan.confirmation_target;
  for (const key of ['participant_version','constraint_version','evidence_version']) fixtureRoom.versions[key] = target[key];
  assert.equal((await requestFixture('/api/rooms')).rooms[0].plan_stage, 'confirmed');
  fixtureRoom.versions.participant_version++;
  assert.equal((await requestFixture('/api/rooms')).rooms[0].plan_stage, 'draft');
});
