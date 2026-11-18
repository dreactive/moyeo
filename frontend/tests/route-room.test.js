import test from 'node:test';
import assert from 'node:assert/strict';
import snapshot from '../fixtures/room-snapshot.json' with {type:'json'};
import {initMaps} from '../src/map.js';
import {applySnapshot,setSelectedDay} from '../src/state.js';

const elements = new Map();
globalThis.document = {
  querySelectorAll: () => [],
  addEventListener(){},
  getElementById(id) {
    if (!elements.has(id)) elements.set(id,{});
    return elements.get(id);
  }
};
globalThis.location = {search:'',assign(){}};
globalThis.fetch = async () => new Response(null,{status:401});
const {renderMaps} = await import('../src/room.js');
await new Promise(setImmediate);

const route = document.getElementById('route-map');
await initMaps({routeElement:route,placeElement:{}});

test('a new date updates the route before its place requests finish', async () => {
  applySnapshot(snapshot);
  setSelectedDay('2026-11-22');
  await renderMaps(snapshot);
  setSelectedDay('2026-11-21');
  const load = Promise.withResolvers();
  globalThis.fetch = async () => { await load.promise; return Response.json(null); };
  const pending = renderMaps(snapshot);
  try {
    assert.match(route.innerHTML,/2026-11-21/);
  } finally {
    load.resolve();
    await pending;
  }
});

test('chat-only renders share one in-flight route lookup', async () => {
  const room = {...snapshot,room_id:'room-dedupe'};
  applySnapshot(room);
  const load = Promise.withResolvers();
  const paths = [];
  globalThis.fetch = async path => { paths.push(path); await load.promise; return Response.json(null); };
  const first = renderMaps(room);
  const chatUpdate = renderMaps({...room,messages:[]});
  load.resolve();
  await Promise.all([first,chatUpdate]);
  assert.equal(paths.length,2);
});

test('unavailable coordinates leave the rest of the selected route usable', async () => {
  const room = {...snapshot,room_id:'room-partial'};
  applySnapshot(room);
  const place = {id:'fixture:place-a',latitude:34.761,longitude:127.661};
  globalThis.fetch = async path => path.endsWith('place-a') ? Response.json({place}) : new Response(null,{status:503});
  await renderMaps(room);
  assert.match(route.innerHTML,/가상 A식당 · 34[.]761, 127[.]661/);
  assert.match(document.getElementById('route-load-status').innerHTML,/일부 장소 좌표/);
});
