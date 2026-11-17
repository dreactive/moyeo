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
