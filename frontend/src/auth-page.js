import {requestJson} from './api.js';
import {navigate} from './session.js';
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
