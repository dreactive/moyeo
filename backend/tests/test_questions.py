import pytest
from fastapi import HTTPException


def test_question_answer_targets_and_ownership(room):
    from backend.services.questions import validate_answer
    question = room['questions'][0]
    assert validate_answer(room, question, 'u1', {'stay_minutes':40}) == {'stay_minutes':40}
    with pytest.raises(HTTPException):
        validate_answer(room, question, 'u1', {'stay_minutes':0})
    question['owner_id'] = 'u2'
    with pytest.raises(HTTPException):
        validate_answer(room, question, 'u1', {'stay_minutes':40})
    question['owner_id'] = None
    question['target_ref'] = 'missing'
    with pytest.raises(HTTPException):
        validate_answer(room, question, 'u1', {'stay_minutes':40})



def test_question_answer_records_input_without_mutating_review(room):
    from backend.services.questions import answer_question
    q = room['questions'][0]
    old = room['current_plan']['days'][0]['visits'][1]['stay_minutes']
    answer_question(room, q['id'], 'u1', {'stay_minutes':40})
    assert q['answer'] == {'stay_minutes':40}
    assert q['answered_by'] == 'u1'
    assert room['current_plan']['days'][0]['visits'][1]['stay_minutes'] == old
    assert room['active_target'] is None
