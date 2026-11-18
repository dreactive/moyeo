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
