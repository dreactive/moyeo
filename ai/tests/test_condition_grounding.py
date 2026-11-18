def test_budget_needs_actual_message_evidence():
    from ai.condition_grounding import condition_value
    assert condition_value('budget_krw', '내 예산은 20만원') == 200000
    assert condition_value('budget', '안녕') is None
