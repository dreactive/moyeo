import test from 'node:test';
import assert from 'node:assert/strict';
import * as costs from '../src/fixed-costs.js';

test('membership updates add named cost targets while retaining the selected target and edited draft', () => {
  const owner={value:'u1',dataset:{},innerHTML:'<option value="u1">처음 이름</option>'};
  const amount={value:'123456'},description={value:'작성 중 메모'};
  const row={querySelector:selector => selector === '[name=cost_owner]' ? owner : selector === '[name=cost_price]' ? amount : description};
  globalThis.document={querySelectorAll:selector => selector === '[name=cost_owner]' ? [owner] : [row]};
  costs.refreshCostOwners?.([{user_id:'u1',name:'기존 참가자'},{user_id:'u2',name:'새 참가자'}]);
  assert.match(owner.innerHTML,/<option value="u2"[^>]*>새 참가자<\/option>/);
  assert.deepEqual([owner.value,amount.value,description.value],['u1','123456','작성 중 메모']);
});

test('a removed member target remains selected rather than changing to all participants', () => {
  const owner={value:'former',dataset:{},innerHTML:''};
  globalThis.document={querySelectorAll:() => [owner]};
  costs.refreshCostOwners?.([{user_id:'u1',name:'현재 참가자'}]);
  assert.match(owner.innerHTML,/<option value="former" selected>former<\/option>/);
  assert.equal(owner.value,'former');
});
