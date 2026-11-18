from ai.tests.test_place_route_tools import task


async def test_generation_returns_candidates_without_selecting():
    from ai.runner import generate_candidates
    from ai.models.fake import FakeModelBackend
    events = []

    async def sink(event):
        events.append(event)

    candidates = await generate_candidates(task(), FakeModelBackend(), sink, 1)
    assert candidates[0]["tool_name"] == "get_car_route"
    assert events[0]["payload"]["selected_index"] is None
    assert events[0]["payload"]["scores"] == []
