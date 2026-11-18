import test from 'node:test';
import assert from 'node:assert/strict';
import room from '../fixtures/room-snapshot.json' with {type:'json'};
import place from '../fixtures/place-details.json' with {type:'json'};
import otherPlace from '../fixtures/place-details-b.json' with {type:'json'};
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
  const placeMap = {};
  initMaps({routeElement:{},placeElement:placeMap});
  applySnapshot(structuredClone(room));
  return {requests,output,placeMap};
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
    const loading = output.place;
    const next = structuredClone(room);
    next.current_plan.confirmation_target[key] += 'changed';
    applySnapshot(next);
    requests[0].resolve(Response.json(details(11111)));
    await pending;
    assert.equal(output.place,loading,key);
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

test('place details link back to their visit in the displayed plan', async () => {
  const {requests,output} = prepare();
  const pending = selectPlace(room.room_id,place.place.id);
  requests[0].resolve(Response.json(place));
  await pending;
  assert.match(output.place,/data-route-place="fixture:place-a"/);
});

test('the place card shows address and hours before the source disclosure', async () => {
  const {requests,output} = prepare();
  const pending = selectPlace(room.room_id,place.place.id);
  requests[0].resolve(Response.json(place));
  await pending;
  assert.match(output.place,/<dt>주소<\/dt><dd>계약 예시용 주소[^]*<dt>영업시간<\/dt><dd>[^]*<summary>장소 정보 출처/);
});

test('an obsolete place failure does not interrupt the newest selection', async () => {
  const {requests} = prepare();
  const older = selectPlace(room.room_id,place.place.id);
  const newer = selectPlace(room.room_id,place.place.id);
  requests[1].resolve(Response.json(place));
  await newer;
  requests[0].reject(new Error('Earlier detail failed'));
  await assert.doesNotReject(older);
});

test('menu IDs remain available to answer the room menu question', async () => {
  const {requests,output} = prepare();
  const pending = selectPlace(room.room_id,place.place.id);
  requests[0].resolve(Response.json(place));
  await pending;
  assert.match(output.place,/장소 정보 출처<\/summary>[^]*메뉴 ID <code>fixture:menu-a<\/code>/);
});

test('selecting a new place immediately replaces the previous card and map with loading', async () => {
  const {requests,output,placeMap} = prepare();
  const first = selectPlace(room.room_id,place.place.id);
  requests[0].resolve(Response.json(place));
  await first;
  const next = selectPlace(room.room_id,otherPlace.place.id);
  assert.match(output.place,/불러오는 중/);
  assert.match(placeMap.innerHTML,/장소를 선택하세요/);
  requests[1].resolve(Response.json(otherPlace));
  await next;
});

test('a failed place lookup offers a retry that restores the latest card and map', async () => {
  const {requests,output,placeMap} = prepare();
  const stale = selectPlace(room.room_id,place.place.id);
  const pending = selectPlace(room.room_id,otherPlace.place.id);
  requests[0].resolve(Response.json(place));
  await stale;
  assert.match(output.place,/불러오는 중/);

  requests[1].resolve(new Response(null,{status:503}));
  await assert.rejects(pending);
  assert.match(output.place,/불러오지 못했어요[^]*data-place="fixture:place-b">장소 정보 다시 시도/);

  const retry = selectPlace(room.room_id,otherPlace.place.id);
  requests[2].resolve(Response.json(otherPlace));
  await retry;
  assert.match(output.place,/가상 B공원/);
  assert.match(placeMap.innerHTML,/가상 B공원/);
});
