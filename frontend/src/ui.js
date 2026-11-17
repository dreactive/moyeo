export const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
export const html = (id, value) => { document.getElementById(id).innerHTML = value; };
export const money = value => value == null ? '미확인' : Number(value).toLocaleString('ko-KR') + '원';
export const showError = error => { document.getElementById('error').textContent = error?.message ?? ''; };
export const run = task => Promise.resolve().then(task).catch(showError);
