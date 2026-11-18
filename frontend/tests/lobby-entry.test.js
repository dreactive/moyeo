import test,{beforeEach} from 'node:test';
import assert from 'node:assert/strict';
import * as lobby from '../src/lobby.js';

beforeEach(() => {
  globalThis.location = {search:'',assign() {}};
  globalThis.sessionStorage = {setItem() {},getItem() {},removeItem() {}};
  globalThis.document = {getElementById:() => ({})};
});

test('room creation resumes invitations after a failure without creating another room', async () => {
  const calls = [];
  let unavailable = true;
  globalThis.fetch = async (path,options) => {
    calls.push([path,JSON.parse(options.body)]);
    if (path === '/api/rooms') return Response.json({room_id:'r1',title:'새 여행',invite_code:'CODE'});
    if (path.endsWith('/members') && JSON.parse(options.body).email === 'second@x.test' && unavailable) return new Response('',{status:503});
    return Response.json({name:'친구'});
  };
  const state = {};
  await assert.rejects(lobby.createRoomWithInvites(['first@x.test','second@x.test'],state),{status:503});
  unavailable = false;
  const result = await lobby.createRoomWithInvites(['first@x.test','second@x.test'],state);
  assert.equal(result.room.room_id,'r1');
  assert.equal(result.results.length,2);
  assert.equal(calls.filter(([path]) => path === '/api/rooms').length,1);
  assert.equal(calls.filter(([,body]) => body.email === 'first@x.test').length,1);
});

test('missing invitees are reported while accepted members and the created room remain available', async () => {
  globalThis.fetch = async path => path === '/api/rooms'
    ? Response.json({room_id:'r1',invite_code:'CODE'})
    : Response.json({detail:'User not found'},{status:404});
  const result = await lobby.createRoomWithInvites(['missing@x.test']);
  assert.deepEqual(result.results,[{ok:false,email:'missing@x.test'}]);
  assert.equal(result.room.invite_code,'CODE');
});

test('pending lobby actions lock create and join and unlock them after failure', async () => {
  const create = {},join = {},tab = {};
  const failure = Promise.withResolvers();
  let calls = 0;
  const execute = lobby.lobbyActionLock([create,join,tab],() => {});
  const first = execute(async () => { calls++; await failure.promise; });
  await execute(async () => { calls++; });
  assert.equal(calls,1);
  assert.deepEqual([create.disabled,join.disabled,tab.disabled],[true,true,true]);
  failure.reject(new Error('offline'));
  await first;
  assert.deepEqual([create.disabled,join.disabled,tab.disabled],[false,false,false]);
});

test('fixture room links and selection stay separate from live selection', () => {
  globalThis.location.search = '?mode=fixture';
  const stored = [];
  globalThis.sessionStorage.setItem = (...args) => stored.push(args);
  globalThis.location.assign = path => stored.push(path);
  lobby.enterRoom({room_id:'a b'});
  assert.deepEqual(stored[0],['trip-fixture-room','a b']);
  const url = new URL(stored[1],'https://workspace.local');
  assert.equal(url.searchParams.get('room'),'a b');
  assert.equal(url.searchParams.get('mode'),'fixture');
});

test('only deleting the selected room clears the selection', async () => {
  let selected = 'r1';
  const removed = [];
  globalThis.sessionStorage = {getItem:() => selected,removeItem:key => removed.push(key)};
  globalThis.fetch = async () => Response.json({ok:true});
  await lobby.deleteRoom('r2');
  assert.deepEqual(removed,[]);
  await lobby.deleteRoom('r1');
  assert.deepEqual(removed,['trip-room']);
});

function lobbyDocument() {
  const elements = {};
  const element = id => elements[id] ??= {disabled:false,value:'',hidden:false,innerHTML:'',focus() {}};
  const controls = ['open-create','logout','create-room','invite-email','invite-code'].map(element);
  element('rooms').innerHTML = 'previous rooms';
  globalThis.document = {
    getElementById:element,
    querySelectorAll:selector => selector.startsWith('#open-create') ? controls : [],
    addEventListener() {}
  };
  return {elements,controls};
}

test('lobby session and list failures protect actions and retry without losing the previous list', async () => {
  const {elements,controls} = lobbyDocument();
  let phase = 'session-down';
  globalThis.fetch = async path => {
    if (phase === 'session-down' || (path === '/api/rooms' && phase === 'list-down')) return new Response('',{status:503});
    return Response.json(path === '/api/auth/me' ? {name:'여행자',email:'me@x.test'} : {rooms:[]});
  };
  await lobby.startLobbyPage();
  assert.equal(elements.retry.hidden,false);
  assert.ok(controls.every(control => control.disabled));
  assert.equal(elements.rooms.innerHTML,'previous rooms');
  phase = 'list-down';
  await elements.retry.onclick();
  assert.equal(elements.retry.hidden,false);
  assert.ok(controls.every(control => control.disabled));
  assert.equal(elements.rooms.innerHTML,'previous rooms');
  phase = 'ready';
  await elements.retry.onclick();
  assert.equal(elements.retry.hidden,true);
  assert.ok(controls.every(control => !control.disabled));
  assert.match(elements.rooms.innerHTML,/첫 여행방/);
});

test('an expired lobby session redirects before the room list is requested', async () => {
  lobbyDocument();
  const paths = [];
  const visited = [];
  globalThis.location.assign = path => visited.push(path);
  globalThis.fetch = async path => { paths.push(path); return new Response('',{status:401}); };
  await lobby.startLobbyPage();
  assert.deepEqual(paths,['/api/auth/me']);
  assert.deepEqual(visited,['/login.html']);
});

test('expired lobby actions keep fixture mode on the authentication redirect', async () => {
  globalThis.location.search = '?mode=fixture';
  let visited;
  globalThis.location.assign = path => visited = path;
  await lobby.lobbyActionLock([])(() => { throw Object.assign(new Error('expired'),{status:401}); });
  const url = new URL(visited,'https://workspace.local');
  assert.equal(url.pathname,'/login.html');
  assert.equal(url.searchParams.get('next'),'/rooms');
  assert.equal(url.searchParams.get('mode'),'fixture');
});

test('an invalid create response can be retried without reusing an invalid room', async () => {
  let requests = 0;
  globalThis.fetch = async () => Response.json(++requests === 1 ? {} : {room_id:'r1'});
  const state = {};
  await assert.rejects(lobby.createRoomWithInvites([],state),/방 정보/);
  const result = await lobby.createRoomWithInvites([],state);
  assert.equal(result.room.room_id,'r1');
  assert.equal(requests,2);
});
