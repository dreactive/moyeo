import {runRoomTask,roomLoadRedirect} from './room-errors.js';
import {restoreTripForm,readTripForm,bindFixedCostControls} from './trip-form.js';
import {renderRoutePanel} from './route-view.js';
import {getSelectedDay,setSelectedDay} from './state.js';
import {renderOverview,renderAgentBanner,renderChanged,routeKey,placeVisitDay} from './workspace-view.js';
import {renderChat,isSendKey} from './chat.js';
import {getUser} from './state.js';
import {requireSession,readRoomId,saveRoomId,clearRoomId,navigate,preparePage,signOut,pageUrl} from './session.js';
import {html,escapeHtml as e} from './ui.js';
import {requestJson,getDataMode} from './api.js';
import {applySnapshot,subscribeState,setUser} from './state.js';
import {showError} from './ui.js';
import {getSnapshot,appendMessage,applyRoomResponse} from './state.js';
import {openRoomEvents} from './events.js';
import {withPending} from './ui.js';
import {renderItems,renderConstraints,renderQuestions,renderConflicts,readDecisionValue} from './items.js';
import {renderPlan,displayPlan} from './plan.js';
import {renderCost} from './cost.js';
import {scenarios,replayScenario,setFixtureUser,getFixtureScenario} from './fixture-api.js';
import {tripPatch} from './trip-input.js';
import {initMaps,renderRouteMap,renderPlaceMap} from './map.js';
import {selectPlace,renderPlace} from './place.js';
import {getSelectedPlace} from './state.js';
const run = task => runRoomTask(task,{
  showError,
  expired:expireRoomSession,
  stale:() => roomId ? refreshRoom().catch(showError) : undefined
});
function expireRoomSession() {
  closeEvents();
  html('error',`세션이 만료되었습니다. <a href="${e(pageUrl('/login.html'))}">다시 로그인해 주세요.</a>`);
}
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
  renderChanged('plan',[shared,getUser()?.id],() => { renderPlan(snapshot); renderCost(displayPlan(snapshot)?.cost,getUser()?.id,snapshot.members); });
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
  if (!roomUiBound) {
    initMaps({routeElement:document.getElementById('route-map'),placeElement:document.getElementById('place-map'),appKey:document.querySelector('meta[name="kakao-map-app-key"]').content});
    bindSessionActions(); bindChatKeys(); bindFixtureControls(); bindPlanActions(); bindDecisionActions(); bindTripInput(); bindSettingsDialog(); bindInviteCopy(); bindRoomLifecycle(); bindHistory();
    subscribeState(snapshot => snapshot && renderRoom(snapshot));
    roomUiBound = true;
  }
  setUser(user);
  html('session', e(user.name));
  if (getDataMode() === 'fixture') {
    document.getElementById('fixture-user').value = user.id;
    document.getElementById('scenario').value = getFixtureScenario();
  }
  await openSavedRoom(savedRoom);
}
async function openSavedRoom(id) {
  try { enterRoom(await requestJson('/api/rooms/' + encodeURIComponent(id))); }
  catch (error) {
    const destination = roomLoadRedirect(error);
    if (!destination) throw error;
    clearRoomId();
    navigate(destination);
  }
}
run(startRoomApp);
let roomUiBound = false;
let closeEvents = () => {};
let roomId = null;
let tripBaseline = {};
export async function refreshRoom(id = roomId) {
  const snapshot = await requestJson('/api/rooms/' + encodeURIComponent(id));
  if (id === roomId) applyRoomResponse(snapshot,id);
}
export function enterRoom(snapshot) {
  closeEvents();
  routeRenderStamp = null;
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
    run(() => withPending(event.submitter,() => task(Object.fromEntries(new FormData(event.target)),event.submitter?.value,event.target)));
  };
}
function showUser(user) { setUser(user); html('session',e(user?.name ?? '로그인 전')); }

function bindSessionActions() {
  document.getElementById('logout').onclick = () => run(async () => {
    await signOut();
    closeEvents(); roomId = null;
    applySnapshot(null); showUser(null);
  });
  bindForm('message',async (body, action,form) => {
    if (!roomId) throw new Error('먼저 방에 입장하세요.');
    appendMessage(await requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/messages',{method:'POST',body}));
    form.reset();
  });
}

function bindChatKeys() {
  const form = document.getElementById('message');
  form.elements.text.onkeydown = event => {
    if (isSendKey(event)) { event.preventDefault(); form.requestSubmit(); }
  };
  document.getElementById('new-messages').onclick = event => {
    const list = document.getElementById('messages');
    list.scrollTop = list.scrollHeight;
    event.currentTarget.hidden = true;
  };
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
    run(() => withPending(button,() => roomAction('plan/' + action,action === 'activate' ? {plan_revision:snapshot.current_plan.plan_revision} : {target:displayPlan(snapshot).confirmation_target})));
  });
  document.getElementById('replan').onclick = event => run(() => withPending(event.currentTarget,() => roomAction('agent-runs',{reason:'manual_replan'})));
}

