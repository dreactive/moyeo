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

test('selecting a room action reveals only its form', () => {
  const panels = {create:{},join:{querySelector: () => ({focus() {}})}};
  globalThis.document = {getElementById: id => panels[id]};
  const create = {getAttribute: () => 'create',setAttribute() {}};
  const join = {getAttribute: () => 'join',setAttribute() {}};
  rooms.chooseRoomAction([create,join], join);
  assert.deepEqual([panels.create.hidden,panels.join.hidden], [true,false]);
});

test('a failed room session lookup leaves choices hidden and offers retry', async () => {
  const elements = {error:{},'room-actions':{hidden:true}};
  const retry = {hidden:true};
  globalThis.document = {getElementById: id => elements[id]};
  globalThis.fetch = async () => new Response('', {status:503});
  await rooms.checkRoomsPage(retry);
  assert.deepEqual([retry.hidden,elements['room-actions'].hidden], [false,true]);
});

test('a pending create blocks join until the room entry can be retried', async () => {
  const trip = [];
  const join = [['invite_code',' AbC ']];
  const createButton = {};
  const joinButton = {};
  const choice = {};
  trip.querySelector = () => createButton;
  join.querySelector = () => joinButton;
  globalThis.FormData = Map;
  globalThis.document = {getElementById: () => ({}),querySelectorAll: () => []};
  const create = Promise.withResolvers();
  let sent;
  globalThis.fetch = async (path, options) => {
    if (path === '/api/rooms') return create.promise;
    sent = [path, JSON.parse(options.body)];
    return new Response('', {status:404});
  };
  rooms.bindRoomForms(trip,join,[choice]);
  const submit = {preventDefault() {}};
  const pending = trip.onsubmit(submit);
  await join.onsubmit(submit);
  assert.equal(sent,undefined);
  assert.equal(choice.disabled,true);
  create.resolve(new Response('', {status:503}));
  await pending;
  assert.equal(choice.disabled,false);
  await join.onsubmit(submit);
  assert.deepEqual(sent, ['/api/rooms/join',{invite_code:'AbC'}]);
});

test('room page startup opens choices for the signed-in user', async () => {
  const elements = {};
  const element = id => elements[id] ??= {querySelector: () => ({})};
  globalThis.document = {getElementById: element,querySelectorAll: () => []};
  globalThis.fetch = async () => Response.json({name:'여행자'});
  await rooms.startRoomsPage();
  assert.equal(elements.session.textContent,'여행자');
  assert.equal(elements['room-actions'].hidden,false);
});

test('room selection reports an inaccessible previously selected room', async () => {
  globalThis.location = {search:'?reason=room-access'};
  const elements = {error:{},session:{},'room-actions':{},logout:{}};
  globalThis.document = {getElementById: id => elements[id]};
  globalThis.fetch = async () => Response.json({name:'여행자'});
  await rooms.checkRoomsPage({});
  assert.match(elements.error.textContent,/방에 접근할 수 없습니다/);
});
