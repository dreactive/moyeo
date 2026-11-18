import {requestJson} from './api.js';
import {navigate,saveRoomId} from './session.js';

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
