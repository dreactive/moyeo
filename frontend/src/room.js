import {renderRoutePanel} from './route-view.js';
import {getSelectedDay,setSelectedDay} from './state.js';
import {renderOverview,renderAgentBanner,renderChanged,routeKey} from './workspace-view.js';
import {renderChat,isSendKey} from './chat.js';
import {getUser} from './state.js';
import {requireSession,readRoomId,saveRoomId,clearRoomId,navigate,preparePage,signOut} from './session.js';
import {html,escapeHtml as e} from './ui.js';
import {requestJson,getDataMode} from './api.js';
import {applySnapshot,subscribeState,setUser} from './state.js';
import {showError} from './ui.js';
import {getSnapshot,appendMessage,applyRoomResponse} from './state.js';
import {openRoomEvents} from './events.js';
import {run} from './ui.js';
import {renderItems,renderConstraints,renderQuestions,renderConflicts,readDecisionValue} from './items.js';
import {renderPlan,displayPlan} from './plan.js';
import {renderCost} from './cost.js';
import {scenarios,replayScenario,setFixtureUser,emitFixture} from './fixture-api.js';
import {readTripConfig,tripPatch} from './trip-input.js';
import {appendCost,readFixedCosts} from './fixed-costs.js';
import {initMaps,renderRouteMap,renderPlaceMap} from './map.js';
import {selectPlace,renderPlace} from './place.js';
import {getSelectedPlace} from './state.js';
function renderDecisionRegions(snapshot) {
  const {messages,agent_status,...shared} = snapshot;
  renderChanged('decisions',[shared,getUser()?.id],() => {
    if (document.activeElement?.closest('#constraints form,#questions form')) return false;
    renderItems(snapshot); renderConstraints(snapshot); renderQuestions(snapshot); renderConflicts(snapshot);
  });
}
export function renderRoom(snapshot) {
  const {messages,agent_status,...shared} = snapshot;
  renderDecisionRegions(snapshot);
  renderChanged('plan',[shared,getUser()?.id],() => { renderPlan(snapshot); renderCost(displayPlan(snapshot)?.cost,getUser()?.id); });
  renderChanged('route-panel',[displayPlan(snapshot),getSelectedDay()],() => renderRoutePanel(snapshot,getSelectedDay()));
  run(() => renderMaps(snapshot));
  renderChanged('chat',[snapshot.room_id,snapshot.messages,snapshot.members,getUser()?.id],() => renderChat(snapshot,getUser()?.id));
  renderOverview(snapshot);
  renderAgentBanner(snapshot);
}
export async function startRoomApp() {
  preparePage();
  const user = await requireSession();
  if (!user) return;
  const savedRoom = readRoomId();
  if (!savedRoom) return navigate('/rooms.html');
  initMaps({routeElement:document.getElementById('route-map'),placeElement:document.getElementById('place-map'),appKey:document.querySelector('meta[name="kakao-map-app-key"]').content});
  bindSessionActions(); bindFixtureControls(); bindPlanActions(); bindDecisionActions(); bindTripInput(); bindHistory();
  html('mode', getDataMode() === 'fixture' ? '개발용 fixture · 실제 API 조회 아님' : 'LIVE · Backend 연결');
  subscribeState(snapshot => snapshot && renderRoom(snapshot));
  setUser(user);
  html('session', e(user.name));
  if (savedRoom) enterRoom(await requestJson('/api/rooms/' + encodeURIComponent(savedRoom)));
}
startRoomApp().catch(showError);
let closeEvents = () => {};
let roomId = null;
let tripBaseline = {};
export async function refreshRoom(id = roomId) {
  const snapshot = await requestJson('/api/rooms/' + encodeURIComponent(id));
  if (id === roomId) applyRoomResponse(snapshot,id);
}
export function enterRoom(snapshot) {
  closeEvents();
  roomId = snapshot.room_id;
  restoreTrip(snapshot);
  saveRoomId(roomId);
  applySnapshot(snapshot);
  closeEvents = openRoomEvents(roomId,{onMessage:data => appendMessage(data.message,data.seq),
    onRoomUpdated:() => run(() => refreshRoom()),onPlanConfirmed:() => run(() => refreshRoom()),
    onAgentStatus:() => run(() => refreshRoom()),onReconnect:() => run(() => refreshRoom())});
}


