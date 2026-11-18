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

test('only the selected review day offers places from the frozen itinerary', () => {
  const review = structuredClone(snapshot.current_plan);
  review.item_snapshots[0].title = '<검토 장소>';
  renderRoutePanel({...snapshot,review_plan:review}, '2026-11-21');
  assert.match(output['route-summary']?.innerHTML ?? '', /data-place="fixture:place-a">&lt;검토 장소&gt;/);
  renderRoutePanel({...snapshot,review_plan:review}, '2026-11-22');
  assert.doesNotMatch(output['route-summary'].innerHTML, /data-place=/);
});

test('route summary shows the plan revision and scheduled times', () => {
  renderRoutePanel(snapshot, '2026-11-21');
  assert.match(output['route-summary'].innerHTML, /여행안 v1/);
  assert.match(output['route-summary'].innerHTML, /11:30–12:30 · 체류 60분/);
});
