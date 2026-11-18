import {getDataMode,requestJson} from './api.js';
import {bindEntryForm,navigate,preparePage,requireSession,saveRoomId,signOut} from './session.js';
import {bindFixedCostControls,readTripForm} from './trip-form.js';
import {run,showError} from './ui.js';

export async function submitRoom(endpoint, body) {
  const snapshot = await requestJson(endpoint, {method:'POST',body});
  if (!snapshot?.room_id) throw new Error('응답에서 방 정보를 찾을 수 없어요.');
  saveRoomId(snapshot.room_id);
  navigate('/');
}

export function chooseRoomAction(actions, selected) {
  for (const action of actions) {
    const open = action === selected;
    const form = document.getElementById(action.getAttribute('aria-controls'));
    action.setAttribute('aria-expanded', String(open));
    form.hidden = !open;
    if (open) form.querySelector('input').focus();
  }
}

export async function checkRoomsPage(retry) {
  retry.hidden = true;
  showError(null);
  try {
    const user = await requireSession();
    if (!user) return;
    document.getElementById('session').textContent = user.name;
    document.getElementById('room-actions').hidden = false;
    document.getElementById('logout').disabled = false;
    if (new URLSearchParams(location.search).get('reason') === 'room-access') {
      showError(new Error('방에 접근할 수 없습니다.'));
    }
  } catch (error) {
    showError(error);
    retry.hidden = false;
  }
}

export function bindRoomForms(trip, join) {
  bindEntryForm(trip, () => submitRoom('/api/rooms', readTripForm(trip)));
  bindEntryForm(join, () => submitRoom('/api/rooms/join', {invite_code:new FormData(join).get('invite_code').trim()}),
    error => showError(error.status === 404 ? new Error('초대 코드를 확인해 주세요.') : error));
}

export function startRoomsPage() {
  preparePage();
  const actions = document.querySelectorAll('[data-room-action]');
  for (const action of actions) {
    action.onclick = () => chooseRoomAction(actions, action);
  }
  bindRoomForms(document.getElementById('trip'), document.getElementById('join'));
  bindFixedCostControls();
  document.getElementById('logout').onclick = () => run(signOut);
  document.getElementById('fixture-invite').hidden = getDataMode() !== 'fixture';
  const retry = document.getElementById('retry');
  retry.onclick = () => checkRoomsPage(retry);
  return retry.onclick();
}

if (globalThis.document?.getElementById('room-actions')) startRoomsPage();
