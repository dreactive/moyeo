import test from 'node:test';
import assert from 'node:assert/strict';
import {navigate} from '../src/session.js';

test('navigation carries only the selected fixture mode across pages', () => {
  globalThis.location = {search:'?mode=fixture&extra=value',assign: url => assert.equal(url,'/rooms.html?mode=fixture')};
  navigate('/rooms.html');
});
