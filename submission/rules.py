"""Tool-schema rule filter, shared by the submission predictor and tools/local_eval.py.

A candidate that is a tool call (raw JSON with "name" and "arguments": one
object, a list of objects, or one object per line) is excluded when
  * the request provides no tools at all, or
  * every provided tool has a readable name and the call names none of them.
If the tool list cannot be read completely, only the "no tools" part applies.
If every candidate would be excluded, or anything unexpected happens, the
scores are returned unchanged. Standard library only; never raises.
"""
from __future__ import annotations

import json
import math


def _tool_name(tool):
    """Name of one tool entry (object or JSON string), or None if unreadable."""
    if isinstance(tool, str):
        try:
            tool = json.loads(tool)
        except Exception:
            return None
    if not isinstance(tool, dict):
        return None
    name = tool.get('name')
    if not isinstance(name, str) and isinstance(tool.get('function'), dict):
        name = tool['function'].get('name')  # {"type": "function", "function": {...}} layout
    return name if isinstance(name, str) else None


def tool_names(tools):
    """Set of tool names, or None if any entry has no readable name."""
    names = [_tool_name(tool) for tool in tools]
    return None if any(name is None for name in names) else set(names)


def calls(candidate: str):
    """Return the tool-call dicts if the candidate is a raw JSON tool call, else None."""
    text = candidate.strip()
    values = []
    try:
        value = json.loads(text)
        values = value if isinstance(value, list) else [value]
    except Exception:
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                values.append(json.loads(line))
            except Exception:
                return None
    if not values or not all(isinstance(v, dict) and 'name' in v and 'arguments' in v for v in values):
        return None
    return values


def excluded(candidate: str, no_tools: bool, names) -> bool:
    found = calls(candidate)
    if found is None:
        return False
    if no_tools:
        return True
    if names is None:  # tool list present but not fully readable: do not guess
        return False
    return any(not isinstance(call.get('name'), str) or call['name'] not in names for call in found)


def apply_rules(scores, candidates, tools) -> list:
    """Scores with excluded candidates set to -inf (unchanged if all would be excluded)."""
    try:
        no_tools, names = len(tools) == 0, tool_names(tools)
        masked = [-math.inf if excluded(c, no_tools, names) else s for c, s in zip(candidates, scores)]
        return masked if any(math.isfinite(s) for s in masked) else list(scores)
    except Exception:
        return list(scores)
