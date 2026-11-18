import {html,escapeHtml as e,avatar,money} from './ui.js';
import {requestJson,getDataMode} from './api.js';
import {applySnapshot,subscribeState,setUser,getUser} from './state.js';
import {showError} from './ui.js';
import {getSnapshot,appendMessage,applyRoomResponse} from './state.js';
import {openRoomEvents} from './events.js';
import {withPending,runFormAction} from './ui.js';
import {runRoomTask,roomLoadRedirect} from './room-errors.js';
import {requireSession,readRoomId,saveRoomId,clearRoomId,navigate,preparePage,signOut,pageUrl} from './session.js';
import {renderChanged,sharedRenderData,routeKey,placeVisitDay,agentLabels,requestProgress,latestCalculations} from './workspace-view.js';
import {renderRoutePanel} from './route-view.js';
import {getSelectedDay,setSelectedDay} from './state.js';
import {renderGroupedChat,isSendKey,sendChatMessage} from './chat.js';
import {enhanceAnchorPickers,refreshAnchorSummaries} from './place-picker.js';
import {unreadCount} from './chat-unread.js';
import {mergeMessages,groupByDay,monthGrid,monthKey,shiftMonth} from './chat-dates.js';
import {initChatBubble} from './chat-bubble.js';
import {renderItems,renderConstraints,renderQuestions,renderConflicts,readDecisionValue} from './items.js';
import {renderPlan,displayPlan,planAgreement} from './plan.js';
import {renderCost} from './cost.js';
import {scenarios,replayScenario,setFixtureUser,getFixtureScenario} from './fixture-api.js';
import {readTripConfig,requireTripBasics,tripPatch} from './trip-input.js';
import {appendCost,readFixedCosts,refreshCostOwners} from './fixed-costs.js';
import {initMaps,renderRouteMap,renderPlaceMap,hasCoordinates,locatedMentions} from './map.js';
import {selectPlace,renderPlace,renderSelectedPlaceAgreement} from './place.js';
import {planItemAgreements} from './agreement.js';
import {getSelectedPlace} from './state.js';
const stateLabel = {idle:'대기',running:'진행 중',needs_input:'입력 필요',done:'완료',waiting:'대기 중',failed:'일부 실패',held:'보류 중'};
const run = task => runRoomTask(task,{
  showError,
  expired:expireRoomSession,
  stale:() => roomId ? refreshRoom().catch(showError) : undefined
});
export function expireRoomSession() {
  roomSessionExpired = true;
  closeEvents();
  const dialog = document.getElementById('setup-dialog');
  if (dialog?.open) dialog.close();
  html('error',`세션이 만료되었습니다. <a href="${e(pageUrl('/login.html'))}">다시 로그인해 주세요.</a>`);
}
export function renderDecisionRegions(snapshot) {
  renderChanged('decisions',[sharedRenderData(snapshot),getUser()?.id],() => {
    if (document.activeElement?.closest('#constraints form,#questions form') || document.querySelector('#constraints [data-pending],#questions [data-pending],#conflicts [data-pending]')) return false;
    renderItems(snapshot); renderConstraints(snapshot); renderQuestions(snapshot); renderConflicts(snapshot);
  });
}
export function renderRoom(snapshot) {
  if (!snapshot) return;
  syncSetupDialog(snapshot);
  refreshCostOwners(snapshot.members);
  const shared = sharedRenderData(snapshot);
  const plan = displayPlan(snapshot);
  const {count,status} = planAgreement(snapshot,plan);
  renderDecisionRegions(snapshot);
  renderChanged('plan',[shared,getUser()?.id],() => {
    if (document.querySelector('#plan [data-pending]')) return false;
    renderPlan(snapshot);
  });
  renderChanged('cost',[snapshot.room_id,plan?.confirmation_target,plan?.cost,count,status,snapshot.versions,snapshot.agent_results,snapshot.members,getUser()?.id],
    () => renderCost(plan?.cost,getUser()?.id,snapshot.members,snapshot));
  renderChanged('route-panel',[shared,getSelectedDay()],() => renderRoutePanel(snapshot,getSelectedDay()));
  renderChanged('place-agreement',[snapshot.room_id,plan,snapshot.items,snapshot.confirmed_plan,snapshot.versions,snapshot.agent_results,snapshot.agent_requests,getSelectedPlace()],
    () => renderSelectedPlaceAgreement(snapshot));
  run(() => renderMaps(snapshot)); run(() => fillMenuChoices(snapshot.room_id));
  enhanceAnchorPickers(mapKey,document.getElementById('questions')).catch(() => {});
  chatDays = groupByDay(mergeMessages(olderMessages.get(snapshot.room_id) ?? [],snapshot.messages));
  renderChanged('chat',[snapshot.room_id,chatDays,snapshot.members,getUser()?.id],() => renderGroupedChat({...snapshot,messages:mergeMessages(olderMessages.get(snapshot.room_id) ?? [],snapshot.messages)},getUser()?.id));
  updateChatUnread(snapshot);
  const ownerId = snapshot.owner_id ?? snapshot.members[0]?.user_id;
  html('chat-count', `<button type="button" class="people-toggle" aria-expanded="${peopleOpen}" aria-controls="people-list">참여자 ${snapshot.members.length}명<span aria-hidden="true">${peopleOpen ? '▴' : '▾'}</span></button>`);
  const people = document.getElementById('people-list');
  people.hidden = !peopleOpen;
  people.innerHTML = `<p class="people-title">이 방에 있는 사람</p><ul>${snapshot.members.map(member => `<li>${avatar(member.name)}<span class="people-name">${e(member.name)}${member.user_id === getUser()?.id ? ' <small>(나)</small>' : ''}</span>${member.user_id === ownerId ? '<span class="tag owner">방장</span>' : ''}</li>`).join('')}</ul>`;
  html('room-heading', e(snapshot.title));
  document.title = snapshot.title + ' · 모여';
  const titleInput = document.querySelector('#trip [name=title]');
  const isOwner = ownerId === getUser()?.id;
  if (titleInput && snapshot.title !== titleBaseline && (titleInput.value === titleBaseline || !isOwner)) { titleInput.value = snapshot.title; titleBaseline = snapshot.title; }
  if (titleInput) {
    titleInput.readOnly = !isOwner;
    titleInput.title = isOwner ? '' : '채팅방 이름은 방장만 바꿀 수 있어요';
    const hint = document.getElementById('title-owner-hint');
    if (hint) hint.hidden = isOwner;
  }
  html('invite-box', `<span class="invite-label">초대 코드</span><strong class="invite-code">${e(snapshot.invite_code)}</strong><button type="button" class="ghost sm" data-copy-invite="${e(snapshot.invite_code)}">초대 코드 복사</button>`);
  const config = snapshot.config;
  const missingBasics = config.per_person_budget_krw == null || !config.region;
  html('trip-meta', [config.start_date && config.end_date ? config.start_date + ' — ' + config.end_date : '날짜 미정', config.region || '지역 미정', '자동차', config.per_person_budget_krw == null ? '1인 예산 미정' : '1인 예산 ' + money(config.per_person_budget_krw)].map(e).join(' · ')
    + (missingBasics ? ' <button type="button" class="accent sm" data-open-trip>여행 조건 정하기</button>' : ''));
  html('members', `<span class="muted">${snapshot.members.length}명이 함께하는 중</span><span class="avatar-stack">${snapshot.members.map(member => avatar(member.name)).join('')}</span>`);
  const requestMessages = new Set(snapshot.agent_requests?.map(request => request.source_message_id));
  renderChanged('agent',[shared,snapshot.agent_status,snapshot.messages.filter(message => requestMessages.has(message.id))],
    () => renderRoomAgent(snapshot));
  syncReplanButton(snapshot);
  html('route-badge', displayPlan(snapshot) ? '여행안 r' + e(displayPlan(snapshot).plan_revision) : '여행안 없음');
}
export function renderRoomAgent(snapshot) {
  const status = snapshot.agent_status;
  const steps = {idle:['대기'],running:['조건 반영','조사·계산 중'],needs_input:['조건 반영','입력이 필요해요'],done:['조건 반영','동선·경비 검토','참가자 동의 대기'],
    waiting:['조건 반영','남은 작업 대기'],failed:['조건 반영','일부 작업 실패'],held:['조건 반영','최신 내용 확인 중']}[status.state] ?? [stateLabel[status.state] ?? status.state];
  const label = !status.label || status.label === status.state || status.label === 'Ready' ? agentLabels[status.state] ?? status.state : status.label;
  const questions = snapshot.questions.filter(item => item.status === 'open').length;
  const conflicts = snapshot.conflicts.filter(item => item.status === 'open').length;
  html('agent', `<strong>${e(label)}</strong><span class="state state-${e(status.state)}" title="${e(status.state)}">${e(stateLabel[status.state] ?? status.state)}</span>
  <p class="steps">${steps.map((step,index) => `<span class="${index < steps.length - 1 || status.state === 'done' ? 'done' : 'now'}">${e(step)}</span>`).join('<i>›</i>')}</p>
  <p>확인 질문 ${questions}개 · 해결할 충돌 ${conflicts}개</p>${requestProgress(snapshot)}${latestCalculations(snapshot)}`);
  syncReplanButton(snapshot);
}
function syncReplanButton(snapshot) {
  const replan = document.getElementById('replan');
  replan.disabled = snapshot.agent_status.state === 'running' || replan.dataset.pending === 'true';
}
let mapKey = '';
let peopleOpen = false;
let bubble = null;
let roomUiBound = false;
export async function startRoomApp() {
  preparePage();
  const user = await requireSession();
  if (!user) return;
  roomSessionExpired = false;
  showUser(user);
  if (!roomUiBound) {
    bubble = initChatBubble({launcher:document.getElementById('chat-launcher'),panel:document.getElementById('chat-panel')});
    const appKey = document.querySelector('meta[name="kakao-map-app-key"]').content;
    initMaps({routeElement:document.getElementById('route-map'),placeElement:document.getElementById('place-map'),appKey});
    mapKey = appKey;
    enhanceAnchorPickers(appKey).catch(() => {});
    bindSessionActions(); bindChatKeys(); bindFixtureControls(); bindPlanActions(); bindDecisionActions(); bindTripInput(); bindSetupDialog(); bindHistory(); bindRoomLifecycle();
    subscribeState(snapshot => snapshot && renderRoom(snapshot));
    roomUiBound = true;
  }
  if (getDataMode() === 'fixture') {
    document.getElementById('fixture-user').value = user.id;
    document.getElementById('scenario').value = getFixtureScenario();
  }
  const params = new URLSearchParams(location.search);
  const invite = params.get('invite');
  if (invite && getDataMode() !== 'fixture') return enterRoom(await requestJson('/api/rooms/join',{method:'POST',body:{invite_code:invite}}));
  const target = params.get('room') || readRoomId();
  if (!target) return navigate('/rooms.html');
  try { enterRoom(await requestJson('/api/rooms/' + encodeURIComponent(target))); }
  catch (error) {
    const destination = roomLoadRedirect(error);
    if (!destination) throw error;
    clearRoomId();
    navigate(destination);
  }
}
run(startRoomApp);
let closeEvents = () => {};
let roomId = null;
let roomSessionExpired = false;
let tripBaseline = {};
let titleBaseline = '';
export async function refreshRoom(id = roomId) {
  const snapshot = await requestJson('/api/rooms/' + encodeURIComponent(id));
  if (id === roomId) applyRoomResponse(snapshot,id);
}
let saveTimer = null;
function showSaved() {
  const status = document.getElementById('trip-save-status');
  status.textContent = '설정 저장됨';
  status.classList.add('show');
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => { status.classList.remove('show'); status.textContent = ''; },2500);
}
let chatOpen = false;
let chatSeenId = null;
const olderMessages = new Map();
let chatDays = [];
async function loadAllMessages(id) {
  if (getDataMode() === 'fixture') return;
  const result = await requestJson('/api/rooms/' + encodeURIComponent(id) + '/messages?after_seq=0');
  if (id !== roomId) return;
  olderMessages.set(id,result.messages);
  const snapshot = getSnapshot();
  if (snapshot) renderRoom(snapshot);
}
let calendarMonth = null;
function drawCalendar() {
  const available = new Set(chatDays.map(day => day.key));
  const months = chatDays.map(day => monthKey(day.key));
  const [year,month] = calendarMonth.split('-').map(Number);
  const prev = shiftMonth(calendarMonth,-1), next = shiftMonth(calendarMonth,1);
  const cell = day => {
    if (!day) return '<td></td>';
    const key = `${calendarMonth}-${String(day).padStart(2,'0')}`;
    return available.has(key)
      ? `<td><button type="button" class="has-chat" data-jump-day="${key}" aria-label="${month}월 ${day}일 대화로 이동">${day}</button></td>`
      : `<td><button type="button" disabled aria-label="${month}월 ${day}일 대화 없음">${day}</button></td>`;
  };
  document.getElementById('date-menu').innerHTML = `<div class="cal-head">
    <button type="button" class="cal-nav" data-cal-month="${prev}" ${months[0] > prev ? 'disabled' : ''} aria-label="이전 달">‹</button>
    <strong>${year}년 ${month}월</strong>
    <button type="button" class="cal-nav" data-cal-month="${next}" ${months.at(-1) < next ? 'disabled' : ''} aria-label="다음 달">›</button></div>
  <table class="cal"><thead><tr>${['일','월','화','수','목','금','토'].map(name => `<th scope="col">${name}</th>`).join('')}</tr></thead>
  <tbody>${monthGrid(year,month).map(week => `<tr>${week.map(cell).join('')}</tr>`).join('')}</tbody></table>`;
}
function openDateMenu(anchor) {
  const menu = document.getElementById('date-menu');
  calendarMonth = monthKey(anchor.closest('.date-sep')?.id.replace('day-','') ?? chatDays.at(-1)?.key ?? '');
  drawCalendar();
  const panel = document.getElementById('chat-panel').getBoundingClientRect();
  const box = anchor.getBoundingClientRect();
  menu.style.top = Math.max(56,box.bottom - panel.top + 4) + 'px';
  menu.hidden = false;
  menu.querySelector('.has-chat')?.focus();
}
function closeDateMenu() { const menu = document.getElementById('date-menu'); if (menu) menu.hidden = true; }
document.addEventListener('click',event => {
  const monthButton = event.target.closest('[data-cal-month]');
  if (monthButton) { calendarMonth = monthButton.dataset.calMonth; drawCalendar(); return; }
  const opener = event.target.closest('[data-date-menu]');
  const jump = event.target.closest('[data-jump-day]');
  if (opener) return openDateMenu(opener);
  if (jump) {
    closeDateMenu();
    const target = document.getElementById('day-' + jump.dataset.jumpDay);
    const list = document.getElementById('messages');
    if (target) list.scrollTo({top:target.offsetTop - list.offsetTop,behavior:'smooth'});
    target?.classList.remove('flash'); void target?.offsetWidth; target?.classList.add('flash');
    return;
  }
  if (!event.target.closest('#date-menu')) closeDateMenu();
});
document.addEventListener('keydown',event => { if (event.key === 'Escape' && !document.getElementById('date-menu')?.hidden) { event.stopPropagation(); closeDateMenu(); } },true);
function updateChatUnread(snapshot) {
  const last = snapshot.messages.at(-1)?.id ?? '';
  if (chatOpen || chatSeenId === null) chatSeenId = last;
  const count = chatOpen ? 0 : unreadCount(snapshot.messages,chatSeenId,getUser()?.id);
  const badge = document.getElementById('chat-unread');
  badge.hidden = !count;
  badge.textContent = count > 99 ? '99+' : String(count);
  document.getElementById('chat-launcher').setAttribute('aria-label',count ? `채팅방 열기, 새 메시지 ${count}개` : '채팅방 열기');
}
function scrollChatToEnd() { const list = document.getElementById('messages'); list.scrollTop = list.scrollHeight; }
function setChatOpen(open,focus = true) {
  chatOpen = open;
  try { sessionStorage.setItem('chat-open',open ? '1' : '0'); } catch {}
  const panel = document.getElementById('chat-panel');
  const launcher = document.getElementById('chat-launcher');
  panel.hidden = !open;
  bubble?.update();
  launcher.setAttribute('aria-expanded',String(open));
  launcher.classList.toggle('open',open);
  if (open) {
    chatSeenId = getSnapshot()?.messages.at(-1)?.id ?? chatSeenId;
    const badge = document.getElementById('chat-unread'); badge.hidden = true;
    scrollChatToEnd();
    if (focus) document.getElementById('message-text').focus();
  } else if (focus) launcher.focus();
}
document.addEventListener('click',event => {
  if (event.target.closest('#chat-launcher')) { if (!bubble?.wasDragged()) setChatOpen(!chatOpen); }
  else if (event.target.closest('[data-chat-close]')) setChatOpen(false);
});
document.addEventListener('keydown',event => {
  if (event.key === 'Escape' && chatOpen && !peopleOpen && document.getElementById('chat-panel').contains(document.activeElement)) setChatOpen(false);
});
export function enterRoom(snapshot) {
  closeEvents();
  roomSessionExpired = false;
  routeRenderStamp = null;
  roomId = snapshot.room_id;
  chatSeenId = null;
  restoreTrip(snapshot);
  saveRoomId(roomId);
  if (getDataMode() !== 'fixture') {
    const url = new URL(location.href);
    url.searchParams.delete('invite'); url.searchParams.set('room',roomId);
    history.replaceState(null,'',url.pathname + url.search);
  }
  applySnapshot(snapshot);
  let restore = false; try { restore = sessionStorage.getItem('chat-open') === '1'; } catch {}
  setChatOpen(restore,false);
  run(() => loadAllMessages(roomId));
  closeEvents = openRoomEvents(roomId,{onMessage:data => appendMessage(data.message,data.seq),
    onRoomUpdated:() => run(() => refreshRoom()),onPlanConfirmed:() => run(() => refreshRoom()),
    onAgentStatus:() => run(() => refreshRoom()),onReconnect:() => run(() => refreshRoom()),
    onRoomDeleted:() => { closeEvents(); clearRoomId(); navigate('/rooms.html?deleted=1'); }});
}


