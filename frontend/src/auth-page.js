import {requestJson} from './api.js';
import {bindEntryForm,navigate,preparePage} from './session.js';
import {showError} from './ui.js';

export async function submitAuth(action, data) {
  const {name,email,password} = data;
  if (action === 'register' && (password.length < 8 || password !== data.password_confirmation)) {
    throw new RangeError('비밀번호는 8자 이상이며 확인 값과 같아야 합니다.');
  }
  const body = action === 'register' ? {name,email,password} : {email,password};
  await requestJson('/api/auth/' + action, {method:'POST',body});
  navigate('/rooms.html');
}

export async function checkAuthPage(submit, retry) {
  retry.hidden = true;
  showError(null);
  try {
    await requestJson('/api/auth/me');
    navigate('/rooms.html');
  } catch (error) {
    if (error.status === 401) {
      submit.disabled = false;
    } else {
      showError(new Error('연결 상태를 확인하고 다시 시도해 주세요.'));
      retry.hidden = false;
    }
  }
}

const authErrors = {
  401:'이메일 또는 비밀번호를 확인해 주세요.',
  409:'이미 가입된 이메일이에요.',
  422:'입력한 정보를 확인해 주세요.'
};

export function authErrorMessage(error) {
  if (error instanceof RangeError) return error.message;
  return authErrors[error.status] ?? '연결 상태를 확인하고 다시 시도해 주세요.';
}

export function startAuthPage(form) {
  preparePage();
  const submit = form.querySelector('button[type=submit]');
  const retry = document.getElementById('retry');
  bindEntryForm(form, () => submitAuth(form.dataset.action, Object.fromEntries(new FormData(form))),
    error => showError(new Error(authErrorMessage(error))));
  retry.onclick = () => checkAuthPage(submit, retry);
  return retry.onclick();
}

const authForm = globalThis.document?.getElementById('auth');
if (authForm) startAuthPage(authForm);
