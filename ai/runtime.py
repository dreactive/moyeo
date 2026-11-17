"""JSON-only public boundary; models and providers are selected explicitly."""
from ai.result import empty_result
from ai.tools.context import build_tool_context


class AgentRuntime:
    def __init__(self, config):
        self.config = dict(config)

    async def run(self, task, emit_trace):
        return empty_result(task)

    async def execute_tool(self, name, arguments, context):
        if name != "get_place_details":
            raise ValueError("Unregistered tool")
        return build_tool_context(context)["details"][arguments["place_ref"]]

    async def aclose(self):
        pass


def create_runtime(config):
    return AgentRuntime(config)