function bindForm(id, task) {
  document.getElementById(id).onsubmit = event => {
    event.preventDefault();
    return run(() => runFormAction(event,() => task(Object.fromEntries(new FormData(event.target)),event.submitter?.value,event.target)));
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
    appendMessage(await sendChatMessage(form,payload => requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/messages',{method:'POST',body:payload})));
  });
}
function bindChatKeys() {
  const form = document.getElementById('message');
  form.elements.text.onkeydown = event => {
    if (isSendKey(event)) { event.preventDefault(); form.requestSubmit(form.querySelector('button[type=submit],button:not([type])')); }
  };
  document.getElementById('new-messages').onclick = event => {
    scrollChatToEnd();
    event.currentTarget.hidden = true;
  };
}
export function bindRoomLifecycle() {
  globalThis.addEventListener?.('pagehide',() => closeEvents());
  document.addEventListener('focusout',event => {
    if (!event.target.closest('#constraints form,#questions form')) return;
    queueMicrotask(() => {
      const snapshot = getSnapshot();
      if (!snapshot) return;
      renderDecisionRegions(snapshot);
      run(() => fillMenuChoices(snapshot.room_id));
      enhanceAnchorPickers(mapKey,document.getElementById('questions')).catch(() => {});
    });
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
    run(() => withPending(button,() => roomAction('plan/' + action,action === 'activate' ? {plan_revision:snapshot.current_plan.plan_revision} : {target:displayPlan(snapshot).confirmation_target})).finally(() => renderRoom(getSnapshot())));
  });
  document.getElementById('replan').onclick = event => {
    const button = event.currentTarget;
    return run(() => withPending(button,() => roomAction('agent-runs',{reason:'manual_replan'})).finally(() => renderRoom(getSnapshot())));
  };
}

function bindDecisionActions() {
  document.addEventListener('submit',event => {
    const form = event.target;
    if (!form.dataset.question && !form.dataset.constraint) return;
    event.preventDefault();
    run(() => runFormAction(event,async () => {
      await roomAction(form.dataset.question ? 'questions/' + encodeURIComponent(form.dataset.question) + '/answer' : 'constraints/' + encodeURIComponent(form.dataset.constraint),{value:readDecisionValue(form)},form.dataset.question ? 'POST' : 'PATCH');
      if (form.contains(document.activeElement)) document.activeElement.blur();
    }).finally(() => renderRoom(getSnapshot())));
  });
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-conflict],[data-constraint-confirm]');
    if (!button) return;
    run(() => withPending(button,() => button.dataset.conflict ? roomAction('conflicts/' + encodeURIComponent(button.dataset.conflict) + '/select',{option_id:button.dataset.option}) : roomAction('constraints/' + encodeURIComponent(button.dataset.constraintConfirm) + '/confirm')).finally(() => renderRoom(getSnapshot())));
  });
}

