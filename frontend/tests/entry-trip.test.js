import test from 'node:test';
import assert from 'node:assert/strict';
import * as trip from '../src/trip-form.js';

test('creation payload includes title and the existing trip config', () => {
  globalThis.FormData = Map;
  globalThis.document = {querySelectorAll: () => []};
  const payload = trip.readTripForm([['title','여수'],['per_person_budget_krw','150000']]);
  assert.deepEqual([payload.title,payload.per_person_budget_krw,payload.origin], ['여수',150000,null]);
});