function bindForm(id, task) {
  document.getElementById(id).onsubmit = event => {
    event.preventDefault();
    run(() => task(Object.fromEntries(new FormData(event.target)),event.submitter?.value,event.target));
  };
}
function showUser(user) { setUser(user); html('session',e(user?.name ?? '로그인 전')); }

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
  const id = roomId;
  const result = await requestJson('/api/rooms/' + encodeURIComponent(id) + '/' + path,{method,body});
  if (result.room_id) applyRoomResponse(result,id); else if (id === roomId) await refreshRoom(id);
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
    run(() => roomAction(form.dataset.question ? 'questions/' + encodeURIComponent(form.dataset.question) + '/answer' : 'constraints/' + encodeURIComponent(form.dataset.constraint),{value:readDecisionValue(form)},form.dataset.question ? 'POST' : 'PATCH'));
  });
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-conflict],[data-constraint-confirm]');
    if (!button) return;
    run(() => button.dataset.conflict ? roomAction('conflicts/' + encodeURIComponent(button.dataset.conflict) + '/select',{option_id:button.dataset.option}) : roomAction('constraints/' + encodeURIComponent(button.dataset.constraintConfirm) + '/confirm'));
  });
}

function bindTripInput() {
  document.getElementById('add-cost').onclick = () => appendCost();
  document.addEventListener('click',event => event.target.closest('[data-remove-cost]')?.closest('[data-cost-id]').remove());
  bindForm('trip',async (data,action) => {
    const body = {title:data.title,...readTripConfig(data,readFixedCosts())};
    if (action === 'create') enterRoom(await requestJson('/api/rooms',{method:'POST',body}));
    else {
      delete body.title;
      const baseline = tripBaseline;
      const patch = tripPatch(body,baseline,getSnapshot().config);
      if (!Object.keys(patch).length) return;
      await roomAction('trip',patch,'PATCH');
      if (tripBaseline === baseline) tripBaseline = structuredClone(body);
    }
  });
}

function restoreTrip(snapshot) {
  const form = document.getElementById('trip');
  form.elements.title.value = snapshot.title;
  Object.entries(snapshot.config).forEach(([key,value]) => { if (form.elements[key]) form.elements[key].value = value; });
  ['origin','destination','lodging'].forEach(key => ['label','latitude','longitude'].forEach(field => form.elements[key + '_' + field].value = snapshot.config[key]?.[field] ?? ''));
  html('fixed-costs',''); snapshot.config.fixed_costs.forEach(appendCost);
  tripBaseline = readTripConfig(Object.fromEntries(new FormData(form)),readFixedCosts());
}
function bindHistory() {
  document.getElementById('history').onclick = () => run(async () => {
    const result = await requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/messages?after_seq=0');
    result.messages.forEach(appendMessage);
  });
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-message]');
    if (button) run(async () => {
      appendMessage(await requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/messages/' + encodeURIComponent(button.dataset.message)));
      document.getElementById('message-' + button.dataset.message)?.scrollIntoView({block:'center'});
    });
  });
}

let routeRenderStamp = null;
async function renderMaps(snapshot) {
  const date = getSelectedDay();
  const key = routeKey(snapshot,date);
  if (key === routeRenderStamp) return;
  const plan = displayPlan(snapshot);
  const refs = [...new Set(plan?.days.filter(day => day.date === date).flatMap(day => day.visits.map(visit => visit.place_ref)) ?? [])];
  const details = await Promise.all(refs.map(ref => requestJson('/api/rooms/' + encodeURIComponent(snapshot.room_id) + '/places/' + encodeURIComponent(ref))));
  if (routeKey(getSnapshot() ?? {},getSelectedDay()) !== key) return;
  renderRouteMap(plan,new Map(details.filter(Boolean).map(detail => [detail.place.id,detail.place])),snapshot.config,date);
  routeRenderStamp = key;
  if (getSelectedPlace()) await selectPlace(snapshot.room_id,getSelectedPlace());
  else { renderPlace(null); renderPlaceMap(null); }
}

document.addEventListener('click',event => {
  const button = event.target.closest('[data-place]');
  if (button) run(() => selectPlace(roomId,button.dataset.place));
});

document.getElementById('retry').onclick = () => run(async () => {
  showError(null);
  if (roomId) await refreshRoom();
  else showUser(await requestJson('/api/auth/me'));
});