function bindTripInput() {
  document.getElementById('add-cost').onclick = () => appendCost();
  document.addEventListener('click',event => event.target.closest('[data-remove-cost]')?.closest('[data-cost-id]').remove());
  bindForm('trip',async (data,action) => {
    const body = requireTripBasics(readTripConfig(data,readFixedCosts()));
    {
      const baseline = tripBaseline;
      const patch = tripPatch(body,baseline,getSnapshot().config);
      const title = String(data.title ?? '').trim();
      if (!title) throw new Error('채팅방 이름을 입력하세요.');
      if (title !== titleBaseline) patch.title = title;
      if (!Object.keys(patch).length) return showSaved();
      await roomAction('trip',patch,'PATCH');
      if (tripBaseline === baseline) tripBaseline = structuredClone(body);
      if (patch.title) titleBaseline = patch.title;
      showSaved();
    }
  });
}

// The owner must set the room name and per-person budget before the room starts.
const needsSetup = snapshot => getDataMode() !== 'fixture' && !!snapshot
  && (snapshot.config.per_person_budget_krw == null || !snapshot.config.region) && (snapshot.owner_id ?? snapshot.members[0]?.user_id) === getUser()?.id;
let setupRoomId = null;
export function syncSetupDialog(snapshot) {
  const dialog = document.getElementById('setup-dialog');
  if (!dialog) return;
  if (roomSessionExpired || !needsSetup(snapshot)) { if (dialog.open) dialog.close(); setupRoomId = null; return; }
  const form = document.getElementById('setup-form');
  if (setupRoomId !== snapshot.room_id) {
    form.reset(); form.elements.title.value = snapshot.title;
    setupRoomId = snapshot.room_id;
  }
  html('setup-count', `${snapshot.members.length}명`);
  html('setup-members', snapshot.members.map(member => `<li>${avatar(member.name)}<span>${e(member.name)}${member.user_id === getUser()?.id ? ' <small class="muted">(나 · 방장)</small>' : ''}</span></li>`).join(''));
  html('setup-invite', `초대 코드 <strong>${e(snapshot.invite_code)}</strong>를 공유하면 더 들어올 수 있어요.`);
  if (!dialog.open) { dialog.showModal?.() ?? dialog.setAttribute('open',''); ([form.elements.title,form.elements.region,form.elements.per_person_budget_krw].find(input => !input.value.trim()) ?? form.elements.title).focus(); }
}
function bindSetupDialog() {
  const dialog = document.getElementById('setup-dialog');
  if (!dialog) return;
  dialog.addEventListener('cancel',event => event.preventDefault());
  const error = document.getElementById('setup-error');
  const fail = (message,input) => { error.textContent = message; error.hidden = false; input?.focus(); };
  document.getElementById('setup-form').addEventListener('submit',event => {
    event.preventDefault();
    const form = event.target, title = form.elements.title.value.trim(), region = form.elements.region.value.trim(), budgetText = form.elements.per_person_budget_krw.value.trim();
    if (form.querySelector('button[type=submit]').disabled) return;
    error.hidden = true;
    if (!title) return fail('채팅방 이름을 입력하세요.',form.elements.title);
    if (!region) return fail('도시를 입력하세요.',form.elements.region);
    const budget = Number(budgetText);
    if (!budgetText || !Number.isInteger(budget) || budget < 0) return fail('1인 전체 예산을 0 이상의 정수로 입력하세요.',form.elements.per_person_budget_krw);
    const button = form.querySelector('button[type=submit]');
    const snapshot = getSnapshot();
    const patch = {region,per_person_budget_krw:budget,...(title !== snapshot.title ? {title} : {})};
    run(() => withPending(button,async () => {
      try {
        await roomAction('trip',patch,'PATCH');
        restoreTrip(getSnapshot());
        syncSetupDialog(getSnapshot());
        showSaved();
      } catch (problem) {
        fail(problem.message || '저장하지 못했어요. 다시 시도해 주세요.');
        throw problem;
      }
    }));
  });
}

