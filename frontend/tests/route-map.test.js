import test from 'node:test';
import assert from 'node:assert/strict';
import {initMaps,renderRouteMap} from '../src/map.js';
import snapshot from '../fixtures/room-snapshot.json' with {type:'json'};

const {current_plan:plan,config} = snapshot;
const route = {};
const place = {};
initMaps({routeElement:route,placeElement:place});

test('route map only displays the selected day', () => {
  renderRouteMap(plan,new Map(),config,'2026-11-22');
  assert.match(route.innerHTML,/2026-11-22/);
  assert.doesNotMatch(route.innerHTML,/fixture:place-a|서버 polyline/);
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
