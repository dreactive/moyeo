import json
from pathlib import Path
import pytest


def task():
    return json.loads(Path("ai/fixtures/agent-task.json").read_text(encoding="utf-8"))


async def test_details_restored_and_cross_room_isolation():
    from ai.tools.registry import RegisteredTools
    tools = RegisteredTools(task(), "fixture")
    result = await tools.execute("get_place_details", {"place_ref": "fixture:place-a"})
    assert result["menus"][0]["price_krw"] == 10000
    other = task()
    other["observations"] = []
    with pytest.raises(ValueError):
        await RegisteredTools(other, "fixture").execute("get_place_details", {"place_ref": "unknown"})


async def test_route_anchors_units_and_missing_leg():
    from ai.tools.registry import RegisteredTools
    context = task()
    context["observations"].append({"tool_name": "get_car_route", "arguments": {}, "result": {
        "from_ref": "anchor:origin", "to_ref": "fixture:place-a", "distance_m": 1200,
        "duration_seconds": 180, "toll_krw": None, "polyline": [], "evidence_id": "fixture:route"}})
    tools = RegisteredTools(context)
    route = await tools.execute("get_car_route", {"from_ref": "anchor:origin",
                                "to_ref": "fixture:place-a", "departure_at": None})
    assert (route["distance_m"], route["duration_seconds"]) == (1200, 180)
    with pytest.raises(ValueError):
        await tools.execute("get_car_route", {"from_ref": "fixture:place-a", "to_ref": "anchor:destination"})


async def test_route_cache_does_not_cross_departure_time():
    from ai.tools.registry import RegisteredTools
    context = task()
    context["observations"] = [{"tool_name": "get_car_route",
        "arguments": {"from_ref": "anchor:origin", "to_ref": "anchor:destination",
                      "departure_at": "2026-11-21T09:00:00+09:00"},
        "result": {"from_ref": "anchor:origin", "to_ref": "anchor:destination",
                   "distance_m": 1000, "duration_seconds": 300, "polyline": []}}]
    with pytest.raises(ValueError):
        await RegisteredTools(context).execute("get_car_route",
            {"from_ref": "anchor:origin", "to_ref": "anchor:destination",
             "departure_at": "2026-11-21T17:00:00+09:00"})
