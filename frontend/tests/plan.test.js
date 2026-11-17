import test from 'node:test';
import assert from 'node:assert/strict';
import * as plan from '../src/plan.js';
test('review stays fixed when a new draft arrives; every target field matters', () => {
  const a = {participant_version:1,constraint_version:1,evidence_version:1,plan_revision:1,content_hash:'a'};
  const review = {confirmation_target:a};
  assert.equal(plan.displayPlan({review_plan:review,current_plan:{}}),review);
  assert.equal(plan.sameTarget(a,{...a}),true);
  for (const key of Object.keys(a)) assert.equal(plan.sameTarget(a,{...a,[key]:'changed'}),false);
});
