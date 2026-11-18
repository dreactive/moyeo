import {requestJson} from './api.js';
import {html,escapeHtml as e,avatar,clock,showError} from './ui.js';
import {clearRoomId,navigate,pageUrl,preparePage,readRoomId,requireSession,saveRoomId,signOut} from './session.js';

const stageLabel = {empty:'계획 전',draft:'여행안 r{n} 검토 중',confirmed:'여행안 r{n} 확정'};
export const roomUrl = id => '/?room=' + encodeURIComponent(id);
export function dateRange(start,end) {
  const short = value => value ? value.slice(5).replace('-','/') : '';
  return start && end ? (start === end ? short(start) : `${short(start)} – ${short(end)}`) : '날짜 미정';
}
export function roomCard(room) {
  const stage = (stageLabel[room.plan_stage] ?? '').replace('{n}',room.plan_revision ?? '');
  const last = room.last_message;
  const lastLine = last ? `<p class="room-last"><strong>${last.mine ? '나' : e(last.author_name)}</strong> ${e(last.text)}<time>${clock(last.created_at)}</time></p>` : '<p class="room-last muted">아직 대화가 없어요. 들어가서 첫 이야기를 시작하세요.</p>';
  const deleteButton = room.is_owner
    ? `<button type="button" class="room-delete" data-delete-room="${e(room.room_id)}" data-room-title="${e(room.title)}">삭제</button>`
    : '<button type="button" class="room-delete" disabled title="방장만 삭제할 수 있어요">삭제</button>';
  return `<article class="room-card">
  <div class="room-card-head"><h3><a class="room-link" href="${pageUrl(roomUrl(room.room_id))}" data-enter-room="${e(room.room_id)}">${e(room.title)}</a></h3><span class="pill stage-${e(room.plan_stage)}">${e(stage)}</span></div>
  <p class="muted small">${room.is_owner ? '<span class="tag owner">방장</span> ' : ''}${e(room.region || '도시 미정')} · ${e(dateRange(room.start_date,room.end_date))}${room.agent_state === 'running' ? ' · <span class="running">계획 도우미 작업 중</span>' : ''}</p>
  ${lastLine}
  <div class="room-card-foot"><span class="members">${room.members.slice(0,5).map(member => avatar(member.name)).join('')}<span>${room.members.length}명</span></span><span class="room-card-actions"><span class="muted small">초대 ${e(room.invite_code)}</span>${deleteButton}</span></div></article>`;
}
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
export function addInvitee(list,raw,selfEmail = '') {
  const email = String(raw ?? '').trim().toLowerCase();
  if (!EMAIL.test(email)) return {list,error:'이메일 형식을 확인하세요.'};
  if (email === String(selfEmail).toLowerCase()) return {list,error:'본인은 자동으로 들어가요.'};
  if (list.includes(email)) return {list,error:'이미 추가한 이메일이에요.'};
  return {list:[...list,email],error:null};
}
export function inviteSummary(results) {
  const added = results.filter(result => result.ok).map(result => result.name);
  const missing = results.filter(result => !result.ok).map(result => result.email);
  return {added,missing};
}
export async function loadRooms() {
  const {rooms} = await requestJson('/api/rooms');
  html('room-count', rooms.length ? `${rooms.length}개의 여행방` : '아직 참여한 여행방이 없어요');
  html('rooms', rooms.map(roomCard).join('') || `<div class="lobby-empty"><h3>첫 여행방을 만들어 보세요</h3><p class="muted">새로 만들거나, 친구에게 받은 초대 코드로 들어갈 수 있어요.</p><div class="actions center"><button type="button" class="primary" data-open-create>새 여행방 만들기</button><button type="button" class="ghost" data-open-join>초대 코드로 입장</button></div></div>`);
  return rooms;
}

export function enterRoom(room) {
  if (!room?.room_id) throw new Error('응답에서 방 정보를 찾을 수 없어요.');
  saveRoomId(room.room_id);
  navigate(roomUrl(room.room_id));
}

