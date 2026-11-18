import test from 'node:test';
import assert from 'node:assert/strict';
import {readAnswer,parseValue,placeRefOf,readDecisionValue} from '../src/items.js';
import {errorText} from '../src/api.js';
test('question answers are serialized per field without hand-written JSON', () => {
  assert.deepEqual(readAnswer('menu_selection',{menu_id:'m1',quantity:'2',scope:'per_person'}),{menu_id:'m1',quantity:2,scope:'per_person'});
  assert.deepEqual(readAnswer('visit_duration',{stay_minutes:'90'}),{stay_minutes:90});
  assert.deepEqual(readAnswer('lodging',{label:'숙소',latitude:'34.75',longitude:'127.67'}),{label:'숙소',latitude:34.75,longitude:127.67});
  assert.deepEqual(readAnswer('support_target',{item_id:'item-a'}),{item_id:'item-a'});
  assert.deepEqual(readAnswer('constraint_value',{value:'16:00'}),{value:'16:00'});
  assert.deepEqual(readAnswer('constraint_value',{value:'200000'}),{value:200000});
});
test('constraint values keep plain text and parse JSON when valid', () => {
  assert.equal(parseValue('16:00'),'16:00');
  assert.equal(parseValue('"16:00"'),'16:00');
  assert.deepEqual(parseValue('{"a":1}'),{a:1});
});
test('menu questions find the target place from plan snapshots', () => {
  const snapshot = {review_plan:null,current_plan:{item_snapshots:[{id:'i1',place_ref:'p1'}]},confirmed_plan:null};
  assert.equal(placeRefOf(snapshot,'i1'),'p1');
  assert.equal(placeRefOf(snapshot,'missing'),null);
});

test('menu questions never fall back to frozen places absent from the current draft', () => {
  const frozen = {item_snapshots:[{id:'i1',place_ref:'old-place'}]};
  const snapshot = {review_plan:frozen,confirmed_plan:frozen,current_plan:null};
  assert.equal(placeRefOf(snapshot,'i1'),null);
  snapshot.current_plan = {item_snapshots:[]};
  assert.equal(placeRefOf(snapshot,'i1'),null);
});

test('route departure answers reject missing, invalid, and past Seoul times', t => {
  t.mock.method(Date,'now',() => Date.parse('2026-11-20T12:00:00+09:00'));
  const answer = value => readDecisionValue({dataset:{valueMode:'route-departure'},elements:{value:{value}}});
  assert.throws(() => answer(''),/출발 날짜와 시각/);
  assert.throws(() => answer('invalid'),/미래/);
  assert.throws(() => answer('2026-11-20T11:59'),/미래/);
  assert.throws(() => answer('2026-11-20T12:00'),/미래/);
  assert.deepEqual(answer('2026-11-20T12:01'),{value:'2026-11-20T12:01:00+09:00'});
});
test('server errors become short Korean messages', () => {
  assert.equal(errorText(401,'Invalid credentials'),'이메일 또는 비밀번호가 맞지 않아요.');
  assert.equal(errorText(409,'Confirmation target changed'),'여행안이 바뀌었어요. 새 안을 확인해 주세요.');
  assert.equal(errorText(403,'unknown detail'),'권한이 없어요.');
  assert.equal(errorText(503,null),'서버와 연결하지 못했어요.');
});
test('times with an offset are shown in Asia/Seoul', async () => {
  const {clock} = await import('../src/ui.js');
  assert.equal(clock('2026-11-18T01:51:47+00:00'),'10:51');
  assert.equal(clock('2026-11-21T10:10:00+09:00'),'10:10');
});
