import argparse
import asyncio
import json
from pathlib import Path
from ai.runtime import create_runtime


async def run(args):
    runtime = create_runtime({"model_backend": args.model, "provider_mode": args.providers,
                              "base_model_path": args.base_model_path,
                              "adapter_path": args.adapter_path, "env_file": args.env_file})
    try:
        result = await runtime.run(json.loads(Path(args.task).read_text(encoding="utf-8")), None)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{args.model}/{args.providers}: {result['completion']}")
    finally:
        await runtime.aclose()


def parser():
    command = argparse.ArgumentParser()
    command.add_argument("command", choices=["run"])
    command.add_argument("--task", required=True)
    command.add_argument("--model", choices=["fake", "local_qwen"], default="fake")
    command.add_argument("--providers", choices=["fixture", "live"], default="fixture")
    command.add_argument("--output", required=True)
    command.add_argument("--base-model-path")
    command.add_argument("--adapter-path")
    command.add_argument("--env-file")
    return command


if __name__ == "__main__":
    asyncio.run(run(parser().parse_args()))
