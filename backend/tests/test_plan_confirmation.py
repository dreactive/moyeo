def test_semantic_hash_ignores_poll_time_and_votes(room):
    from backend.services.planning import semantic_plan_hash
    from copy import deepcopy
    plan = deepcopy(room['current_plan'])
    before = semantic_plan_hash(plan)
    plan.update(retrieved_at='later', supporter_ids=['u1'], agent_status='running')
    assert semantic_plan_hash(plan) == before
    plan['item_snapshots'][0]['title'] = 'changed'
    assert semantic_plan_hash(plan) != before
