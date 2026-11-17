def test_semantic_hash_ignores_poll_time_and_votes(room):
    from backend.services.planning import semantic_plan_hash
    from copy import deepcopy
    plan = deepcopy(room['current_plan'])
    before = semantic_plan_hash(plan)
    plan.update(retrieved_at='later', supporter_ids=['u1'], agent_status='running')
    assert semantic_plan_hash(plan) == before
    plan['item_snapshots'][0]['title'] = 'changed'
    assert semantic_plan_hash(plan) != before


def test_frozen_target_survives_new_draft(room):
    from backend.services.planning import freeze_review
    from copy import deepcopy
    target = deepcopy(room['current_plan']['confirmation_target'])
    freeze_review(room, target)
    room['current_plan']['plan_revision'] += 1
    room['current_plan']['days'] = []
    freeze_review(room, target)
    assert room['review_plan']['days']
    assert room['active_target'] == target
