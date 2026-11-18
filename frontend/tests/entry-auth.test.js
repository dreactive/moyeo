import test from 'node:test';
import assert from 'node:assert/strict';
import * as auth from '../src/auth-page.js';

test('login succeeds directly into room selection', async () => {
  let visited;
  globalThis.location = {search:'',assign: path => visited = path};
  globalThis.fetch = async () => Response.json({id:'u1'});
  await auth.submitAuth('login', {email:'test@example.test',password:'example-password'});
  assert.equal(visited,'/rooms.html');
});

test('successful auth never emits a network-path redirect after normalization', async () => {
  const visited = [];
  globalThis.location = {search:'',assign: path => visited.push(path)};
  globalThis.fetch = async () => Response.json({id:'u1'});
  await auth.submitAuth('login',{email:'test@example.test',password:'example-password'},'/a/..//evil.test');
  assert.deepEqual(visited,['/rooms']);
  assert.equal(new URL(visited[0],'https://app.test').origin,'https://app.test');
});

test('signup refuses mismatched passwords before sending a request', async () => {
  globalThis.fetch = () => assert.fail('signup should stay on the form');
  await assert.rejects(auth.submitAuth('register', {password:'long-enough',password_confirmation:'different'}), RangeError);
});

test('an unavailable session lookup enables retry and keeps the form protected', async () => {
  const retry = {hidden:true};
  const submit = {disabled:true};
  globalThis.document = {getElementById: () => ({})};
  globalThis.fetch = async () => new Response('', {status:503});
  await auth.checkAuthPage(submit,retry);
  assert.deepEqual([retry.hidden,submit.disabled], [false,true]);
});

test('auth forms become available after the anonymous session check', async () => {
  const button = {disabled:true};
  const form = {querySelector: () => button};
  globalThis.document = {getElementById: () => ({}),querySelectorAll: () => []};
  globalThis.fetch = async () => new Response('', {status:401});
  await auth.startAuthPage(form);
  assert.equal(button.disabled,false);
  assert.equal(typeof form.onsubmit,'function');
});

test('authentication failures distinguish credentials, registration, and retry', () => {
  assert.match(auth.authErrorMessage({status:401}), /이메일 또는 비밀번호/);
  assert.match(auth.authErrorMessage({status:409}), /가입된 이메일/);
  assert.match(auth.authErrorMessage({status:422}), /입력한 정보/);
  assert.match(auth.authErrorMessage({status:503}), /다시 시도/);
});
