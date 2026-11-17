import a from '../fixtures/place-details.json' with {type:'json'};
import b from '../fixtures/place-details-b.json' with {type:'json'};
export const fixturePlaces = new Map([[a.place.id,a],[b.place.id,b]]);
export function resetFixturePlaces() {
  [a,b].forEach(details => fixturePlaces.set(details.place.id,structuredClone(details)));
}
