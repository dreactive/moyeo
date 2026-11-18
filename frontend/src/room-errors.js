export async function runRoomTask(task,handlers) {
  try { return await task(); }
  catch (error) {
    handlers.showError(error);
    if (error.status === 401) handlers.expired();
  }
}
