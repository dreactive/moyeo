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
