import test from 'node:test';
import assert from 'node:assert/strict';
import {drawKakao,clearKakao} from '../src/kakao-adapter.js';
import {initMaps,renderRouteMap} from '../src/map.js';
import snapshot from '../fixtures/room-snapshot.json' with {type:'json'};

test('clearing a Kakao host detaches its markers and lines', () => {
  const layers = [];
  class Layer {
    constructor({map}) { this.map = map; layers.push(this); }
    setMap(map) { this.map = map; }
  }
  const maps = {
    LatLng:class {},
    Map:class {setBounds(){}},
    LatLngBounds:class {extend(){}},
    Marker:Layer,
    Polyline:Layer
  };
  const host = {classList:new Set()};
  const point = {latitude:34.7,longitude:127.6};
  drawKakao(maps,host,[point],[[point,point]]);
  clearKakao(host);
  assert.deepEqual(layers.map(layer => layer.map),[null,null]);
});

test('Kakao viewport styles stay out of the fallback host', () => {
  const child = {style:{}};
  const host = {classList:new Set(),style:{},ownerDocument:{createElement:() => child},append(){}};
  const maps = {
    LatLng:class {},
    Map:class { constructor(node) { node.style.overflow = 'hidden'; } setBounds(){} },
    LatLngBounds:class {extend(){}},
    Marker:class {}
  };
  drawKakao(maps,host,[{latitude:34.7,longitude:127.6}]);
  assert.equal(child.style.overflow,'hidden');
  assert.equal(host.style.overflow,undefined);
});

test('a Kakao drawing failure preserves the selected route data',async t => {
  globalThis.kakao = {maps:{
    load:callback => callback(),
    LatLng:class {},
    Map:class { constructor() { throw new Error('Map drawing failed'); } }
  }};
  t.after(() => delete globalThis.kakao);
  const classes = new Set();
  const route = {classList:{add: key => classes.add(key),remove: key => classes.delete(key)}};
  await initMaps({routeElement:route,placeElement:{},appKey:'test-key'});
  renderRouteMap(snapshot.current_plan,new Map(),snapshot.config,'2026-11-21');
  assert.match(route.innerHTML,/지도를 표시할 수 없어요/);
  assert.match(route.innerHTML,/서버 polyline/);
  assert.equal(classes.has('sdk'),false);
});

test('the Kakao route labels visits by their position within the selected day',async t => {
  const titles = [];
  const maps = {
    load:callback => callback(),
    LatLng:class {},
    Map:class {setBounds(){}},
    LatLngBounds:class {extend(){}},
    Marker:class {constructor({title}) { titles.push(title); }},
    Polyline:class {}
  };
  globalThis.kakao = {maps};
  t.after(() => delete globalThis.kakao);
  await initMaps({routeElement:{classList:new Set()},placeElement:{},appKey:'test-key'});
  titles.length = 0;
  const places = new Map([['fixture:place-b',{name:'둘째 장소',latitude:34.77,longitude:127.68}]]);
  renderRouteMap(snapshot.current_plan,places,snapshot.config,'2026-11-21');
  assert.deepEqual(titles,['예시 출발지','예시 숙소','2. 둘째 장소']);
});

test('Kakao shows a visible visit number when custom overlays are available', () => {
  const labels = [];
  const maps = {
    LatLng:class {},
    Map:class {setBounds(){}},
    LatLngBounds:class {extend(){}},
    Marker:class {},
    CustomOverlay:class {constructor({content}) { labels.push(content.textContent); }}
  };
  const host = {classList:new Set(),ownerDocument:{createElement:() => ({style:{}})},append(){}};
  drawKakao(maps,host,[{latitude:34.7,longitude:127.6,name:'둘째 장소',visitNumber:2}]);
  assert.deepEqual(labels,['2']);
});
