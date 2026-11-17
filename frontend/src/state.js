let snapshot = null;
let selectedPlace = null;
export const getSnapshot = () => snapshot;
export const getSelectedPlace = () => selectedPlace;
export function applySnapshot(next) {
  snapshot = next;
  if (!next?.current_plan?.item_snapshots.some(item => item.place_ref === selectedPlace)) selectedPlace = null;
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


