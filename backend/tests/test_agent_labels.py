import pytest

from backend.services.extraction import extraction_label


def test_selected_question_label_is_the_actual_question_even_when_other_proposals_filtered():
    result = dict(completion='needs_input', extraction_report={'status': 'filtered'},
                  decision_report={'status': 'selected', 'action': 'ask', 'candidate_id': 'c2'},
                  questions=[{'text': '어디에서 출발하시나요?'}])
    assert extraction_label(result) == '어디에서 출발하시나요?'


@pytest.mark.parametrize('action', ['direct', 'unsupported'])
def test_selected_response_label_preserves_actual_response(action):
    assert extraction_label(dict(completion='done', decision_report={'status': 'selected', 'action': action},
                                 response='이 요청은 현재 지원하지 않습니다.')) == '이 요청은 현재 지원하지 않습니다.'


def test_executed_tool_needs_input_label_explains_remaining_work():
    label = extraction_label(dict(completion='needs_input', decision_report={'status': 'held', 'reason': 'no_actual_candidates'},
                                  observations=[{'tool_name': 'search_places', 'result': {'places': []}}]))
    assert '도구 실행' in label and '보완' in label


def test_judge_tool_and_configuration_failures_have_distinct_safe_labels():
    judge = extraction_label(dict(completion='needs_input', decision_report={'status': 'failed', 'reason': 'RuntimeError'}))
    tool = extraction_label(dict(completion='needs_input', decision_report={'status': 'failed', 'reason': 'tool_failed'}))
    configuration = extraction_label(dict(completion='needs_input', extraction_report={
        'status': 'failed', 'issue_codes': ['auxiliary_configuration_missing']}))
    service = extraction_label(dict(completion='needs_input', extraction_report={
        'status': 'failed', 'issue_codes': ['auxiliary_request_failed']}))
    assert len({judge, tool, configuration, service}) == 4
    assert 'Qwen' in judge and '채점' in judge
    assert '도구 실행' in tool
    assert 'API 키' in configuration and '설정' in configuration
    assert '보조 모델 요청' in service


def test_stale_decision_label_explains_hold_instead_of_claiming_success():
    label = extraction_label(dict(completion='needs_input', decision_report={'status': 'stale', 'reason': 'request_changed'}))
    assert '변경' in label and '보류' in label
