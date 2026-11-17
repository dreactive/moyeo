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


def test_question_http_replans_target(api):
    response = api.post('/api/rooms/room-fixture/questions/question-stay/answer', json={'value':{'stay_minutes':40}})
    assert response.status_code == 200
    question = next(q for q in response.json()['questions'] if q['id'] == 'question-stay')
    assert question['answer'] == {'stay_minutes':40}


def test_support_target_answer_only_updates_original_author(room):
    from backend.services.questions import answer_question
    question = dict(id='question:support_target:oppose:m4',owner_id='u4',field='support_target',target_ref=None,text='Which item?',related_item_ids=['item-a','item-b'],status='open',answer=None,answered_by=None)
    room['questions'].append(question)
    with pytest.raises(HTTPException):
        answer_question(room, question['id'], 'u1', {'item_id':'item-a'})
    answer_question(room, question['id'], 'u4', {'item_id':'item-a'})
    assert 'u4' in room['items'][0]['opponent_ids']
    assert room['confirmations'] == []
