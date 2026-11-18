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
  const control = event.submitter ?? event.target.querySelector('button[type="submit"],button:not([type])')
    ?? event.target.ownerDocument?.querySelector(`button[type="submit"][form="${event.target.id}"]`);
  return withPending(control,task);
}
const avatarColors = ['#efe7dc','#e3ecfb','#f6e1e6','#e4eefe','#e6f3ea','#f1e9fb'];
export const avatar = name => {
  const text = String(name ?? '?');
  const color = avatarColors[[...text].reduce((sum,char) => sum + char.charCodeAt(0),0) % avatarColors.length];
  return `<span class="avatar" style="background:${color}" aria-hidden="true">${escapeHtml(text.replace(/^참가자/,'').slice(0,2))}</span>`;
};
const seoulTime = new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
export const clock = value => {
  const text = String(value ?? '');
  if (/T\d{2}:\d{2}.*(Z|[+-]\d{2}:?\d{2})$/.test(text) && !Number.isNaN(Date.parse(text))) return seoulTime.format(new Date(text));
  return /T(\d{2}:\d{2})/.exec(text)?.[1] ?? escapeHtml(text);
};