export function restoreTrip(snapshot) {
  const form = document.getElementById('trip');
  form.elements.title.value = snapshot.title;
  titleBaseline = snapshot.title;
  document.title = snapshot.title + ' · 모여';
  Object.entries(snapshot.config).forEach(([key,value]) => { if (form.elements[key]) form.elements[key].value = value; });
  ['lodging'].forEach(key => ['label','latitude','longitude','source_ref'].forEach(field => { if (form.elements[key + '_' + field]) form.elements[key + '_' + field].value = snapshot.config[key]?.[field] ?? ''; }));
  refreshAnchorSummaries();
  html('fixed-costs',''); snapshot.config.fixed_costs.forEach(line => appendCost(line,snapshot.members));
  tripBaseline = readTripConfig(Object.fromEntries(new FormData(form)),readFixedCosts());
}
function bindHistory() {
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-message]');
    if (button) run(async () => {
      setChatOpen(true,false);
      appendMessage(await requestJson('/api/rooms/' + encodeURIComponent(roomId) + '/messages/' + encodeURIComponent(button.dataset.message)));
      const target = document.getElementById('message-' + button.dataset.message);
      target?.scrollIntoView({block:'center',behavior:'smooth'});
      target?.classList.remove('flash'); void target?.offsetWidth; target?.classList.add('flash');
    });
  });
}

