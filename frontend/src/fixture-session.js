const fixtureSessionKey = 'trip-fixture-session-v1';

export function clearFixtureSession() {
  globalThis.sessionStorage?.removeItem(fixtureSessionKey);
  globalThis.sessionStorage?.removeItem('trip-fixture-room');
}

export function readStoredFixtureSession() {
  return globalThis.sessionStorage?.getItem(fixtureSessionKey) ?? null;
}

export function readFixtureSession(stored = readStoredFixtureSession()) {
  try {
    return JSON.parse(stored);
  } catch {
    clearFixtureSession();
    return null;
  }
}

export function saveFixtureSession({authenticated,userId,snapshot,scenario}) {
  const stored = JSON.stringify({authenticated,userId,snapshot,scenario});
  globalThis.sessionStorage?.setItem(fixtureSessionKey, stored);
  return stored;
}
