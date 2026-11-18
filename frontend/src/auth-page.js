import {requestJson} from './api.js';
import {navigate} from './session.js';

export async function submitAuth(action, data) {
  const {name,email,password} = data;
  if (action === 'register' && (password.length < 8 || password !== data.password_confirmation)) {
    throw new RangeError('비밀번호는 8자 이상이며 확인 값과 같아야 합니다.');
  }
  const body = action === 'register' ? {name,email,password} : {email,password};
  await requestJson('/api/auth/' + action, {method:'POST',body});
  navigate('/rooms.html');
}
