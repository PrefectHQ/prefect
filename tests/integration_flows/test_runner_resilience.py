import asyncio
import shutil
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

from prefect import flow
from prefect.runner import Runner

"\nDemonstrate that process workers are resilient when flow files go missing.\n\nWorkers should continue operating when they can't load flow files for hook execution.\n"


async def test_runner_resilience_with_missing_file():
    """Test that runners handle missing flow files gracefully"""
    temp_dir = Path(tempfile.mkdtemp())
    flow_file = temp_dir / "my_flow.py"
    print(f"Working in: {temp_dir}")
    flow_content = dedent(
        '\n        from prefect import flow\n        \n        def my_hook(flow, flow_run, state):\n            print("This hook won\'t run because the file will be missing!")\n        \n        @flow(on_crashed=[my_hook])\n        def my_flow():\n            print("Flow executing...")\n            raise RuntimeError("Intentional crash to trigger hooks")\n    '
    )
    flow_file.write_text(flow_content)
    print("Created flow file")
    runner = Runner(name="test-runner")
    runner_crashed = False
    try:
        async with runner:
            deployment_id = await runner.add_flow(
                await flow.from_source(
                    source=str(temp_dir), entrypoint="my_flow.py:my_flow"
                ),
                name="test-deployment",
            )
            print(f"Deployed flow: {deployment_id}")
            from prefect import get_client

            async with get_client() as client:
                flow_run = await client.create_flow_run_from_deployment(
                    deployment_id=deployment_id
                )
                print(f"Created flow run: {flow_run.id}")
            flow_file.unlink()
            print("\n🗑️  DELETED flow file!")
            print("Flow file no longer exists - runner will try to load it for hooks")
            print("\nExecuting flow run...")
            try:
                process = await runner.execute_flow_run(flow_run.id)
                print(
                    f"Process exited with code: {(process.returncode if process else 'None')}"
                )
            except Exception as e:
                print(
                    f"\n❌ Runner crashed during execute_flow_run: {type(e).__name__}: {e}"
                )
                runner_crashed = True
                raise
    except Exception as e:
        if not runner_crashed:
            print(f"\n❌ Runner crashed with: {type(e).__name__}: {e}")
            runner_crashed = True
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
    if not runner_crashed:
        print("\n✅ Runner survived missing flow file!")
        print("This shows the fix is working - runners are resilient to missing files")
        return True
    else:
        print("\nRunner crashed - this demonstrates the bug")
        return False


def main():
    """Run the test"""
    try:
        success = asyncio.run(test_runner_resilience_with_missing_file())
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"\nTest failed with exception: {type(e).__name__}: {e}")
        sys.exit(1)


def test_runner_resilience():
    """Test for runner_resilience."""
    main()