export async function createRoomWithInvites(invitees,state = {}) {
  if (!state.room) {
    const room = await requestJson('/api/rooms',{method:'POST',body:{}});
    if (!room?.room_id) throw new Error('응답에서 방 정보를 찾을 수 없어요.');
    state.room = room;
    saveRoomId(state.room.room_id);
  }
  state.results ??= [];
  for (const email of invitees) {
    if (state.results.some(result => result.email === email)) continue;
    try {
      const member = await requestJson('/api/rooms/' + encodeURIComponent(state.room.room_id) + '/members',{method:'POST',body:{email}});
      state.results.push({ok:true,email,name:member.name});
    } catch (error) {
      if (error.status !== 404) throw error;
      state.results.push({ok:false,email});
    }
  }
  return {room:state.room,results:state.results};
}

export async function deleteRoom(id) {
  await requestJson('/api/rooms/' + encodeURIComponent(id),{method:'DELETE'});
  if (readRoomId() === id) clearRoomId();
}

function lobbyError(error) {
  if (error.status === 401) return navigate('/login.html?next=' + encodeURIComponent('/rooms'));
  showError(error);
}

export function lobbyActionLock(controls,onError = lobbyError) {
  let pending = false;
  return async task => {
    if (pending) return;
    pending = true;
    const group = typeof controls === 'function' ? [...controls()] : controls;
    const available = group.filter(control => !control.disabled);
    available.forEach(control => control.disabled = true);
    showError(null);
    try { return await task(); }
    catch (error) { onError(error); }
    finally {
      pending = false;
      available.forEach(control => control.disabled = false);
    }
  };
}

function openDialog(dialog) {
  if (dialog.showModal) dialog.showModal();
  else dialog.setAttribute('open','');
}
function closeDialog(dialog) {
  if (dialog.close) dialog.close();
  else dialog.removeAttribute('open');
}

