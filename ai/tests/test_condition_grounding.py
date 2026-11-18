def test_budget_needs_actual_message_evidence():
    from ai.condition_grounding import condition_value
    assert condition_value('budget_krw', '내 예산은 20만원') == 200000
    assert condition_value('budget', '안녕') is None

def test_deadline_needs_time_and_arrival_intent():
    from ai.condition_grounding import condition_value
    assert condition_value('return_by', '난 16시까지 역에 도착해야 해') == '16:00'
    assert condition_value('return_by', '안녕') is None
    assert condition_value('return_by', '12시에 점심 먹자') is None
