import test from 'node:test';
import assert from 'node:assert/strict';
import {backendOrigin, publicHtml} from '../scripts/deployment.mjs';

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
