let snapshot = null;
let selectedPlace = null;
export const getSnapshot = () => snapshot;
export const getSelectedPlace = () => selectedPlace;
export function applySnapshot(next) {
  snapshot = next;
  if (!next?.current_plan?.item_snapshots.some(item => item.place_ref === selectedPlace)) selectedPlace = null;
}
export function setSelectedPlace(ref) { selectedPlace = ref; }
