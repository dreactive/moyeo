import {html,escapeHtml as e} from './ui.js';
export function renderRoom(snapshot) {
  renderItems(snapshot); renderConstraints(snapshot); renderQuestions(snapshot); renderConflicts(snapshot);
  renderPlan(snapshot); renderCost(displayPlan(snapshot)?.cost);
  html('messages',snapshot.messages.map(message => `<li id="message-${e(message.id)}"><strong>${e(snapshot.members.find(member => member.user_id === message.author_id)?.name ?? message.author_id)}</strong><p>${e(message.text)}</p><small>${e(message.created_at)}</small></li>`).join(''));
  html('room-heading', e(snapshot.title) + ' · 초대 ' + e(snapshot.invite_code));
  html('members', snapshot.members.map(member => e(member.name)).join(' · '));
  html('agent', e(snapshot.agent_status.label) + ' / ' + e(snapshot.agent_status.state) + ' / ' + e(snapshot.agent_status.run_id));
}
import {requestJson,getDataMode} from './api.js';
import {applySnapshot,subscribeState,setUser} from './state.js';
import {showError} from './ui.js';
export async function startRoomApp() {
  bindAccount(); bindSessionActions(); bindFixtureControls(); bindPlanActions(); bindDecisionActions(); bindTripInput();
  html('mode', getDataMode() === 'fixture' ? '개발용 fixture · 실제 API 조회 아님' : 'LIVE · Backend 연결');
  subscribeState(snapshot => snapshot && renderRoom(snapshot));
  const user = await requestJson('/api/auth/me');
  setUser(user);
  html('session', e(user.name));
  const savedRoom = getDataMode() === 'fixture' ? 'room-fixture' : sessionStorage.getItem('trip-room');
  if (savedRoom) enterRoom(await requestJson('/api/rooms/' + encodeURIComponent(savedRoom)));
}
startRoomApp().catch(showError);
import {getSnapshot,appendMessage} from './state.js';
import {openRoomEvents} from './events.js';
import {run} from './ui.js';
let closeEvents = () => {};
let roomId = null;
export async function refreshRoom(id = roomId) {
  const snapshot = await requestJson('/api/rooms/' + encodeURIComponent(id));
  if (id === roomId && snapshot.seq >= (getSnapshot()?.seq ?? 0)) applySnapshot(snapshot);
}
export function enterRoom(snapshot) {
  closeEvents();
  roomId = snapshot.room_id;
  sessionStorage.setItem('trip-room',roomId);
  applySnapshot(snapshot);
  closeEvents = openRoomEvents(roomId,{onMessage:data => appendMessage(data.message),
    onRoomUpdated:() => run(() => refreshRoom()),onPlanConfirmed:() => run(() => refreshRoom()),
    onAgentStatus:() => run(() => refreshRoom()),onReconnect:() => run(() => refreshRoom())});
}

import {renderItems,renderConstraints,renderQuestions,renderConflicts} from './items.js';
import {renderPlan,displayPlan} from './plan.js';
import {renderCost} from './cost.js';

function bindForm(id, task) {
  document.getElementById(id).onsubmit = event => {
    event.preventDefault();
    run(() => task(Object.fromEntries(new FormData(event.target)),event.submitter?.value,event.target));
  };
}
function showUser(user) { setUser(user); html('session',e(user?.name ?? '로그인 전')); }
function bindAccount() {
  bindForm('auth',async (data, action) => {
    const body = action === 'register' ? data : {email:data.email,password:data.password};
    showUser(await requestJson('/api/auth/' + action,{method:'POST',body}));
    document.querySelector('#auth [name=password]').value = '';
  });
  bindForm('join',async body => enterRoom(await requestJson('/api/rooms/join',{method:'POST',body})));
}

function bindSessionActions() {
  document.getElementById('logout').onclick = () => run(async () => {
    await requestJson('/api/auth/logout',{method:'POST'});
    closeEvents(); roomId = null; sessionStorage.removeItem('trip-room');
    applySnapshot(null); showUser(null); location.reload();
  });
  bindForm('message',async (body, action,form) => {
    if (!roomId) throw new Error('먼저 방에 입장하세요.');
    appendMessage(await requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/messages',{method:'POST',body}));
    form.reset();
  });
}

import {scenarios,replayScenario,setFixtureUser,emitFixture} from './fixture-api.js';
function bindFixtureControls() {
  if (getDataMode() !== 'fixture') return;
  document.getElementById('fixture-controls').hidden = false;
  html('scenario',Object.entries(scenarios).map(([key,value]) => `<option value="${e(key)}">${e(value.label)}</option>`).join(''));
  document.getElementById('replay').onclick = () => enterRoom(replayScenario(document.getElementById('scenario').value));
  document.getElementById('fixture-user').onchange = event => { showUser(setFixtureUser(event.target.value)); renderRoom(getSnapshot()); };
  document.getElementById('reconnect').onclick = () => run(() => refreshRoom());
}

async function roomAction(path,body,method = 'POST') {
  if (!roomId) throw new Error('먼저 방에 입장하세요.');
  const result = await requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/' + path,{method,body});
  if (result.room_id) applySnapshot(result); else await refreshRoom();
}
function bindPlanActions() {
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-plan]');
    if (!button) return;
    const snapshot = getSnapshot();
    const action = button.dataset.plan;
    run(() => roomAction('plan/' + action,action === 'activate' ? {plan_revision:snapshot.current_plan.plan_revision} : {target:displayPlan(snapshot).confirmation_target}));
  });
  document.getElementById('replan').onclick = () => run(() => roomAction('agent-runs',{reason:'manual_replan'}));
}

function bindDecisionActions() {
  document.addEventListener('submit',event => {
    const form = event.target;
    if (!form.dataset.question && !form.dataset.constraint) return;
    event.preventDefault();
    run(() => roomAction(form.dataset.question ? 'questions/' + encodeURIComponent(form.dataset.question) + '/answer' : 'constraints/' + encodeURIComponent(form.dataset.constraint),{value:JSON.parse(new FormData(form).get('value'))},form.dataset.question ? 'POST' : 'PATCH'));
  });
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-conflict],[data-constraint-confirm]');
    if (!button) return;
    run(() => button.dataset.conflict ? roomAction('conflicts/' + encodeURIComponent(button.dataset.conflict) + '/select',{option_id:button.dataset.option}) : roomAction('constraints/' + encodeURIComponent(button.dataset.constraintConfirm) + '/confirm'));
  });
}

import {readAnchor} from './trip-input.js';
import {appendCost,readFixedCosts} from './fixed-costs.js';
function bindTripInput() {
  document.getElementById('add-cost').onclick = () => appendCost();
  document.addEventListener('click',event => event.target.closest('[data-remove-cost]')?.closest('[data-cost-id]').remove());
  bindForm('trip',async (data,action) => {
    const body = {title:data.title,region:data.region,start_date:data.start_date,end_date:data.end_date,transport:'car',day_start_time:data.day_start_time,day_end_time:data.day_end_time,per_person_budget_krw:Number(data.per_person_budget_krw),fixed_costs:readFixedCosts()};
    ['origin','destination','lodging'].forEach(key => body[key] = readAnchor(data,key));
    if (action === 'create') enterRoom(await requestJson('/api/rooms',{method:'POST',body}));
    else { delete body.title; await roomAction('trip',body,'PATCH'); }
  });
}

