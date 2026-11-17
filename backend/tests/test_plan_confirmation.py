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


def test_official_vote_is_unique_and_owned(room):
    from backend.services.planning import record_confirmation
    target = room['current_plan']['confirmation_target']
    record_confirmation(room, 'u1', target, 'confirm')
    record_confirmation(room, 'u1', target, 'confirm')
    assert len(room['confirmations']) == 1
    record_confirmation(room, 'u1', target, 'withdraw')
    assert room['confirmations'][0]['stance'] == 'withdraw'
    assert room['confirmed_plan'] is None


def test_blocking_or_unchecked_requirements_prevent_green(room):
    from backend.services.planning import ready_to_confirm
    plan = room['current_plan']
    assert not ready_to_confirm(room, plan)
    plan['validation'] = 'ready'
    room['constraints'] = []
    assert ready_to_confirm(room, plan)
    plan['blocking_conflict_ids'] = ['blocking']
    assert not ready_to_confirm(room, plan)
    plan['blocking_conflict_ids'] = []
    room['constraints'] = [{'kind':'hard','status':'needs_owner_confirmation'}]
    assert not ready_to_confirm(room, plan)


def test_four_members_same_target_required(room):
    from backend.services.planning import record_confirmation, finalize_plan
    room['current_plan']['validation'] = 'ready'
    room['constraints'] = []
    target = room['current_plan']['confirmation_target']
    for user_id in ('u1','u2','u3'):
        record_confirmation(room, user_id, target, 'confirm')
    assert not finalize_plan(room)
    record_confirmation(room, 'u4', target, 'confirm')
    assert finalize_plan(room)
    assert room['confirmed_plan'] == room['review_plan']
    room['current_plan']['days'] = []
    assert room['confirmed_plan']['days']


def test_explicit_activation_discards_previous_votes(room):
    from backend.services.planning import activate_plan, record_confirmation
    target = room['current_plan']['confirmation_target']
    record_confirmation(room, 'u1', target, 'confirm')
    room['current_plan']['plan_revision'] = 2
    room['current_plan']['confirmation_target'] = dict(target, plan_revision=2)
    activate_plan(room, 2)
    assert room['active_target']['plan_revision'] == 2
    assert room['confirmations'] == []
