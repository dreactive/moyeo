import test from 'node:test';
import assert from 'node:assert/strict';
import fixture from '../fixtures/room-snapshot.json' with {type:'json'};
import {renderItems} from '../src/items.js';
test('old confirmed state cannot invent current majority support', () => {
  const room = structuredClone(fixture);
  room.confirmed_plan = structuredClone(room.current_plan);
  room.current_plan.confirmation_target.content_hash = 'new';
  room.items[0].state='confirmed'; room.items[0].supporter_ids=[];
  let output='';
  globalThis.document={getElementById:() => ({set innerHTML(value){output=value;}})};
  renderItems(room);
  assert.match(output,/새 안 · 미확정/);
  assert.doesNotMatch(output,/card confirmed/);
});
