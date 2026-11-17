import test from 'node:test';
import assert from 'node:assert/strict';
import room from '../fixtures/room-snapshot.json' with {type:'json'};
import place from '../fixtures/place-details.json' with {type:'json'};
import {applySnapshot} from '../src/state.js';
import {selectPlace} from '../src/place.js';
import {initMaps} from '../src/map.js';

function prepare() {
  const requests = [];
  const output = {};
  globalThis.location = {search:''};
  globalThis.fetch = () => {
    const request = Promise.withResolvers();
    requests.push(request);
    return request.promise;
  };
  globalThis.document = {getElementById:id => ({set innerHTML(value) { output[id] = value; }})};
  initMaps({routeElement:{},placeElement:{}});
  applySnapshot(structuredClone(room));
  return {requests,output};
}
function details(price) {
  const result = structuredClone(place);
  result.menus[0].price_krw = price;
  result.evidence[0].raw_value = 'price-' + price;
  return result;
}
test('older detail request cannot overwrite a newer response for the same place', async () => {
  const {requests,output} = prepare();
  const oldRequest = selectPlace(room.room_id,place.place.id);
  const newRequest = selectPlace(room.room_id,place.place.id);
  requests[1].resolve(Response.json(details(22222)));
  await newRequest;
  requests[0].resolve(Response.json(details(11111)));
  await oldRequest;
  assert.match(output.place,/22,222원/);
  assert.doesNotMatch(output.place,/price-11111/);
});
test('a changed displayed plan target invalidates an in-flight detail response without a replacement request', async () => {
  for (const key of Object.keys(room.current_plan.confirmation_target)) {
    const {requests,output} = prepare();
    const pending = selectPlace(room.room_id,place.place.id);
    const next = structuredClone(room);
    next.current_plan.confirmation_target[key] += 'changed';
    applySnapshot(next);
    requests[0].resolve(Response.json(details(11111)));
    await pending;
    assert.equal(output.place,undefined,key);
  }
});
test('a new draft does not invalidate details for the unchanged pinned review', async () => {
  const {requests,output} = prepare();
  const pinned = structuredClone(room);
  pinned.review_plan = structuredClone(pinned.current_plan);
  applySnapshot(pinned);
  const pending = selectPlace(room.room_id,place.place.id);
  const next = structuredClone(pinned);
  next.current_plan.confirmation_target.plan_revision = 2;
  applySnapshot(next);
  requests[0].resolve(Response.json(details(22222)));
  await pending;
  assert.match(output.place,/22,222원/);
});
test('revision two price and evidence survive a late revision one response for the same place', async () => {
  const {requests,output} = prepare();
  const older = selectPlace(room.room_id,place.place.id);
  const next = structuredClone(room);
  Object.assign(next.current_plan.confirmation_target,{plan_revision:2,evidence_version:2});
  applySnapshot(next);
  const newer = selectPlace(room.room_id,place.place.id);
  requests[1].resolve(Response.json(details(22222)));
  await newer;
  requests[0].resolve(Response.json(details(11111)));
  await older;
  assert.match(output.place,/22,222원/);
  assert.match(output.place,/price-22222/);
  assert.doesNotMatch(output.place,/price-11111/);
});
