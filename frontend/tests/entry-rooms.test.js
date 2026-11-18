import test from 'node:test';
import assert from 'node:assert/strict';
import * as rooms from '../src/rooms-page.js';

test('room entry saves the returned room and then opens the workspace', async () => {
  const actions = [];
  globalThis.location = {search:'',assign: path => actions.push(path)};
  globalThis.sessionStorage = {setItem: (key,id) => actions.push([key,id])};
  globalThis.fetch = async () => Response.json({room_id:'new-room'});
  await rooms.submitRoom('/api/rooms', {title:'주말 여행'});
  assert.deepEqual(actions, [['trip-room','new-room'],'/']);
});