function bindStart(user,execute) {
  const dialog = document.getElementById('create-dialog');
  let invitees = [];
  let flow = {};
  let completed = false;
  const hint = message => html('invite-hint',e(message ?? ''));
  const drawInvitees = () => {
    html('invitees',invitees.map(email => `<li>${avatar(email)}<span>${e(email)}</span><button type="button" class="ghost sm" data-remove-invitee="${e(email)}" aria-label="${e(email)} 빼기">빼기</button></li>`).join(''));
    html('invite-count',invitees.length ? `${invitees.length}명을 초대해요` : '혼자 먼저 만들고 나중에 초대해도 돼요');
  };
  const showTab = name => {
    document.querySelectorAll('[data-start-tab]').forEach(tab => tab.setAttribute('aria-selected',String(tab.dataset.startTab === name)));
    document.getElementById('pane-create').hidden = name !== 'create';
    document.getElementById('pane-join').hidden = name !== 'join';
    document.getElementById(name === 'create' ? 'invite-email' : 'invite-code').focus();
  };
  const open = tab => {
    if (document.getElementById('open-create').disabled) return;
    if (completed) { invitees = []; flow = {}; completed = false; }
    drawInvitees(); hint(null);
    document.querySelectorAll('#pane-create > *, .segmented').forEach(node => { node.hidden = false; });
    document.getElementById('invite-result').hidden = true;
    openDialog(dialog);
    showTab(tab);
  };
  document.addEventListener('click',event => {
    if (event.target.closest('#open-create,[data-open-create]')) open('create');
    if (event.target.closest('[data-open-join]')) open('join');
    if (event.target.closest('[data-close-create]:not(:disabled)')) closeDialog(dialog);
    const tab = event.target.closest('[data-start-tab]');
    if (tab) showTab(tab.dataset.startTab);
    const remove = event.target.closest('[data-remove-invitee]');
    if (remove) { invitees = invitees.filter(email => email !== remove.dataset.removeInvitee); drawInvitees(); }
  });
  document.getElementById('invite-add').onsubmit = event => {
    event.preventDefault();
    const input = document.getElementById('invite-email');
    const next = addInvitee(invitees,input.value,user.email);
    hint(next.error);
    if (next.error) return;
    invitees = next.list; input.value = ''; drawInvitees(); input.focus();
  };
  const createButton = document.getElementById('create-room');
  createButton.onclick = () => execute(async () => {
    const pending = document.getElementById('invite-email').value.trim();
    if (pending && !invitees.includes(pending.toLowerCase())) {
      const next = addInvitee(invitees,pending,user.email);
      if (next.error) return hint(next.error);
      invitees = next.list; drawInvitees();
    }
    document.getElementById('invite-email').value = ''; hint(null);
    const {room,results} = await createRoomWithInvites(invitees,flow);
    const {added,missing} = inviteSummary(results);
    if (!missing.length) return enterRoom(room);
    completed = true;
    const box = document.getElementById('invite-result');
    document.querySelectorAll('#pane-create > :not(#invite-result)').forEach(node => { node.hidden = true; });
    document.querySelector('.segmented').hidden = true;
    box.hidden = false;
    loadRooms().catch(lobbyError);
    box.innerHTML = `<p><strong>${e(room.title)}</strong>을 만들었어요.${added.length ? ' ' + e(added.join(', ')) + '님을 초대했어요.' : ''}</p>
    <p class="warn-text">아직 가입하지 않은 이메일: ${e(missing.join(', '))}</p>
    <p class="muted small">이 친구들은 가입한 뒤 아래 초대 코드로 들어오면 돼요.</p>
    <div class="link-row"><input readonly value="${e(room.invite_code)}" aria-label="초대 코드"><button type="button" class="ghost" data-copy-link="${e(room.invite_code)}">코드 복사</button></div>
    <a class="primary-link" href="${pageUrl(roomUrl(room.room_id))}" data-enter-room="${e(room.room_id)}">방으로 들어가기</a>`;
  });
  document.addEventListener('click',event => {
    const copy = event.target.closest('[data-copy-link]');
    if (copy) navigator.clipboard?.writeText(copy.dataset.copyLink).then(() => { copy.textContent = '복사됨'; }).catch(lobbyError);
  });
}
function bindJoin(execute) {
  document.getElementById('join').onsubmit = event => {
    event.preventDefault();
    execute(async () => {
      const code = event.target.elements.invite_code.value.trim();
      if (!code) throw new Error('초대 코드를 입력하세요.');
      try {
        const room = await requestJson('/api/rooms/join',{method:'POST',body:{invite_code:code}});
        enterRoom(room);
      } catch (error) {
        if (error.status === 404) throw new Error('초대 코드를 확인해 주세요.');
        throw error;
      }
    });
  };
}
function bindDelete(execute) {
  const dialog = document.getElementById('delete-dialog');
  let target = null;
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-delete-room]');
    if (!button || document.getElementById('open-create').disabled) return;
    target = button.dataset.deleteRoom;
    html('delete-room-name',e(button.dataset.roomTitle));
    openDialog(dialog);
    document.getElementById('delete-cancel').focus();
  });
  document.getElementById('delete-cancel').onclick = () => closeDialog(dialog);
  const confirm = document.getElementById('delete-confirm');
  confirm.onclick = () => execute(async () => {
    if (!target) return;
    await deleteRoom(target);
    closeDialog(dialog);
    await loadRooms();
  });
}
export async function startLobbyPage() {
  preparePage();
  const controls = () => document.querySelectorAll('#open-create,#logout,#create-dialog button,#create-dialog input,#delete-dialog button,[data-delete-room]');
  const retry = document.getElementById('retry');
  let ready = false;
  let checking = false;
  const execute = lobbyActionLock(controls);
  const check = async () => {
    if (checking) return;
    checking = true;
    retry.hidden = true;
    showError(null);
    controls().forEach(control => control.disabled = true);
    try {
      const user = await requireSession();
      if (!user) return;
      html('session',e(user.name));
      if (!ready) {
        bindStart(user,execute);
        bindJoin(execute);
        bindDelete(execute);
        document.getElementById('logout').onclick = () => execute(signOut);
        document.addEventListener('click',event => {
          const link = event.target.closest('[data-enter-room]');
          if (!link) return;
          event.preventDefault();
          if (!document.getElementById('open-create').disabled) enterRoom({room_id:link.dataset.enterRoom});
        });
        ready = true;
      }
      await loadRooms();
      controls().forEach(control => control.disabled = false);
    } catch (error) {
      lobbyError(error);
      if (error.status !== 401) retry.hidden = false;
    } finally { checking = false; }
  };
  retry.onclick = check;
  if (new URLSearchParams(location.search).get('deleted')) {
    html('notice','방장이 여행방을 삭제해서 목록으로 돌아왔어요.');
    history.replaceState(null,'',pageUrl('/rooms'));
  }
  if (new URLSearchParams(location.search).get('reason') === 'room-access') html('notice','방에 접근할 수 없습니다. 다른 방을 선택해 주세요.');
  return check();
}
if (typeof document !== 'undefined' && document.getElementById('rooms')) {
  document.addEventListener('submit',() => showError(null),true);
  startLobbyPage().catch(lobbyError);
}
