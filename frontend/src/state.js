let snapshot = null;
let selectedPlace = null;
export const getSnapshot = () => snapshot;
export const getSelectedPlace = () => selectedPlace;
export function applySnapshot(next) {
  snapshot = next;
  if (!(next?.review_plan ?? next?.current_plan)?.item_snapshots.some(item => item.place_ref === selectedPlace)) selectedPlace = null;
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


export function appendMessage(message) {
  if (snapshot?.room_id !== message.room_id || snapshot.messages.some(old => old.id === message.id)) return;
  snapshot = {...snapshot,messages:[...snapshot.messages,message]};
  listeners.forEach(listener => listener(snapshot));
}

