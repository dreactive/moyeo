"""Exercise real LangChain/OpenAI serialization against an in-process HTTP transport."""
import json
import httpx
import pytest
from ai.tests.test_auxiliary import task, batch, analysis


def test_external_structured_client_sends_json_schema_without_executable_tools(monkeypatch):
    import langchain_openai
    from ai.auxiliary import create_auxiliary
    from ai.auxiliary_schema import AuxiliaryBatch
    original = langchain_openai.ChatOpenAI
    requests = []
    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert request.url.path == '/v1/chat/completions'
        assert body['model'] == 'gpt-6-luna'
        assert body['reasoning_effort'] == 'none'
        assert 'temperature' not in body and 'tools' not in body and 'tool_choice' not in body
        assert body['response_format']['type'] == 'json_schema'
        schema = body['response_format']['json_schema']
        assert schema['strict'] is True
        assert schema['schema']['additionalProperties'] is False
        assert set(schema['schema']['properties']) == set(schema['schema']['required'])
        payload = AuxiliaryBatch.model_validate(batch(analysis=analysis(summary='엑스포 검색 요청'))).model_dump()
        return httpx.Response(200, json=dict(id='chatcmpl-test', object='chat.completion', created=0,
            model='gpt-6-luna', choices=[dict(index=0, message=dict(role='assistant', content=json.dumps(payload)), finish_reason='stop')],
            usage=dict(prompt_tokens=10, completion_tokens=10, total_tokens=20)))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(langchain_openai, 'ChatOpenAI', lambda **kwargs: original(**kwargs, http_client=client))
        auxiliary = create_auxiliary(dict(auxiliary_backend='external', aux_api_key='sk-test-placeholder',
                                          aux_base_url='https://api.example.invalid/v1', aux_model='gpt-6-luna'))
        result = auxiliary.extract(task('엑스포 검색해줘'))
    assert result['analysis']['summary'] == '엑스포 검색 요청'
    assert len(requests) == 1


async def test_external_http_failure_becomes_safe_failed_receipt(monkeypatch):
    import langchain_openai
    from ai.auxiliary import create_auxiliary, prepare_auxiliary
    original = langchain_openai.ChatOpenAI
    def respond(request):
        return httpx.Response(401, json=dict(error=dict(message='sk-hidden-private-token', type='authentication_error', code='bad_key')))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(langchain_openai, 'ChatOpenAI', lambda **kwargs: original(**kwargs, http_client=client))
        auxiliary = create_auxiliary(dict(auxiliary_backend='external', aux_api_key='sk-test-placeholder',
                                          aux_base_url='https://api.example.invalid/v1', aux_model='gpt-6-luna'))
        result = await prepare_auxiliary(task('엑스포 검색해줘'), auxiliary)
    assert result['extraction_report']['status'] == 'failed'
    assert result['extraction_report']['issue_codes'] == ['auxiliary_request_failed']
    assert 'sk-hidden' not in json.dumps(result)
