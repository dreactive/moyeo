import test from 'node:test';
import assert from 'node:assert/strict';
import {initMaps,renderRouteMap,renderPlaceMap} from '../src/map.js';
import snapshot from '../fixtures/room-snapshot.json' with {type:'json'};

const {current_plan:plan,config} = snapshot;
const route = {};
const place = {};
initMaps({routeElement:route,placeElement:place});

test('route map only displays the selected day', () => {
  renderRouteMap(plan,new Map(),config,'2026-11-22');
  assert.match(route.innerHTML,/2026-11-22/);
  assert.doesNotMatch(route.innerHTML,/가상 A식당|서버 polyline/);
});

test('route map shows lodging between the trip start and return', () => {
  renderRouteMap(plan,new Map(),config,'2026-11-22');
  assert.match(route.innerHTML,/예시 숙소/);
  assert.match(route.innerHTML,/예시 귀가 지점/);
  assert.doesNotMatch(route.innerHTML,/예시 출발지/);
});

test('coordinate fallback presents anchor names and readable coordinates', () => {
  renderRouteMap(plan,new Map(),config,'2026-11-21');
  assert.match(route.innerHTML,/예시 출발지 · 34[.]76, 127[.]66/);
});

test('server route geometry stays folded under travel information', () => {
  renderRouteMap(plan,new Map(),config,'2026-11-21');
  assert.match(route.innerHTML,/900초/);
  assert.match(route.innerHTML,/<details><summary>서버 polyline<[/]summary>/);
});

test('clearing the personal map removes SDK mode from that host only', () => {
  const classes = new Set(['sdk']);
  place.classList = {remove: name => classes.delete(name)};
  renderRouteMap(plan,new Map(),config,'2026-11-21');
  const before = route.innerHTML;
  renderPlaceMap(null);
  assert.equal(classes.has('sdk'),false);
  assert.match(place.innerHTML,/장소를 선택/);
  assert.equal(route.innerHTML,before);
});

test('an SDK load failure keeps coordinates visible with the failure reason',async t => {
  route.insertAdjacentHTML = (_,markup) => { route.innerHTML = markup + route.innerHTML; };
  globalThis.document = {createElement:() => ({}),head:{append:script => script.onerror()}};
  t.after(() => delete globalThis.document);
  const loading = initMaps({appKey:'test-key',routeElement:route,placeElement:place});
  renderRouteMap(plan,new Map(),config,'2026-11-21');
  await loading;
  assert.match(route.innerHTML,/지도를 불러오지 못했어요/);
  assert.match(route.innerHTML,/34[.]76, 127[.]66/);
});

test('the coordinate and travel lists use place names from the displayed plan', () => {
  renderRouteMap(plan,new Map(),config,'2026-11-21');
  assert.match(route.innerHTML,/가상 A식당 · 좌표 미확인/);
  assert.match(route.innerHTML,/가상 A식당 → 가상 B공원/);
});
