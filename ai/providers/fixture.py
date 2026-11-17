import json
from copy import deepcopy
from pathlib import Path
from ai.tools.context import build_tool_context


def catalog():
    return json.loads((Path(__file__).parents[1] / "fixtures/provider.json").read_text(encoding="utf-8"))


def fixture_route(context, arguments):
    data, places = catalog(), build_tool_context(context)["places"]
    for ref in (arguments["from_ref"], arguments["to_ref"]):
        if ref not in data["locations"] or any(places.get(ref, {}).get(k) != data["locations"][ref][k]
                                             for k in ("latitude", "longitude")):
            raise ValueError("No fixture route for these coordinates")
    return deepcopy(next(r for r in data["routes"] if all(r[k] == arguments[k] for k in ("from_ref", "to_ref"))))
