import test from 'node:test';
import assert from 'node:assert/strict';
import {drawKakao,clearKakao} from '../src/kakao-adapter.js';

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
