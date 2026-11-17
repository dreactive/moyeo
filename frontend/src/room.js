import {html,escapeHtml as e} from './ui.js';
export function renderRoom(snapshot) {
  html('room-heading', e(snapshot.title) + ' · 초대 ' + e(snapshot.invite_code));
  html('members', snapshot.members.map(member => e(member.name)).join(' · '));
  html('agent', e(snapshot.agent_status.label) + ' / ' + e(snapshot.agent_status.state) + ' / ' + e(snapshot.agent_status.run_id));
}
import {requestJson,getDataMode} from './api.js';
import {applySnapshot,subscribeState,setUser} from './state.js';
import {showError} from './ui.js';
export async function startRoomApp() {
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

