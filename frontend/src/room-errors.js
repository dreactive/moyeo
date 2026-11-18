export async function runRoomTask(task,handlers) {
  try { return await task(); }
  catch (error) {
    handlers.showError(error);
    if (error.status === 401) handlers.expired();
    else if (error.status === 409) await handlers.stale?.();
  }
}
