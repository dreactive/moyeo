async def test_trace_redacts_keys_and_links_calls():
    from ai.trace import emit
    events = []
    async def sink(event):
        events.append(event)
    await emit(sink, {"run_id": "r"}, 1, "tool_call", "r:1",
               {"tool_name": "search_places", "API_KEY": "secret", "nested": {"reasoning": "private", "ok": 1}})
    assert events[0]["call_id"] == "r:1"
    assert events[0]["payload"] == {"tool_name": "search_places", "nested": {"ok": 1}}
    await emit(None, {"run_id": "r"}, 1, "tool_result", "r:1", {})
