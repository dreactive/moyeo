import test from 'node:test';
import assert from 'node:assert/strict';
import {unreadCount} from '../src/chat-unread.js';
const messages = [{id:'m1',author_id:'me'},{id:'m2',author_id:'you'},{id:'m3',author_id:'me'},{id:'m4',author_id:'you'}];
test('closed chat counts newer messages from others only', () => {
  assert.equal(unreadCount(messages,'m1','me'),2);
  assert.equal(unreadCount(messages,'m3','me'),1);
  assert.equal(unreadCount(messages,'m4','me'),0);
  assert.equal(unreadCount(messages,null,'me'),0);
  assert.equal(unreadCount(messages,'missing','me'),0);
});
