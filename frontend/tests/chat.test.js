import test from 'node:test';
import assert from 'node:assert/strict';
const chat = await import('../src/chat.js').catch(() => ({}));
test('Enter only sends outside Korean composition and without Shift', () => {
  assert.equal(chat.isSendKey?.({key:'Enter'}),true);
  assert.equal(chat.isSendKey?.({key:'Enter',isComposing:true}),false);
  assert.equal(chat.isSendKey?.({key:'Enter',shiftKey:true}),false);
});
