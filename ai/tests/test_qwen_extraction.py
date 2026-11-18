
def test_compact_messages_are_projected_with_distinct_source_ids(monkeypatch):
    import ai.models.qwen_extraction as module
    from ai.tests.test_place_route_tools import task
    monkeypatch.setattr(module, 'generate_object', lambda model, tokenizer, request: dict(places=['오동도'],conditions=[],intents=['place']))
    value = task()
    value['recent_messages'] = [dict(id='new',author_id='u1',text='오동도 가자')]
    output = module.generate_extraction(None,None,dict(phase='extract',context=value))
    assert output['item_proposals'][0]['evidence']['message_id'] == 'new'
