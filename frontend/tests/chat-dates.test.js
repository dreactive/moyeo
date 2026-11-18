import test from 'node:test';
import assert from 'node:assert/strict';
import {dayKey,dayLabel,mergeMessages,groupByDay} from '../src/chat-dates.js';
test('days follow Seoul time and read like a chat date header', () => {
  assert.equal(dayKey('2026-11-18T15:30:00+00:00'),'2026-11-19');
  assert.equal(dayKey('2026-11-18T14:59:00+00:00'),'2026-11-18');
  assert.equal(dayLabel('2026-11-18'),'2026년 11월 18일 수요일');
});
test('history and live messages merge by id and group by day', () => {
  const merged = mergeMessages([{id:'b',seq:2,created_at:'2026-11-18T01:00:00Z'}],[{id:'a',seq:1,created_at:'2026-11-17T01:00:00Z'},{id:'b',seq:2,created_at:'2026-11-18T01:00:00Z'},{id:'c',seq:3,created_at:'2026-11-18T02:00:00Z'}]);
  assert.deepEqual(merged.map(m => m.id),['a','b','c']);
  const groups = groupByDay(merged);
  assert.deepEqual(groups.map(g => [g.key,g.messages.length]),[['2026-11-17',1],['2026-11-18',2]]);
});
test('calendar month grid starts on Sunday and pads the last week', async () => {
  const {monthGrid,shiftMonth,monthKey} = await import('../src/chat-dates.js');
  const grid = monthGrid(2026,11);
  assert.deepEqual(grid[0],[1,2,3,4,5,6,7]);
  assert.deepEqual(grid.at(-1),[29,30,null,null,null,null,null]);
  assert.deepEqual(monthGrid(2026,12)[0],[null,null,1,2,3,4,5]);
  assert.equal(shiftMonth('2026-12',1),'2027-01');
  assert.equal(shiftMonth('2026-01',-1),'2025-12');
  assert.equal(monthKey('2026-11-18'),'2026-11');
});
