import test from 'node:test';
import assert from 'node:assert/strict';
import {readAnchor} from '../src/trip-input.js';
test('blank anchors remain null and partial anchors cannot become zero coordinates', () => {
  assert.equal(readAnchor({},'origin'),null);
  assert.throws(() => readAnchor({origin_label:'역'},'origin'));
  assert.deepEqual(readAnchor({origin_label:'역',origin_latitude:'34.7',origin_longitude:'127.6'},'origin'),{label:'역',latitude:34.7,longitude:127.6});
});
