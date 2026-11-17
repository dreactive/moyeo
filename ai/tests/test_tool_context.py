import json
from pathlib import Path


def test_runtime_restores_refs_without_backend():
    from ai.tools.context import build_tool_context
    task = json.loads(Path("ai/fixtures/agent-task.json").read_text(encoding="utf-8"))
    ctx = build_tool_context(task)
    assert ctx["places"]["fixture:place-a"]["latitude"] == 34.761
    assert ctx["places"]["anchor:origin"]["latitude"] == 34.76
    assert ctx["details"]["fixture:place-a"]["menus"][0]["price_krw"] == 10000
