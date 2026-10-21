"""
Demonstrate that process workers are resilient when flow files go missing.

Workers should continue operating when they can't load flow files for hook execution.
"""

import shutil
from pathlib import Path
from textwrap import dedent

import pytest

from prefect import flow
from prefect.runner import Runner
from prefect.runner._hook_runner import HookRunner


async def test_runner_resilience_with_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Test that runners handle missing flow files gracefully"""

    # Record crashed-hook calls directly. Log assertions are unreliable here
    # because another integration test reconfigures logging at import time.
    crashed_hook_flow_run_ids = []
    run_crashed_hooks = HookRunner.run_crashed_hooks

    async def record_crashed_hooks(self, flow_run, state):
        crashed_hook_flow_run_ids.append(flow_run.id)
        await run_crashed_hooks(self, flow_run, state)

    monkeypatch.setattr(HookRunner, "run_crashed_hooks", record_crashed_hooks)

    flow_file = tmp_path / "my_flow.py"
    # Outside `tmp_path`, which the test deletes before its assertions.
    hook_marker = tmp_path.parent / f"{tmp_path.name}-hook-ran"

    print(f"Working in: {tmp_path}")

    # Create a flow file with an on_crashed hook that records whether it ran
    flow_content = dedent(f"""
        from pathlib import Path

        from prefect import flow

        def my_hook(flow, flow_run, state):
            Path({str(hook_marker)!r}).write_text("ran")

        @flow(on_crashed=[my_hook])
        def my_flow():
            print("Flow executing...")
            raise RuntimeError("Intentional crash to trigger hooks")
    """)

    flow_file.write_text(flow_content)
    print("Created flow file")

    # Create a runner and deploy the flow
    runner = Runner(name="test-runner", pause_on_shutdown=False)

    runner_crashed = False

    try:
        # Deploy the flow
        deployment_id = await runner.add_flow(
            await flow.from_source(
                source=str(tmp_path),
                entrypoint="my_flow.py:my_flow",
            ),
            name="test-deployment",
        )
        print(f"Deployed flow: {deployment_id}")

        # Create a flow run
        from prefect import get_client

        async with get_client() as client:
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment_id
            )
            print(f"Created flow run: {flow_run.id}")

        # DELETE THE FLOW FILE before execution
        flow_file.unlink()
        print("\n🗑️  DELETED flow file!")
        print("Flow file no longer exists - runner will try to load it for hooks")

        # Execute the flow run
        print("\nExecuting flow run...")
        try:
            await runner.start(run_once=True)
        except Exception as e:
            print(
                f"\n❌ Runner crashed while executing the flow run: {type(e).__name__}: {e}"
            )
            runner_crashed = True
            raise

        async with get_client() as client:
            flow_run = await client.read_flow_run(flow_run.id)

    except Exception as e:
        if not runner_crashed:  # Only if the crash wasn't already reported
            print(f"\n❌ Runner crashed with: {type(e).__name__}: {e}")
            runner_crashed = True

    finally:
        # Cleanup
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)

    assert not runner_crashed, "Runner raised while the flow file was missing"
    # The engine cannot load the deleted file, so the runner reports the run as
    # crashed and then tries, and fails, to load the flow for its on_crashed hooks.
    assert flow_run.state is not None and flow_run.state.is_crashed(), (
        f"Expected the flow run to crash, but its state is {flow_run.state!r}"
    )
    assert crashed_hook_flow_run_ids == [flow_run.id], (
        "The runner did not reach its on_crashed hook handling"
    )
    assert not hook_marker.exists(), (
        "The on_crashed hook ran, so the runner loaded the deleted flow file"
    )
    print("\n✅ Runner survived missing flow file!")
