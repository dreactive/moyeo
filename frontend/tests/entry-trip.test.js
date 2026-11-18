import test from 'node:test';
import assert from 'node:assert/strict';
import * as trip from '../src/trip-form.js';

test('creation payload includes title and the existing trip config', () => {
  globalThis.FormData = Map;
  globalThis.document = {querySelectorAll: () => []};
  const payload = trip.readTripForm([['title','여수'],['per_person_budget_krw','150000']]);
  assert.deepEqual([payload.title,payload.per_person_budget_krw,payload.origin], ['여수',150000,null]);
});

test('restoring the trip pre-fills title and scalar settings', () => {
  const form = [];
  form.elements = {title:{}, region:{}};
  globalThis.document.getElementById = () => form;
  trip.restoreTripForm({title:'주말 여행', config:{region:'여수'}});
  assert.deepEqual(form.elements, {title:{value:'주말 여행'},region:{value:'여수'}});
});

test('restoring an anchor writes its fields individually', () => {
  const form = [];
  form.elements = {title:{}, origin_label:{},origin_latitude:{},origin_longitude:{}};
  globalThis.document.getElementById = () => form;
  trip.restoreTripForm({title:'주말 여행',config:{origin:{label:'여수역',latitude:34,longitude:127}}});
  assert.equal(form.elements.origin_latitude.value,34);
});