function bindDecisionActions() {
  document.addEventListener('submit',event => {
    const form = event.target;
    if (!form.dataset.question && !form.dataset.constraint) return;
    event.preventDefault();
    run(() => withPending(event.submitter,async () => {
      await roomAction(form.dataset.question ? 'questions/' + encodeURIComponent(form.dataset.question) + '/answer' : 'constraints/' + encodeURIComponent(form.dataset.constraint),{value:readDecisionValue(form)},form.dataset.question ? 'POST' : 'PATCH');
      if (form.contains(document.activeElement)) document.activeElement.blur();
    }));
  });
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-conflict],[data-constraint-confirm]');
    if (!button) return;
    run(() => withPending(button,() => button.dataset.conflict ? roomAction('conflicts/' + encodeURIComponent(button.dataset.conflict) + '/select',{option_id:button.dataset.option}) : roomAction('constraints/' + encodeURIComponent(button.dataset.constraintConfirm) + '/confirm')));
  });
}

function bindInviteCopy() {
  const button = document.getElementById('copy-invite');
  button.onclick = () => run(() => withPending(button,async () => {
    try { await navigator.clipboard.writeText(getSnapshot().invite_code); }
    catch { throw new Error('초대 코드를 직접 선택해 복사해 주세요.'); }
    button.textContent = '복사됨';
  }));
}

function bindRoomLifecycle() {
  globalThis.addEventListener?.('pagehide',() => closeEvents());
  document.addEventListener('focusout',() => queueMicrotask(() => {
    const snapshot = getSnapshot();
    if (snapshot) renderRoom(snapshot);
  }));
}

function bindSettingsDialog() {
  const dialog = document.getElementById('trip-settings');
  document.getElementById('open-settings').onclick = () => {
    restoreTrip(getSnapshot());
    dialog.showModal();
  };
  dialog.querySelector('[data-close-settings]').onclick = () => dialog.close();
}

function bindTripInput() {
  bindFixedCostControls();
  bindForm('trip',async (data,action,form) => {
    const body = readTripForm(form);
    {
      delete body.title;
      const baseline = tripBaseline;
      const patch = tripPatch(body,baseline,getSnapshot().config);
      if (!Object.keys(patch).length) { document.getElementById('trip-settings').close(); return; }
      await roomAction('trip',patch,'PATCH');
      if (tripBaseline === baseline) tripBaseline = structuredClone(body);
      document.getElementById('trip-settings').close();
    }
  });
}

function restoreTrip(snapshot) {
  tripBaseline = restoreTripForm(snapshot);
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
document.getElementById('route-load-status').onclick = event => {
  if (!event.target.closest('[data-route-retry]')) return;
  const snapshot = getSnapshot();
  if (snapshot) return run(() => renderMaps(snapshot,true));
};
export async function renderMaps(snapshot, retry = false) {
  const date = getSelectedDay();
  const key = routeKey(snapshot,date);
  const sameRoute = key === routeRenderStamp?.key;
  if ((!retry && sameRoute) || routeKey(getSnapshot() ?? {},date) !== key) return;
  const plan = displayPlan(snapshot);
  html('route-load-status','');
  if (!sameRoute) renderRouteMap(plan,new Map(),snapshot.config,date);
  const refs = [...new Set(plan?.days.filter(day => day.date === date).flatMap(day => day.visits.map(visit => visit.place_ref)) ?? [])];
  const stamp = {key};
  routeRenderStamp = stamp;
  const results = await Promise.allSettled(refs.map(ref => requestJson('/api/rooms/' + encodeURIComponent(snapshot.room_id) + '/places/' + encodeURIComponent(ref))));
  if (routeRenderStamp !== stamp || routeKey(getSnapshot() ?? {},getSelectedDay()) !== key) return;
  const expired = results.find(result => result.status === 'rejected' && result.reason.status === 401);
  if (expired) throw expired.reason;
  const places = results.flatMap(result => result.status === 'fulfilled' && result.value?.place ? [result.value.place] : []);
  if (places.length) renderRouteMap(plan,new Map(places.map(place => [place.id,place])),snapshot.config,date);
  if (places.length < refs.length) {
    const note = places.length ? '일부 장소 좌표를 불러오지 못했어요.' : '장소 좌표를 불러오지 못했어요.';
    html('route-load-status',`<p>${note}</p><button type="button" data-route-retry>좌표 다시 불러오기</button>`);
  }
  if (getSelectedPlace()) await selectPlace(snapshot.room_id,getSelectedPlace());
  else { renderPlace(null); renderPlaceMap(null); }
}

function focusRoutePlace(ref) {
  const snapshot = getSnapshot();
  const day = placeVisitDay(displayPlan(snapshot),ref,getSelectedDay());
  if (!day) return;
  setSelectedDay(day.date);
  renderRoom(snapshot);
  document.getElementById('route-map').scrollIntoView({block:'center',behavior:'smooth'});
}

document.addEventListener('click',event => {
  const place = event.target.closest('[data-route-place]');
  if (place) focusRoutePlace(place.dataset.routePlace);
  const day = event.target.closest('[data-day]');
  if (day) { setSelectedDay(day.dataset.day); renderRoom(getSnapshot()); }
  const button = event.target.closest('[data-place]');
  if (button) run(() => selectPlace(roomId,button.dataset.place));
});

document.getElementById('retry').onclick = () => run(async () => {
  showError(null);
  if (roomId) await refreshRoom();
  else await startRoomApp();
});
