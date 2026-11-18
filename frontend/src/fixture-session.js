const fixtureSessionKey = 'trip-fixture-session-v1';

export function clearFixtureSession() {
  globalThis.sessionStorage?.removeItem(fixtureSessionKey);
  globalThis.sessionStorage?.removeItem('trip-fixture-room');
}

export function readFixtureSession() {
  try {
    return JSON.parse(globalThis.sessionStorage?.getItem(fixtureSessionKey) ?? 'null');
  } catch {
    clearFixtureSession();
    return null;
  }
}

export function saveFixtureSession({authenticated,userId,snapshot,scenario}) {
  const state = {authenticated,userId,snapshot,scenario};
  globalThis.sessionStorage?.setItem(fixtureSessionKey, JSON.stringify(state));
}
