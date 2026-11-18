export async function runRoomTask(task,handlers) {
  try { return await task(); }
  catch (error) {
    handlers.showError(error);
    if (error.status === 401) handlers.expired();
    else if (error.status === 409) await handlers.stale?.();
  }
}
export function roomLoadRedirect(error) {
  if (error.status === 401) return '/login.html';
  return [403,404].includes(error.status) ? '/rooms.html?reason=room-access' : null;
}
