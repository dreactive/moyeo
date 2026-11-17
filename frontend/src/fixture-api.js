import initial from '../fixtures/room-snapshot.json' with {type:'json'};
export const fixtureRoom = structuredClone(initial);
export async function requestFixture() { return structuredClone(fixtureRoom); }
