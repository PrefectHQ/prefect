"""
Demonstrate that process workers are resilient when flow files go missing.

Workers should continue operating when they can't load flow files for hook execution.
"""

import shutil
from pathlib import Path
from textwrap import dedent

from prefect import flow
from prefect.runner import Runner


async def test_runner_resilience_with_missing_file(tmp_path: Path):
    """Test that runners handle missing flow files gracefully"""

    flow_file = tmp_path / "my_flow.py"

    print(f"Working in: {tmp_path}")

    # Create a flow file with on_crashed hook
    flow_content = dedent("""
        from prefect import flow
        
        def my_hook(flow, flow_run, state):
            print("This hook won't run because the file will be missing!")
        
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
    # A final state shows the runner picked up and finished the run, rather than
    # exiting without submitting it.
    assert flow_run.state is not None and flow_run.state.is_final(), (
        f"Expected the flow run to finish, but its state is {flow_run.state!r}"
    )
    print(f"\n✅ Runner survived missing flow file! Final state: {flow_run.state.name}")
