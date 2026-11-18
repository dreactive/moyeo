import test from 'node:test';
import assert from 'node:assert/strict';
import * as session from '../src/session.js';

test('navigation carries only the selected fixture mode across pages', () => {
  globalThis.location = {search:'?mode=fixture&extra=value',assign: url => assert.equal(url,'/rooms.html?mode=fixture')};
  session.navigate('/rooms.html');
});

test('only a rejected session redirects the protected page', async () => {
  const visited = [];
  globalThis.location = {search:'',assign: url => visited.push(url)};
  globalThis.fetch = async () => new Response('', {status:503});
  await assert.rejects(session.requireSession(), {status:503});
  assert.deepEqual(visited, []);
  globalThis.fetch = async () => new Response('', {status:401});
  assert.equal(await session.requireSession(), null);
  assert.deepEqual(visited, ['/login.html']);
});

test('fixture navigation uses a separate selected room key', () => {
  globalThis.location = {search:'?mode=fixture'};
  globalThis.sessionStorage = {setItem: (key,id) => assert.deepEqual([key,id], ['trip-fixture-room','sample'])};
  session.saveRoomId('sample');
});

test('sign-out clears room selection after the server accepts it', async () => {
  const actions = [];
  globalThis.location = {search:'',assign: url => actions.push(url)};
  globalThis.sessionStorage = {removeItem: key => actions.push(key)};
  globalThis.fetch = async (path, options) => {
    actions.push([path, options.method]);
    return Response.json({ok:true});
  };
  await session.signOut();
  assert.deepEqual(actions, [['/api/auth/logout','POST'],'trip-room','/login.html']);
});

test('fixture pages label test data and decorate app links', () => {
  const banner = {};
  const link = {dataset:{appLink:''},getAttribute: () => '/signup.html'};
  globalThis.location = {search:'?mode=fixture'};
  globalThis.document = {getElementById: () => banner,querySelectorAll: () => [link]};
  session.preparePage();
  assert.match(banner.textContent, /fixture/);
  assert.equal(link.href,'/signup.html?mode=fixture');
});

test('a pending entry form ignores duplicate submission', async () => {
  const button = {};
  const form = {querySelector: () => button};
  const event = {preventDefault() {}};
  globalThis.document = {getElementById: () => ({})};
  let submitted = 0;
  session.bindEntryForm(form, () => submitted++);
  const first = form.onsubmit(event);
  await form.onsubmit(event);
  await first;
  assert.equal(submitted,1);
});

test('a failing entry action unlocks its whole control group', async () => {
  const submit = {};
  const peer = {};
  const form = {querySelector: () => submit};
  globalThis.document = {getElementById: () => ({})};
  const task = Promise.withResolvers();
  session.bindEntryForm(form, () => task.promise, () => {}, [submit,peer]);
  const request = form.onsubmit({preventDefault() {}});
  assert.equal(peer.disabled,true);
  task.reject(new Error('offline'));
  await request;
  assert.equal(peer.disabled,false);
});

test('a browser-restored page reloads to check the current session', () => {
  let receive;
  let reloads = 0;
  globalThis.addEventListener = (type,callback) => { if (type === 'pageshow') receive = callback; };
  globalThis.location = {search:'',reload: () => reloads++};
  globalThis.document = {getElementById: () => ({}),querySelectorAll: () => []};
  session.preparePage();
  receive({persisted:false});
  receive({persisted:true});
  assert.equal(reloads,1);
});
