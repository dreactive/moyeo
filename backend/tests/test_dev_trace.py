def test_trace_redacts_credentials_and_private_reasoning():
    from backend.services.traces import sanitize
    data = {'api_key':'secret','nested':{'authorization':'Bearer secret','value':3},'reasoning':'private','url':'https://example.test/?api_key=secret&place=a'}
    cleaned = sanitize(data)
    assert 'secret' not in str(cleaned)
    assert 'private' not in str(cleaned)
    assert cleaned['nested']['value'] == 3
