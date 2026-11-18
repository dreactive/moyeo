import {requestJson} from './api.js';
import {bindEntryForm,navigate,pageUrl,preparePage} from './session.js';
import {showError} from './ui.js';

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
export function safeNext(value) {
  const next = String(value ?? '');
  try {
    const decoded = decodeURIComponent(next);
    if (!next.startsWith('/') || /[\\\u0000-\u0020\u007f]/.test(decoded) || decoded.startsWith('//')) return '/rooms';
    const url = new URL(next,'https://workspace.local');
    const pathname = decodeURIComponent(url.pathname);
    if (url.origin !== 'https://workspace.local' || pathname.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(pathname)
      || next === '/' || /^\/(login|signup)(?:\.html)?(?:\/|$)/i.test(pathname)) return '/rooms';
    return next;
  } catch { return '/rooms'; }
}
export function validateAuth(kind,data) {
  const email = String(data.email ?? '').trim();
  if (kind === 'signup' && !String(data.name ?? '').trim()) return '이름을 입력하세요.';
  if (!EMAIL.test(email)) return '이메일 형식을 확인하세요.';
  if (String(data.password ?? '').length < 8) return '비밀번호는 8자 이상이어야 해요.';
  if (kind === 'signup' && !String(data.password).trim()) return '공백만으로 된 비밀번호는 쓸 수 없어요.';
  if (kind === 'signup' && data.password !== data.password_confirm) return '비밀번호 확인이 일치하지 않아요.';
  return null;
}
export function authBody(kind,data) {
  const email = String(data.email).trim().toLowerCase();
  return kind === 'signup' ? {name:String(data.name).trim(),email,password:data.password} : {email,password:data.password};
}

export async function submitAuth(action,data,next = '/rooms.html') {
  const kind = ['register','signup'].includes(action) ? 'signup' : 'login';
  const values = {...data,password_confirm:data.password_confirm ?? data.password_confirmation};
  if (kind === 'signup' && (String(values.password ?? '').length < 8 || values.password !== values.password_confirm)) {
    throw new RangeError('비밀번호는 8자 이상이며 확인 값과 같아야 합니다.');
  }
  const problem = validateAuth(kind,values);
  if (problem) throw new RangeError(problem);
  await requestJson('/api/auth/' + (kind === 'signup' ? 'register' : 'login'),{method:'POST',body:authBody(kind,values)});
  navigate(safeNext(next));
}

const authErrors = {401:'이메일 또는 비밀번호를 확인해 주세요.',409:'이미 가입된 이메일이에요.',422:'입력한 정보를 확인해 주세요.'};
export function authErrorMessage(error) {
  if (error instanceof RangeError) return error.message;
  return authErrors[error.status] ?? '연결 상태를 확인하고 다시 시도해 주세요.';
}

export async function checkAuthPage(submit,retry,next = '/rooms.html') {
  submit.disabled = true;
  retry.hidden = true;
  showError(null);
  try {
    await requestJson('/api/auth/me');
    navigate(safeNext(next));
  } catch (error) {
    if (error.status === 401) submit.disabled = false;
    else {
      showError(new Error('연결 상태를 확인하고 다시 시도해 주세요.'));
      retry.hidden = false;
    }
  }
}

export function startAuthPage(form) {
  preparePage();
  const params = new URLSearchParams(location.search);
  const next = safeNext(params.get('next'));
  const kind = form.id === 'signup-form' || form.dataset?.action === 'register' ? 'signup' : 'login';
  const submit = form.querySelector('button[type=submit]');
  const retry = document.getElementById('retry');
  document.querySelectorAll('a[data-keep-next]').forEach(link => {
    const url = new URL(link.getAttribute('href'),'https://workspace.local');
    if (next !== '/rooms') url.searchParams.set('next',next);
    link.href = pageUrl(url.pathname + url.search);
  });
  if (kind === 'login' && params.get('email') && form.elements?.email) form.elements.email.value = params.get('email');
  bindEntryForm(form,() => submitAuth(kind,Object.fromEntries(new FormData(form)),next),
    error => showError(new Error(authErrorMessage(error))));
  retry.onclick = () => checkAuthPage(submit,retry,next);
  return retry.onclick();
}

const authForm = globalThis.document?.querySelector?.('#login-form, #signup-form');
if (authForm) startAuthPage(authForm);
