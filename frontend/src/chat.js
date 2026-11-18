export const isSendKey = event => event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229;
import {escapeHtml as e,avatar,clock} from './ui.js';
import {groupByDay} from './chat-dates.js';
export const chatDate = value => new Date(value).toLocaleDateString('ko-KR',{timeZone:'Asia/Seoul',month:'long',day:'numeric',weekday:'long'});
export const chatTime = value => new Date(value).toLocaleTimeString('ko-KR',{timeZone:'Asia/Seoul',hour:'numeric',minute:'2-digit'});
export function messageMarkup(message,members,userId) {
  const name = members.find(member => member.user_id === message.author_id)?.name ?? '참가자';
  const time = chatTime(message.created_at);
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
  const members = JSON.stringify(snapshot.members);
  const nodes = list.dataset.userId === userId && list.dataset.members === members ? [...list.children] : [];
  list.replaceChildren(...reconcileRows(chatRows(snapshot.messages),nodes,row => createChatNode(row,snapshot.members,userId)));
  list.dataset.userId = userId;
  list.dataset.members = members;
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
export function renderGroupedChat(snapshot,userId,list = document.getElementById('messages')) {
  const before = {top:list.scrollTop,height:list.scrollHeight,viewport:list.clientHeight,
    first:[...list.children].find(node => node.id.startsWith('message-'))?.id,
    count:[...list.children].filter(node => node.id.startsWith('message-')).length};
  const basis = JSON.stringify([snapshot.room_id,snapshot.members,userId]);
  const previous = new Map(list.dataset.chatBasis === basis ? [...list.children].map(node => [node.id,node]) : []);
  const nameOf = id => snapshot.members.find(member => member.user_id === id)?.name ?? id;
  const rows = groupByDay(snapshot.messages).flatMap(day => [
    {id:'day-' + day.key,markup:`<li class="date-sep" id="day-${e(day.key)}"><button type="button" data-date-menu aria-haspopup="true" aria-controls="date-menu" title="다른 날짜로 이동">${e(day.label)}<span aria-hidden="true">▾</span></button></li>`},
    ...day.messages.map(message => ({id:'message-' + message.id,markup:`<li id="message-${e(message.id)}" class="msg${message.author_id === userId ? ' mine' : ''}">${message.author_id === userId ? '' : avatar(nameOf(message.author_id))}<div class="msg-body"><strong>${e(nameOf(message.author_id))}</strong><p>${e(message.text)}</p><small title="${e(message.created_at)}">${clock(message.created_at)}</small></div></li>`}))
  ]);
  list.replaceChildren(...rows.map(row => {
    if (previous.has(row.id)) return previous.get(row.id);
    const template = document.createElement('template');
    template.innerHTML = row.markup;
    return template.content.firstElementChild;
  }));
  list.dataset.chatBasis = basis;
  const prepended = snapshot.messages.findIndex(message => 'message-' + message.id === before.first) > 0;
  list.scrollTop = chatScroll(before,list.scrollHeight,prepended);
  const notice = document.getElementById('new-messages');
  if (notice) notice.hidden = prepended || snapshot.messages.length <= before.count || before.height - before.top - before.viewport < 64;
}
