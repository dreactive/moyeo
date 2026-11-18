import test from 'node:test';
import assert from 'node:assert/strict';
const chat = await import('../src/chat.js').catch(() => ({}));
test('Enter only sends outside Korean composition and without Shift', () => {
  assert.equal(chat.isSendKey?.({key:'Enter'}),true);
  assert.equal(chat.isSendKey?.({key:'Enter',isComposing:true}),false);
  assert.equal(chat.isSendKey?.({key:'Enter',shiftKey:true}),false);
});
test('chat bubbles escape names and message content', () => {
  const text = chat.messageMarkup?.({id:'m',author_id:'u',text:'<script>',created_at:'2026-11-18T01:00:00Z'},[{user_id:'u',name:'<민수>'}],'u');
  assert.match(text ?? '',/&lt;script&gt;/);
  assert.match(text ?? '',/is-own/);
});
test('chat dates group Korean days rather than browser timezone', () => {
  const rows = chat.chatRows?.([{id:'a',created_at:'2026-11-18T14:59:00Z'},{id:'b',created_at:'2026-11-18T15:01:00Z'}]);
  assert.equal(rows?.length,4);
  assert.equal(rows?.[2].id,'day-11월 19일 목요일');
});
test('new chat rows reuse existing message nodes', () => {
  const old={id:'message-a'};
  const rows=chat.reconcileRows?.([{id:'a'},{id:'b'}],[old],row => ({id:'message-' + row.id}));
  assert.equal(rows?.[0],old);
  assert.equal(rows?.[1].id,'message-b');
});
