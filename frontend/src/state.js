let snapshot = null;
let selectedPlace = null;
export const getSnapshot = () => snapshot;
export const getSelectedPlace = () => selectedPlace;
export function applySnapshot(next) {
  const sameRoom = snapshot?.room_id === next?.room_id;
  snapshot = next;
  const days = (next?.review_plan ?? next?.current_plan)?.days ?? [];
  if (!sameRoom || !days.some(day => day.date === selectedDay)) selectedDay = days[0]?.date ?? null;
  if (!sameRoom || !(next?.review_plan ?? next?.current_plan)?.item_snapshots.some(item => item.place_ref === selectedPlace)) selectedPlace = null;
  listeners.forEach(listener => listener(snapshot));
}
export function setSelectedPlace(ref) { selectedPlace = ref; }
const listeners = new Set();
export function subscribeState(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
let user = null;
export const getUser = () => user;
export const setUser = value => { user = value; };


const byMessageSeq = (left,right) => left.seq - right.seq;

export function appendMessage(message,eventSeq) {
  if (snapshot?.room_id !== message.room_id) return;
  const exists = snapshot.messages.some(old => old.id === message.id);
  snapshot = {...snapshot,seq:Math.max(snapshot.seq ?? 0,eventSeq ?? 0),messages:exists ? snapshot.messages : [...snapshot.messages,message].sort(byMessageSeq)};
  listeners.forEach(listener => listener(snapshot));
}

export function applyRoomResponse(next,expectedRoom) {
  if (next.room_id !== expectedRoom || snapshot?.room_id !== expectedRoom || next.seq < snapshot.seq) return;
  const messages = new Map((snapshot.messages ?? []).map(message => [message.id,message]));
  for (const message of next.messages ?? []) messages.set(message.id,message);
  applySnapshot({...next,messages:[...messages.values()].sort(byMessageSeq)});
}

let selectedDay = null;
export const getSelectedDay = () => selectedDay;
export const setSelectedDay = value => { selectedDay = value; };
