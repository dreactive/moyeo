from copy import deepcopy
from ai.tools.context import build_tool_context


class RegisteredTools:
    def __init__(self, context, mode="fixture", settings=None):
        self.context = build_tool_context(context)
        self.mode, self.settings = mode, settings or {}

    async def execute(self, name, arguments):
        if name == "get_place_details":
            ref = arguments["place_ref"]
            if ref not in self.context["details"]:
                raise ValueError("Place details not observed in this room")
            return deepcopy(self.context["details"][ref])
        raise ValueError("Unregistered tool")
