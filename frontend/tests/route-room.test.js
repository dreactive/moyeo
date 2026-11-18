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
const {renderMaps,renderRoom} = await import('../src/room.js');
await new Promise(setImmediate);

const route = document.getElementById('route-map');
await initMaps({routeElement:route,placeElement:{}});

test('located mentions are shown without a plan and alongside scheduled visits', async () => {
  const room = structuredClone(snapshot);
  room.room_id = 'located-mentions';
  const plan = room.current_plan;
  room.current_plan = null;
  room.review_plan = null;
  room.items.push({...room.items[0],id:'mention',title:'오동도',place_ref:'known-odong',
    place_source_refs:['s1'],state:'mentioned',supporter_ids:[],opponent_ids:[]});
  const paths = [];
  globalThis.fetch = async path => {
    const url = new URL(path,'http://room.test');
    paths.push(url);
    const id = decodeURIComponent(url.pathname.split('/').at(-1));
    return Response.json({place:{id,name:id,latitude:34.7,longitude:127.7}});
  };
  applySnapshot(room);
  await renderMaps(room);
  assert.ok(paths.some(url => url.pathname.endsWith('known-odong') && url.searchParams.has('location_only')));
  assert.match(route.innerHTML,/오동도[^]*34\.7[^]*언급됨/);
  room.current_plan = plan;
  applySnapshot(room);
  setSelectedDay(plan.days[0].date);
  await renderMaps(room);
  assert.match(route.innerHTML,/오동도/);
  assert.match(route.innerHTML,/가상 A식당/);
});

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
  assert.ok(paths.every(path => new URL(path,'http://room.test').searchParams.get('location_only') === 'true'));
});

test('unavailable coordinates leave the rest of the selected route usable', async () => {
  const room = {...snapshot,room_id:'room-partial'};
  applySnapshot(room);
  const place = {id:'fixture:place-a',latitude:34.761,longitude:127.661};
  globalThis.fetch = async path => new URL(path,'http://room.test').pathname.endsWith('place-a') ? Response.json({place}) : new Response(null,{status:503});
  await renderMaps(room);
  assert.match(route.innerHTML,/가상 A식당 · 34[.]761, 127[.]661/);
  assert.match(document.getElementById('route-load-status').innerHTML,/일부 장소 좌표/);
});

test('the route retry refreshes coordinates without changing the selected date', async () => {
  const room = {...snapshot,room_id:'room-retry'};
  applySnapshot(room);
  globalThis.fetch = async () => new Response(null,{status:503});
  await renderMaps(room);
  const status = document.getElementById('route-load-status');
  assert.match(status.innerHTML,/data-route-retry/);
  globalThis.fetch = async path => Response.json({place:{
    id:decodeURIComponent(new URL(path,'http://room.test').pathname.split('/').at(-1)),latitude:34.761,longitude:127.661
  }});
  await status.onclick({target:{closest:selector => selector === '[data-route-retry]' ? {} : null}});
  assert.equal(status.innerHTML,'');
  assert.match(route.innerHTML,/가상 A식당 · 34[.]761, 127[.]661/);
});
test('expired place requests propagate instead of appearing as coordinate failures', async () => {
  const room={...snapshot,room_id:'room-expired'};
  applySnapshot(room);
  globalThis.fetch=async () => new Response(null,{status:401});
  await assert.rejects(renderMaps(room),error => error.status === 401);
});

test('a support-only room update redraws the route and selected details using already loaded coordinates', async () => {
  const room = {...structuredClone(snapshot),room_id:'room-support-only',messages:[]};
  Object.assign(document.getElementById('messages'),{
    querySelector:() => null,querySelectorAll:() => [],dataset:{},children:[],replaceChildren(){}
  });
  applySnapshot(room);
  let requests = 0;
  const detailPaths = [];
  globalThis.fetch = async path => {
    requests++;
    const url = new URL(path,'http://room.test');
    if (!url.searchParams.has('location_only')) detailPaths.push(url.pathname);
    const id = decodeURIComponent(url.pathname.split('/').at(-1));
    return Response.json({place:{id,name:id,latitude:34.761,longitude:127.661},menus:[],evidence:[]});
  };
  await renderMaps(room);
  const {selectPlace} = await import('../src/place.js');
  await selectPlace(room.room_id,'fixture:place-a');
  assert.deepEqual(detailPaths,[`/api/rooms/${room.room_id}/places/fixture%3Aplace-a`]);
  renderRoom(room);
  const before = requests;
  const changed = structuredClone(room);
  Object.assign(changed.items[0],{state:'supported',supporter_ids:['u1','u2','u3'],opponent_ids:['u4']});
  applySnapshot(changed);
  renderRoom(changed);
  assert.match(route.innerHTML,/과반 지지[^]*지지 3\/4 · 반대 1명/);
  assert.match(document.getElementById('route-summary').innerHTML,/과반 지지[^]*지지 3\/4 · 반대 1명/);
  assert.match(document.getElementById('place').innerHTML,/과반 지지[^]*지지 3\/4 · 반대 1명/);
  assert.equal(requests,before);
  const costBefore = document.getElementById('cost').innerHTML;
  changed.confirmations = [{user_id:'u1',target:changed.current_plan.confirmation_target,stance:'confirm'}];
  renderRoom(changed);
  const costAfter = document.getElementById('cost').innerHTML;
  assert.match(costBefore,/같은 여행안 동의 0\/4/);
  assert.match(costAfter,/같은 여행안 동의 1\/4/);
});
