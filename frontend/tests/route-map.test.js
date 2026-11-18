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
