import test from 'node:test';
import assert from 'node:assert/strict';
import {panelPlacement,clampLauncher} from '../src/chat-bubble.js';
const viewport = {width:1440,height:900};
const rect = (left,top,size = 58) => ({left,top,right:left + size,bottom:top + size});
test('chat opens right above a bubble near the bottom', () => {
  const place = panelPlacement(rect(24,818),viewport,380);
  assert.equal(place.side,'above');
  assert.equal(place.left,24);
  assert.equal(place.top + place.height,818 - 12);
  assert.equal(place.height,560);
});
test('a bubble near the top opens the chat below it', () => {
  const place = panelPlacement(rect(600,40),viewport,380);
  assert.equal(place.side,'below');
  assert.equal(place.top,40 + 58 + 12);
});
test('the panel stays inside the screen at the right edge and on phones', () => {
  const right = panelPlacement(rect(1370,800),viewport,380);
  assert.ok(right.left + right.width <= 1440 - 8);
  const phone = panelPlacement(rect(16,760),{width:390,height:844},380);
  assert.ok(phone.width <= 390 - 16 && phone.left >= 8 && phone.top >= 8);
});
test('dragged bubble is kept on screen', () => {
  assert.deepEqual(clampLauncher({x:-50,y:2000},58,viewport),{x:8,y:900 - 58 - 8});
});
