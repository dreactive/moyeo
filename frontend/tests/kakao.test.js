import test from 'node:test';
import assert from 'node:assert/strict';
import {loadKakao,drawKakao} from '../src/kakao-adapter.js';
test('optional SDK adapter uses given coordinates and server polylines only', async () => {
  assert.equal(await loadKakao(''),null);
  const markers=[],paths=[];
  const maps={
    LatLng:class {constructor(lat,lng){this.lat=lat;this.lng=lng;}},
    Map:class {setBounds(){}},
    LatLngBounds:class {extend(){}},
    Marker:class {constructor(options){markers.push(options);}},
    Polyline:class {constructor(options){paths.push(options.path);}}
  };
  const element={innerHTML:'',classList:{add(){}}};
  const points=[{latitude:34.7,longitude:127.6},{latitude:34.8,longitude:127.7}];
  drawKakao(maps,element,points,[points]);
  assert.equal(markers[0].position.lat,34.7);
  assert.equal(markers[1].position.lng,127.7);
  assert.deepEqual(paths[0],markers.map(marker=>marker.position));
});

test('map and search share one SDK script that includes the places services', async t => {
  const scripts=[];
  globalThis.document={createElement:() => ({}),head:{append:script => scripts.push(script)}};
  t.after(() => { delete globalThis.document; delete globalThis.kakao; });
  const first=loadKakao('shared-key'),second=loadKakao('shared-key');
  assert.match(scripts[0].src,/libraries=services/);
  assert.equal(scripts.length,1);
  const maps={load:ready => ready(),services:{}};
  globalThis.kakao={maps};
  scripts.forEach(script => script.onload());
  assert.deepEqual(await Promise.all([first,second]),[maps,maps]);
});
