export const isSendKey = event => event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229;
import {escapeHtml as e} from './ui.js';
export const chatDate = value => new Date(value).toLocaleDateString('ko-KR',{timeZone:'Asia/Seoul',month:'long',day:'numeric',weekday:'long'});
export function messageMarkup(message,members,userId) {
  const name = members.find(member => member.user_id === message.author_id)?.name ?? message.author_id;
  const time = new Date(message.created_at).toLocaleTimeString('ko-KR',{timeZone:'Asia/Seoul',hour:'numeric',minute:'2-digit'});
  return `<li id="message-${e(message.id)}" class="chat-message ${message.author_id === userId ? 'is-own' : ''}"><span class="chat-avatar">${e(name.slice(0,1))}</span><div class="chat-message-content"><span class="chat-author">${e(name)}</span><p class="chat-bubble">${e(message.text)}</p><time class="chat-time" datetime="${e(message.created_at)}">${e(time)}</time></div></li>`;
}
export function chatRows(messages) {
  let date;
  return messages.flatMap(message => {
    const next = chatDate(message.created_at);
    const heading = next !== date ? [{id:'day-' + next,date:next}] : [];
    date = next;
    return [...heading,message];
  });
}
