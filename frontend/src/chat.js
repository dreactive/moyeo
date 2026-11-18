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
export function reconcileRows(rows,nodes,create) {
  const previous = new Map(nodes.map(node => [node.id,node]));
  return rows.map(row => previous.get('message-' + row.id) ?? create(row));
}
export function chatScroll(before,height,prepended) {
  if (before.height - before.top - before.viewport < 64) return height;
  return before.top + (prepended ? height - before.height : 0);
}
function createChatNode(row,members,userId) {
  const template = document.createElement('template');
  template.innerHTML = row.date
    ? `<li id="message-${e(row.id)}" class="chat-date">${e(row.date)}</li>`
    : messageMarkup(row,members,userId);
  return template.content.firstElementChild;
}
export function reconcileChat(list,snapshot,userId) {
  const nodes = list.dataset.userId === userId ? [...list.children] : [];
  list.replaceChildren(...reconcileRows(chatRows(snapshot.messages),nodes,row => createChatNode(row,snapshot.members,userId)));
  list.dataset.userId = userId;
}
function captureChatPosition(list) {
  return {top:list.scrollTop,height:list.scrollHeight,viewport:list.clientHeight,
    first:list.querySelector('.chat-message')?.id,count:list.querySelectorAll('.chat-message').length};
}
function restoreChatPosition(list,before,messages) {
  const prepended = messages.findIndex(message => 'message-' + message.id === before.first) > 0;
  list.scrollTop = chatScroll(before,list.scrollHeight,prepended);
  document.getElementById('new-messages').hidden = prepended || messages.length <= before.count || before.height - before.top - before.viewport < 64;
}
export function renderChat(snapshot,userId) {
  const list = document.getElementById('messages');
  const before = captureChatPosition(list);
  reconcileChat(list,snapshot,userId);
  restoreChatPosition(list,before,snapshot.messages);
}
export async function sendChatMessage(form,send) {
  const text = form.elements.text.value;
  const message = await send({text});
  if (form.elements.text.value === text) form.reset();
  return message;
}