let routeRenderStamp = null;
document.getElementById('route-load-status').onclick = event => {
  if (!event.target.closest('[data-route-retry]')) return;
  const snapshot = getSnapshot();
  if (snapshot) return run(() => renderMaps(snapshot,true));
};
export async function renderMaps(snapshot,retry = false) {
  const date = getSelectedDay();
  const key = routeKey(snapshot,date);
  const sameRoute = key === routeRenderStamp?.key;
  if (routeKey(getSnapshot() ?? {},date) !== key) return;
  const plan = displayPlan(snapshot);
  const mentions = locatedMentions(snapshot,plan);
  const agreement = JSON.stringify([[...planItemAgreements(snapshot,plan)],mentions]);
  if (!retry && sameRoute) {
    if (agreement !== routeRenderStamp.agreement) {
      routeRenderStamp.agreement = agreement;
      renderRouteMap(plan,routeRenderStamp.places,snapshot.config,date,snapshot);
    }
    return;
  }
  html('route-load-status','');
  const stamp = {key,agreement,places:sameRoute ? routeRenderStamp.places : new Map()};
  if (!sameRoute) renderRouteMap(plan,stamp.places,snapshot.config,date,snapshot);
  const visits = plan?.days.filter(day => day.date === date).flatMap(day => day.visits.map(visit => visit.place_ref)) ?? [];
  const refs = [...new Set([...visits,...mentions.map(m => m.ref)])];
  routeRenderStamp = stamp;
  const results = await Promise.allSettled(refs.map(ref => requestJson('/api/rooms/' + encodeURIComponent(snapshot.room_id) + '/places/' + encodeURIComponent(ref) + '?location_only=true')));
  const current = getSnapshot();
  if (routeRenderStamp !== stamp || routeKey(current ?? {},getSelectedDay()) !== key) return;
  const expired = results.find(result => result.status === 'rejected' && result.reason.status === 401);
  if (expired) throw expired.reason;
  const places = results.flatMap(result => result.status === 'fulfilled' && result.value?.place ? [result.value.place] : []);
  stamp.places = new Map([...stamp.places,...places.map(place => [place.id,place])]);
  renderRouteMap(displayPlan(current),stamp.places,current.config,date,current);
  const located = [...stamp.places.values()].filter(hasCoordinates).length;
  if (located < refs.length) {
    const note = located ? '일부 장소 좌표를 불러오지 못했어요.' : '장소 좌표를 불러오지 못했어요.';
    html('route-load-status',`<p>${note}</p><button type="button" data-route-retry>좌표 다시 불러오기</button>`);
  }
  if (getSelectedPlace()) await selectPlace(current.room_id,getSelectedPlace());
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

const menuCache = new Map();
export async function fillMenuChoices(id) {
  for (const select of document.querySelectorAll('select[data-menu-place]')) {
    const ref = select.dataset.menuPlace;
    if (!ref) continue;
    const key = id + '|' + ref;
    if (select.dataset.menuLoaded === key) continue;
    if (!menuCache.has(key)) menuCache.set(key, requestJson('/api/rooms/' + encodeURIComponent(id) + '/places/' + encodeURIComponent(ref)).catch(error => { menuCache.delete(key); throw error; }));
    const details = await menuCache.get(key);
    if (!select.isConnected || select.dataset.menuLoaded === key) continue;
    select.innerHTML = details.menus.length ? details.menus.map(menu => `<option value="${e(menu.id)}">${e(menu.name)} · ${menu.price_krw == null ? e(menu.price_text || '가격 미확인') : money(menu.price_krw)}</option>`).join('') : '<option value="">등록된 메뉴 없음</option>';
    select.dataset.menuLoaded = key;
  }
}
document.addEventListener('submit',() => showError(null),true);
document.addEventListener('click',event => { if (event.target.closest('button')) showError(null); },true);
document.addEventListener('click',event => {
  const button = event.target.closest('[data-copy-invite]');
  if (!button) return;
  const code = button.dataset.copyInvite;
  navigator.clipboard?.writeText(code).then(() => { button.textContent = '복사됨'; setTimeout(() => { button.textContent = '초대 코드 복사'; },1500); },() => prompt('초대 코드',code));
});
document.addEventListener('click',event => {
  if (!event.target.closest('[data-open-trip]')) return;
  const panel = document.getElementById('trip-settings');
  panel.scrollIntoView({block:'start',behavior:'smooth'});
  (panel.querySelector('#trip :invalid') ?? panel.querySelector('[name=per_person_budget_krw]'))?.focus({preventScroll:true});
});
document.addEventListener('click',event => {
  const toggle = event.target.closest('.people-toggle');
  const list = document.getElementById('people-list');
  if (!list) return;
  if (toggle) {
    peopleOpen = !peopleOpen;
    list.hidden = !peopleOpen;
    toggle.setAttribute('aria-expanded',String(peopleOpen));
    toggle.querySelector('span').textContent = peopleOpen ? '▴' : '▾';
  } else if (peopleOpen && !event.target.closest('#people-list')) {
    peopleOpen = false; list.hidden = true;
    document.querySelector('.people-toggle')?.setAttribute('aria-expanded','false');
    const arrow = document.querySelector('.people-toggle span'); if (arrow) arrow.textContent = '▾';
  }
});
document.addEventListener('keydown',event => {
  if (event.key !== 'Escape' || !peopleOpen) return;
  peopleOpen = false; document.getElementById('people-list').hidden = true;
  const toggle = document.querySelector('.people-toggle'); toggle?.setAttribute('aria-expanded','false'); toggle?.focus();
});
