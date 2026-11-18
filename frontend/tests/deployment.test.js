import test from 'node:test';
import assert from 'node:assert/strict';
import {backendOrigin, publicHtml, deploymentConfig} from '../scripts/deployment.mjs';
import {mkdtemp, readFile, readdir, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {copyStatic} from '../scripts/build-files.mjs';
import {buildFrontend} from '../scripts/build.mjs';

async function temporary(t) {
  const directory = await mkdtemp(join(tmpdir(), 'trip-deploy-'));
  t.after(async () => {
    assert.ok(resolve(directory).startsWith(resolve(tmpdir()) + sep));
    await rm(directory, {recursive: true, force: true});
  });
  return directory;
}

test('deployment requires a bare HTTPS backend origin', () => {
  assert.equal(backendOrigin('https://api.example.com/'), 'https://api.example.com');
  for (const value of [undefined, 'http://api.example.com', 'https://x/a', 'https://u:p@x', 'https://x?q=1', 'https://x/#a']) {
    assert.throws(() => backendOrigin(value), /BACKEND_ORIGIN/);
  }
});

test('only the public map key is escaped into the page', () => {
  const html = '<meta name="kakao-map-app-key" content="">';
  assert.equal(publicHtml(html, '\"><&'), '<meta name="kakao-map-app-key" content="&quot;&gt;&lt;&amp;">');
  assert.equal(publicHtml(html), html);
});

test('proxy routing preserves authenticated API paths and disables caching', () => {
  const config = deploymentConfig('https://api.example.com');
  const route = config.routes[0];
  assert.equal('/api/rooms/r/events'.replace(new RegExp(route.src), route.dest), 'https://api.example.com/api/rooms/r/events');
  assert.equal(route.headers['Cache-Control'], 'no-store');
  assert.equal(route.headers['x-vercel-enable-rewrite-caching'], '0');
});

test('entry URLs resolve to packaged HTML while preserving API proxy priority', () => {
  const config = deploymentConfig('https://api.example.com');
  for (const page of ['login','signup','rooms']) {
    const route = config.routes.find(route => route.src === '/' + page);
    assert.equal(route?.dest, '/' + page + '.html');
    assert.ok(config.routes.indexOf(route) > 0);
  }
});

test('static packaging excludes server and development files', async t => {
  const output = await temporary(t);
  await copyStatic(fileURLToPath(new URL('../', import.meta.url)), output);
  const files = await readdir(output);
  for (const name of ['.env', '.env.example', 'server.js', 'scripts', 'tests', 'package.json']) assert.ok(!files.includes(name));
  assert.match(await readFile(join(output, 'index.html'), 'utf8'), /kakao-map-app-key/);
  assert.ok((await readdir(join(output, 'fixtures'))).includes('scenarios.json'));
});

test('a complete build publishes routes and only the public environment key', async t => {
  const root = await temporary(t);
  await copyStatic(fileURLToPath(new URL('../', import.meta.url)), root);
  await buildFrontend(root, {BACKEND_ORIGIN: 'https://api.example.com', KAKAO_JAVASCRIPT_KEY: 'public-map', DEV_TOKEN: 'private-sentinel'});
  const output = join(root, '.vercel/output');
  const config = JSON.parse(await readFile(join(output, 'config.json'), 'utf8'));
  const html = await readFile(join(output, 'static/index.html'), 'utf8');
  assert.equal(config.version, 3);
  assert.match(html, /content="public-map"/);
  assert.ok(!JSON.stringify(config).includes('private-sentinel') && !html.includes('private-sentinel'));
  await writeFile(join(output, 'static/stale.txt'), 'old-build-secret');
  await buildFrontend(root, {BACKEND_ORIGIN: 'https://api.example.com'});
  await assert.rejects(readFile(join(output, 'static/stale.txt')), {code: 'ENOENT'});
});
test('static deployment includes every sign-in entry and workspace stylesheet', async t => {
  const output=await temporary(t);
  await copyStatic(fileURLToPath(new URL('../',import.meta.url)),output);
  for (const name of ['login.html','signup.html','rooms.html','workspace.css']) {
    assert.ok((await readFile(join(output,name),'utf8')).length > 0);
  }
});
