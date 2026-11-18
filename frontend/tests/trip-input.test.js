import test from 'node:test';
import assert from 'node:assert/strict';
import {readAnchor} from '../src/trip-input.js';
test('blank anchors remain null and partial anchors cannot become zero coordinates', () => {
  assert.equal(readAnchor({},'origin'),null);
  assert.throws(() => readAnchor({origin_label:'역'},'origin'));
  assert.deepEqual(readAnchor({origin_label:'역',origin_latitude:'34.7',origin_longitude:'127.6'},'origin'),{label:'역',latitude:34.7,longitude:127.6});
});
import {readTripConfig} from '../src/trip-input.js';
test('trip serialization keeps budget numeric, anchors null and cost IDs stable', () => {
  const costs=[{id:'stable-cost'}];
  const result=readTripConfig({region:'여수',per_person_budget_krw:'200000'},costs);
  assert.equal(result.per_person_budget_krw,200000);
  assert.equal(result.lodging,null);
  assert.equal('origin' in result,false);
  assert.equal(result.fixed_costs,costs);
});
import * as tripInput from '../src/trip-input.js';
test('saving an edited end time leaves a remotely updated budget untouched', () => {
  const baseline={per_person_budget_krw:200000,day_end_time:'18:00'};
  const edited={...baseline,day_end_time:'19:00'};
  const latest={...baseline,per_person_budget_krw:300000};
  const patch=tripInput.changedTripFields(edited,baseline);
  assert.deepEqual(patch,{day_end_time:'19:00'});
  assert.equal({...latest,...patch}.per_person_budget_krw,300000);
  assert.equal(edited.day_end_time,'19:00');
});
test('editing an anchor label preserves a newer coordinate from another participant', () => {
  const baseline={lodging:{label:'호텔',latitude:34.7,longitude:127.6}};
  const edited={lodging:{...baseline.lodging,label:'바다 호텔'}};
  const latest={lodging:{...baseline.lodging,latitude:34.8}};
  assert.deepEqual(tripInput.tripPatch(edited,baseline,latest),{lodging:{label:'바다 호텔',latitude:34.8,longitude:127.6}});
});
test('editing one cost preserves remote prices, metadata and newly added costs', () => {
  const baseline={fixed_costs:[{id:'c1',description:'숙박',unit_price_krw:80000,subtotal_krw:null}]};
  const edited={fixed_costs:[{...baseline.fixed_costs[0],description:'숙박 메모'}]};
  const latest={fixed_costs:[{...baseline.fixed_costs[0],unit_price_krw:90000,subtotal_krw:90000},{id:'c2',description:'교통'}]};
  const result=tripInput.tripPatch(edited,baseline,latest);
  assert.deepEqual(result.fixed_costs,[{...latest.fixed_costs[0],description:'숙박 메모'},latest.fixed_costs[1]]);
});
test('blank optional trip fields become unset instead of failing validation', () => {
  const result=readTripConfig({region:'',start_date:'',end_date:'',day_start_time:'',day_end_time:'',per_person_budget_krw:''},[]);
  assert.deepEqual([result.start_date,result.end_date,result.per_person_budget_krw,result.day_start_time,result.day_end_time],[null,null,null,'09:00','18:00']);
  assert.equal(result.region,'');
  assert.throws(() => tripInput.requireTripBasics(result),/도시/);
  assert.throws(() => tripInput.requireTripBasics({...result,region:'제주'}),/예산/);
  assert.equal(tripInput.requireTripBasics({...result,region:'제주',per_person_budget_krw:0}).per_person_budget_krw,0);
  assert.throws(() => readTripConfig({start_date:'2026-11-20',end_date:'2026-11-19'},[]),/종료일/);
});
