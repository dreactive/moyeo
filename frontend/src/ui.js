export const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
export const html = (id, value) => { document.getElementById(id).innerHTML = value; };
export const money = value => value == null ? '미확인' : Number(value).toLocaleString('ko-KR') + '원';
export const showError = error => { document.getElementById('error').textContent = error?.message ?? ''; };
export const run = task => Promise.resolve().then(task).catch(showError);
export async function withPending(control,task) {
  if (control?.disabled) return;
  if (control) control.disabled = true;
  if (control?.dataset) control.dataset.pending = 'true';
  try { return await task(); }
  finally {
    if (control?.dataset) delete control.dataset.pending;
    if (control) control.disabled = false;
  }
}
export function runFormAction(event,task) {
  const control = event.submitter ?? event.target.querySelector('button[type="submit"],button:not([type])');
  return withPending(control,task);
}
