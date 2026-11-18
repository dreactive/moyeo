
def test_compact_messages_are_projected_with_distinct_source_ids(monkeypatch):
    import ai.models.qwen_extraction as module
    from ai.tests.test_place_route_tools import task
    monkeypatch.setattr(module, 'generate_object', lambda model, tokenizer, request: dict(places=['오동도'],conditions=[],intents=['place']))
    value = task()
    value['recent_messages'] = [dict(id='new',author_id='u1',text='오동도 가자')]
    output = module.generate_extraction(None,None,dict(phase='extract',context=value))
    assert output['item_proposals'][0]['evidence']['message_id'] == 'new'

def test_optional_history_never_pushes_current_message_past_budget():
    from ai.models.qwen_generation import reference_prompt
    class Tokenizer:
        def apply_chat_template(self,messages,**kwargs): return ''.join(m['content'] for m in messages)
        def encode(self,text,**kwargs): return list(text)
        def decode(self,tokens,**kwargs): return ''.join(tokens)
    messages = [dict(role='system',content='schema'),dict(role='user',content='안녕')]
    prompt = reference_prompt(messages,dict(conversation_context=['가'*10000]),Tokenizer(),100)
    assert len(prompt) <= 100 and '안녕' in prompt
