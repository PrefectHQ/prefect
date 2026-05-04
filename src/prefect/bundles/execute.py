import json
import sys

from prefect.utilities.asyncutils import run_coro_as_sync


def execute_bundle_from_file(key: str):
    """
    Loads a bundle from a file and executes it.

    Args:
        key: The key of the bundle to execute.
    """
    with open(key, "r") as f:
        bundle = json.load(f)

    run_coro_as_sync(execute_bundle(bundle))


async def execute_bundle(bundle: dict) -> None:
    # All these imports must stay deferred to break circular imports:
    # bundles/__init__ imports from .execute, and _starter_bundle imports from bundles/__init__
    # _flow_run_executor → runner/__init__ → runner.py → bundles/__init__
    from prefect.bundles import extract_flow_from_bundle
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow
    from prefect.runner._flow_run_executor import FlowRunExecutorContext
    from prefect.runner._starter_bundle import BundleExecutionStarter

    async def resolve_flow(fr: FlowRun) -> Flow:
        return extract_flow_from_bundle(bundle)

    async with FlowRunExecutorContext() as ctx:
        flow_run = FlowRun.model_validate(bundle["flow_run"])
        executor = ctx.create_executor(
            flow_run,
            BundleExecutionStarter(
                bundle=bundle,
                control_channel=ctx.control_channel,
            ),
            resolve_flow=resolve_flow,
            propose_submitting=False,
        )
        await executor.submit()


if __name__ == "__main__":
    if len(sys.argv) < 3 and sys.argv[1] != "--key":
        print("Please provide a key representing a path to a bundle")
        sys.exit(1)
    key = sys.argv[2]
    execute_bundle_from_file(key)
