import test from 'node:test';
import assert from 'node:assert/strict';
import {anchorFromKakao,coordinateText} from '../src/place-picker.js';
import {readAnchor,tripPatch} from '../src/trip-input.js';
import * as picker from '../src/place-picker.js';
test('kakao search results become contract anchors', () => {
  assert.deepEqual(anchorFromKakao({id:'123',place_name:'여수엑스포역',road_address_name:'전남 여수시 망양로 2',address_name:'덕충동',x:'127.74381234',y:'34.75301234'}),
    {label:'여수엑스포역',address:'전남 여수시 망양로 2',latitude:34.753012,longitude:127.743812,source_ref:'kakao:place:123'});
  assert.equal(anchorFromKakao({address_name:'전남 여수시 덕충동',x:'127.7',y:'34.7'}).label,'전남 여수시 덕충동');
  assert.equal(anchorFromKakao({address_name:'a',x:'1',y:'2'}).source_ref,null);
  assert.equal(coordinateText({latitude:34.753,longitude:127.7438}),'34.75300, 127.74380');
  assert.equal(coordinateText({latitude:NaN,longitude:1}),'');
});
test('picked anchors keep their source and lose it after a manual coordinate edit', () => {
  assert.deepEqual(readAnchor({origin_label:'역',origin_latitude:'34.7',origin_longitude:'127.6',origin_source_ref:'kakao:place:1'},'origin'),{label:'역',latitude:34.7,longitude:127.6,source_ref:'kakao:place:1'});
  const picked = {label:'역',latitude:34.7,longitude:127.6,source_ref:'kakao:place:1'};
  const edited = {origin:{label:'역',latitude:34.75,longitude:127.6}};
  assert.deepEqual(tripPatch(edited,{origin:picked},{origin:picked}),{origin:{label:'역',latitude:34.75,longitude:127.6}});
  assert.deepEqual(tripPatch({origin:{...picked,label:'새 이름'}},{origin:picked},{origin:picked}),{origin:{...picked,label:'새 이름'}});
});

function anchorControls() {
  const inputs=Object.fromEntries(['label','latitude','longitude','source_ref'].map(name => [name,{name:'lodging_' + name,value:'',type:name === 'latitude' || name === 'longitude' ? 'number' : 'text',dispatchEvent(){}}]));
  const manual={open:false},hint={hidden:true},clear={},listeners={};
  const root={dataset:{},isConnected:true,classList:{contains:() => false},
    querySelector(selector) {
      if (selector === '[data-anchor-manual]') return manual;
      if (selector === '[data-anchor-fallback]') return hint;
      if (selector === '[data-clear-anchor]') return clear;
      const name=/\[name="([^"]+)"\]/.exec(selector)?.[1];
      return inputs[name] ?? null;
    },
    addEventListener:(type,handler) => {listeners[type]=handler;}
  };
  const scope={querySelectorAll:selector => selector.includes(':not(') ? [root] : []};
  root.parentElement=scope;
  return {root,scope,inputs,manual,hint,clear,listeners};
}

test('without a map key the lodging offers usable manual coordinates and a clear action', async () => {
  const {scope,inputs,manual,hint,clear}=anchorControls();
  assert.equal(await picker.enhanceAnchorPickers('',scope),false);
  assert.equal(manual.open,true);
  assert.equal(hint.hidden,false);
  inputs.label.value='수동 숙소';inputs.latitude.value='34.75';inputs.longitude.value='127.67';
  const data=Object.fromEntries(Object.values(inputs).map(input => [input.name,input.value]));
  assert.deepEqual(readAnchor(data,'lodging'),{label:'수동 숙소',latitude:34.75,longitude:127.67});
  clear.onclick?.();
  assert.deepEqual(Object.values(inputs).map(input => input.value),['','','','']);
  assert.equal(readAnchor(Object.fromEntries(Object.values(inputs).map(input => [input.name,input.value])),'lodging'),null);
});

test('a failed map SDK leaves the same lodging coordinate fallback usable', async t => {
  const {scope,manual,hint}=anchorControls();
  globalThis.document={createElement:() => ({}),head:{append:script => script.onerror()}};
  t.after(() => {delete globalThis.document;});
  assert.equal(await picker.enhanceAnchorPickers('blocked-key',scope),false);
  assert.equal(manual.open,true);
  assert.equal(hint.hidden,false);
});

test('manual lodging coordinate edits clear the provider reference even without the SDK', async () => {
  const {scope,inputs,listeners}=anchorControls();
  await picker.enhanceAnchorPickers('',scope);
  inputs.source_ref.value='kakao:place:old';
  inputs.latitude.value='34.8';
  listeners.input?.({isTrusted:true,target:inputs.latitude});
  assert.equal(inputs.source_ref.value,'');
});
