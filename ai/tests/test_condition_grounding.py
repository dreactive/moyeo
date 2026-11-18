def test_budget_needs_actual_message_evidence():
    from ai.condition_grounding import condition_value
    assert condition_value('budget_krw', '내 예산은 20만원') == 200000
    assert condition_value('budget', '안녕') is None

def test_deadline_needs_time_and_arrival_intent():
    from ai.condition_grounding import condition_value
    assert condition_value('return_by', '난 16시까지 역에 도착해야 해') == '16:00'
    assert condition_value('return_by', '안녕') is None
    assert condition_value('return_by', '12시에 점심 먹자') is None

import pytest

@pytest.mark.parametrize('text', ['예산 20만원은 아니야', '철수는 예산 20만원이라고 했어', '만약 예산이 20만원이면', '예산 20만원 어때?', '전체 예산 20만원', '예산은 20만원보다 더 필요해'])
def test_negative_hypothetical_proxy_and_shared_budgets_are_not_personal_facts(text):
    from ai.condition_grounding import condition_value
    assert condition_value('budget', text) is None

def test_time_period_and_decimal_budget_are_not_misnormalized():
    from ai.condition_grounding import condition_value
    assert condition_value('return_by', '오후 4시까지 귀가해야 해') == '16:00'
    assert condition_value('budget', '내 예산은 2.5만원') == 25000

@pytest.mark.parametrize('key,text', [('budget','철수는 예산 20만원'),('return_by','철수는 16시까지 귀가해야 해')])
def test_third_person_facts_without_quotation_are_not_owned_by_speaker(key,text):
    from ai.condition_grounding import condition_value
    assert condition_value(key,text) is None

@pytest.mark.parametrize('text', ['내 예산은 20만원이 아니라 15만원이야', '내 예산은 20만원은 아냐', '내 예산은 20만원인지 모르겠어', '내 예산은 20만원이면 좋겠어', '내 예산은 20만원에서 15만원으로 바꿀게'])
def test_negation_uncertainty_and_multiple_values_need_clarification(text):
    from ai.condition_grounding import condition_value
    assert condition_value('budget',text) is None

@pytest.mark.parametrize('key,text', [('budget','내 예산은 20만원일 수도 있어'),('budget','예산은 20만원이래'),('budget','예산 없고 선물은 20만원'),('return_by','16시까지 동생이 귀가해야 해'),('return_by','16시까지 귀가할 수도 있어')])
def test_only_complete_personal_assertions_produce_hard_values(key,text):
    from ai.condition_grounding import condition_value
    assert condition_value(key,text) is None


def test_complete_grouped_won_amount_is_not_parsed_as_zero():
    from ai.condition_grounding import condition_value
    assert condition_value('budget','내 예산은 200,000원') == 200000
