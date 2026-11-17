from copy import deepcopy
from ai.tools.context import build_tool_context
from ai.tools.routes import observed_route
from ai.tools.costs import calculate_costs
from ai.tools.itinerary import build_itinerary
from ai.tools.validation import validate_arguments


class RegisteredTools:
    def __init__(self, context, mode="fixture", settings=None):
        self.context = build_tool_context(context)
        self.mode, self.settings = mode, settings or {}

    def remember(self, observation):
        self.context["observations"].append(deepcopy(observation))
        self.context = build_tool_context(self.context)

    async def execute(self, name, arguments):
        validate_arguments(name, arguments, self.context)
        if name == "calculate_costs":
            return calculate_costs(**arguments)
        if name == "build_itinerary":
            return build_itinerary(**arguments, config=self.context["config"])
        if name == "search_places":
            places = [p for p in self.context["places"].values() if "name" in p
                      and arguments["query"] in p["name"]]
            return {"places": deepcopy(places)}
        if name == "get_car_route":
            return observed_route(self.context, arguments)
        if name == "get_place_details":
            ref = arguments["place_ref"]
            if ref not in self.context["details"]:
                raise ValueError("Place details not observed in this room")
            return deepcopy(self.context["details"][ref])
        raise ValueError("Unregistered tool")
