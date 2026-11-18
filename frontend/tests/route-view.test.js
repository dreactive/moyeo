import test from 'node:test';
import assert from 'node:assert/strict';
import {renderRoutePanel} from '../src/route-view.js';
import snapshot from '../fixtures/room-snapshot.json' with {type:'json'};

const output = {};
globalThis.document = {getElementById: id => output[id] ??= {}};

test('route buttons select the provided date', () => {
  renderRoutePanel(snapshot, '2026-11-22');
  assert.match(output['route-days']?.innerHTML ?? '', /aria-pressed="true" data-day="2026-11-22"/);
});
