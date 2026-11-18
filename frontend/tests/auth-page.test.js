import test from 'node:test';
import assert from 'node:assert/strict';
import {safeNext,validateAuth,authBody} from '../src/auth-page.js';
test('login redirect only returns to same-site app paths', () => {
  assert.equal(safeNext('/?invite=abc'),'/?invite=abc');
  assert.equal(safeNext('/dev'),'/dev');
  assert.equal(safeNext('/rooms'),'/rooms');
  for (const bad of [null,'','/','https://evil.test','//evil.test','/\\evil.test','javascript:alert(1)','/login','/signup?next=/']) assert.equal(safeNext(bad),'/rooms',bad);
});

test('redirects reject backslash, control-character and encoded auth paths', () => {
  for (const path of ['/\t/evil.test','/\n/evil.test','/%5cevil.test','/rooms\\../login','/%6cogin.html?next=/','/signup.html']) {
    assert.equal(safeNext(path),'/rooms',path);
  }
});

test('auth redirects reject network paths produced by URL dot-segment normalization', () => {
  for (const path of ['/a/..//evil.test','/a/%2e%2e//evil.test','/a/../%2f/evil.test']) {
    assert.equal(safeNext(path),'/rooms',path);
  }
});
test('signup and login inputs are checked before the request', () => {
  const ok = {name:'민수',email:'a@b.test',password:'password1',password_confirm:'password1'};
  assert.equal(validateAuth('signup',ok),null);
  assert.equal(validateAuth('login',{email:'a@b.test',password:'password1'}),null);
  assert.match(validateAuth('signup',{...ok,name:'  '}),/이름/);
  assert.match(validateAuth('signup',{...ok,email:'abc'}),/이메일/);
  assert.match(validateAuth('signup',{...ok,password:'short',password_confirm:'short'}),/8자/);
  assert.match(validateAuth('signup',{...ok,password:'        ',password_confirm:'        '}),/공백/);
  assert.match(validateAuth('signup',{...ok,password_confirm:'different1'}),/일치/);
});
test('request bodies are trimmed and never carry the confirmation field', () => {
  assert.deepEqual(authBody('signup',{name:' 민수 ',email:' A@B.Test ',password:'password1',password_confirm:'password1'}),{name:'민수',email:'a@b.test',password:'password1'});
  assert.deepEqual(authBody('login',{email:'A@B.test ',password:'password1'}),{email:'a@b.test',password:'password1'});
});
