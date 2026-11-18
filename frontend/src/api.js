import {requestFixture} from './fixture-api.js';
export const getDataMode = () => new URLSearchParams(globalThis.location?.search).get('mode') === 'fixture' ? 'fixture' : 'live';
export async function requestJson(path, options = {}) {
  if (getDataMode() === 'fixture') return requestFixture(path, options);
  const response = await fetch(path, {credentials:'same-origin', ...options,
    headers:{'Content-Type':'application/json', ...options.headers},
    body:options.body === undefined ? undefined : JSON.stringify(options.body)});
  if (!response.ok) {
    const detail = await response.json().then(body => body?.detail, () => null);
    const error = new Error(errorText(response.status,detail) + ' (' + response.status + ')');
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}
const detailText = {
  'Email already registered':'이미 가입된 이메일이에요.','Invalid credentials':'이메일 또는 비밀번호가 맞지 않아요.','Login required':'로그인이 필요해요.',
  'Invite not found':'초대 코드를 찾을 수 없어요.','Room membership required':'이 방의 참가자만 볼 수 있어요.','Room not found':'방을 찾을 수 없어요.',
  'Invalid trip configuration':'여행 조건을 다시 확인하세요.','Only the room owner may rename':'채팅방 이름은 방장만 바꿀 수 있어요.','Invalid room title':'채팅방 이름을 1~200자로 입력하세요.','Only the condition owner may edit':'조건 소유자만 수정할 수 있어요.',
  'Only question owner may answer':'질문 대상자만 답할 수 있어요.','Invalid question answer':'답변 형식을 확인하세요.',
  'Menu does not belong to the target place':'그 장소의 메뉴가 아니에요.','Confirmation target changed':'여행안이 바뀌었어요. 새 안을 확인해 주세요.',
  'Review inputs changed':'검토 중 조건이 바뀌었어요. 새 안을 확인해 주세요.','No active confirmation to withdraw':'철회할 내 확인이 없어요.',
  'Draft revision changed':'더 새로운 초안이 있어요. 화면을 새로 고쳐 주세요.','Conflict inputs changed':'충돌 상황이 바뀌었어요. 다시 확인해 주세요.',
  'Owner selection required':'조건 소유자만 고를 수 있어요.','Only condition owner may select relaxation':'조건 소유자만 고를 수 있어요.',
  'Place not observed in this room':'이 방에서 조회한 장소가 아니에요.','Developer token required':'개발자 token이 필요해요.',
  'Only the room owner may delete':'방장만 여행방을 삭제할 수 있어요.','User not found':'가입된 이메일을 찾을 수 없어요.'
};
const statusText = {400:'요청 내용을 확인하세요.',401:'로그인이 필요해요.',403:'권한이 없어요.',404:'찾을 수 없어요.',409:'최신 상태가 아니에요. 화면을 새로 고쳐 주세요.',422:'입력값을 확인하세요.'};
export function errorText(status,detail) {
  if (typeof detail === 'string' && detailText[detail]) return detailText[detail];
  return statusText[status] ?? (status >= 500 ? '서버와 연결하지 못했어요.' : '요청을 처리하지 못했어요.');
}
