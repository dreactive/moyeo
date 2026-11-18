import {requestJson} from './api.js';
import {navigate} from './session.js';

export async function submitAuth(action, data) {
  const {name,email,password} = data;
  const body = action === 'register' ? {name,email,password} : {email,password};
  await requestJson('/api/auth/' + action, {method:'POST',body});
  navigate('/rooms.html');
}
