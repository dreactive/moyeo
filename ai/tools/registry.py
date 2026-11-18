from copy import deepcopy
from ai.tools.context import build_tool_context
from ai.tools.routes import observed_route
from ai.tools.costs import calculate_costs
from ai.tools.itinerary import build_itinerary
from ai.tools.validation import validate_arguments
from ai.settings import load_settings
from ai.questions import valid_questions


class RegisteredTools:
    def __init__(self, context, mode="fixture", settings=None):
        self.context = build_tool_context(context)
        self.mode, self.settings = mode, settings or {}
        self.context["_provider_mode"] = mode
        self.credentials = load_settings(self.settings) if mode == "live" else {}

    def remember(self, observation):
        self.context["observations"].append(deepcopy(observation))
        self.context = build_tool_context(self.context)

    def restore(self, context):
        self.context = build_tool_context(context)
        self.context["_provider_mode"] = self.mode

    async def execute(self, name, arguments):
        validate_arguments(name, arguments, self.context)
        self.last_execution_source = 'local_calculation' if name in ('calculate_costs', 'build_itinerary') else 'fixture'
        if self.mode == "live" and name in ("search_places", "get_place_details", "get_car_route"):
            self.last_execution_source = 'http'
            if name == 'get_place_details':
                cached = self.context['details'].get(arguments['place_ref'])
                if cached and cached.get('evidence') and all(e['mode'] == 'live' for e in cached['evidence']):
                    self.last_execution_source = 'cache'
            if name == 'get_car_route':
                try:
                    if observed_route(self.context, arguments)['evidence_id'].startswith('kakao:route:'):
                        self.last_execution_source = 'cache'
                except ValueError:
                    pass
            from ai.providers.live import execute
            return await execute(name, arguments, self.context, self.credentials)
        if name == "calculate_costs":
            return calculate_costs(**arguments)
        if name == "build_itinerary":
            config = dict(self.context["config"], _details=self.context["details"],
                          _base_versions=self.context.get("base_versions", {}))
            result = build_itinerary(**arguments, config=config)
            result["questions"] = valid_questions(self.context, result["questions"])
            return result
        if name == "search_places":
            from ai.providers.fixture import catalog
            known = dict(catalog()["locations"], **self.context["places"])
            places = [p for p in known.values() if "name" in p
                      and arguments["query"] in p["name"]]
            return {"places": deepcopy(places) if arguments["region"] == "여수" else []}
        if name == "get_car_route":
            try:
                return observed_route(self.context, arguments)
            except ValueError:
                if self.mode != "fixture":
                    raise
                from ai.providers.fixture import fixture_route
                return fixture_route(self.context, arguments)
        if name == "get_place_details":
            ref = arguments["place_ref"]
            if ref not in self.context["details"]:
                from ai.providers.fixture import catalog
                known = catalog()["details"].get(ref)
                if not known or any(known["place"][k] != self.context["places"][ref][k] for k in ("latitude", "longitude")):
                    raise ValueError("Place details not observed in this room/provider")
                return deepcopy(known)
            return deepcopy(self.context["details"][ref])
        raise ValueError("Unregistered tool")
