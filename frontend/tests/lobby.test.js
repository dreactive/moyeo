import test from 'node:test';
import assert from 'node:assert/strict';
import {roomCard,dateRange,roomUrl,addInvitee,inviteSummary} from '../src/lobby.js';
const room = {room_id:'r1',title:'우리의 <여수>',invite_code:'abc',region:'여수',start_date:'2026-11-21',end_date:'2026-11-22',members:[{user_id:'u1',name:'민수'},{user_id:'u2',name:'지수'}],
  last_message:{author_name:'지수',text:'가상 A식당 가자',created_at:'2026-11-18T01:51:00+00:00',mine:false},plan_stage:'confirmed',plan_revision:3,agent_state:'idle'};
test('room cards link into the room and show status, members and last message', () => {
  const card = roomCard(room);
  assert.match(card,/href="\/\?room=r1"/);
  assert.match(card,/<button type="button" class="room-delete" disabled title="방장만 삭제할 수 있어요">/);
  const mine = roomCard({...room,is_owner:true});
  assert.match(mine,/data-delete-room="r1" data-room-title="우리의 &lt;여수&gt;"/);
  assert.match(mine,/방장/);
  assert.doesNotMatch(card,/class="tag owner"/);
  assert.match(card,/우리의 &lt;여수&gt;/);
  assert.match(card,/여행안 r3 확정/);
  assert.match(card,/지수<\/strong> 가상 A식당 가자<time>10:51<\/time>/);
  assert.match(card,/2명/);
  assert.match(roomCard({...room,plan_stage:'empty',plan_revision:null,last_message:null}),/계획 전[\s\S]*아직 대화가 없어요/);
  assert.match(roomCard({...room,region:null,start_date:null,end_date:null}),/날짜 미정/);
  assert.match(roomCard({...room,last_message:{...room.last_message,mine:true}}),/<strong>나<\/strong>/);
  assert.equal(roomUrl('a b'),'/?room=a%20b');
});
test('dates are shortened and missing dates say so', () => {
  assert.equal(dateRange('2026-11-21','2026-11-22'),'11/21 – 11/22');
  assert.equal(dateRange('2026-11-21','2026-11-21'),'11/21');
  assert.equal(dateRange(null,null),'날짜 미정');
});
test('invitees are normalized, deduplicated and exclude the creator', () => {
  let state = addInvitee([],' Friend@Example.COM ','me@x.test');
  assert.deepEqual(state,{list:['friend@example.com'],error:null});
  assert.match(addInvitee(state.list,'friend@example.com').error,/이미/);
  assert.match(addInvitee(state.list,'abc').error,/형식/);
  assert.match(addInvitee(state.list,'ME@x.test','me@x.test').error,/본인/);
  assert.deepEqual(inviteSummary([{ok:true,email:'a@x.t',name:'지수'},{ok:false,email:'b@x.t'}]),{added:['지수'],missing:['b@x.t']});
});
