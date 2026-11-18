"""Read-only developer calls; results never enter the room application pipeline."""


async def execute_tool(body, name, settings):
    from ai.tools.registry import RegisteredTools
    tools = RegisteredTools(body.context.model_dump(), settings.get('provider_mode', 'fixture'), settings)
    arguments = body.arguments.model_dump()
    result = await tools.execute(name, arguments)
    return dict(tool_name=name, provider_mode=tools.mode, arguments=arguments, result=result)
