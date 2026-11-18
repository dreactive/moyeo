const fixtureSessionKey = 'trip-fixture-session-v1';

export function readFixtureSession() {
  return JSON.parse(globalThis.sessionStorage?.getItem(fixtureSessionKey) ?? 'null');
}

export function saveFixtureSession({authenticated,userId,snapshot,scenario}) {
  const state = {authenticated,userId,snapshot,scenario};
  globalThis.sessionStorage?.setItem(fixtureSessionKey, JSON.stringify(state));
}
