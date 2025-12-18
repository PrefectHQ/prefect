"""
It's a test file for reproducing the 
issue #19404 which can be removed before merge
"""


import asyncio
from prefect import flow, states
from prefect.client.orchestration import get_client


@flow
async def long_running_flow():
    print("Flow started, running for 30 seconds...")
    await asyncio.sleep(30)
    print("Flow completed")


async def main():
    async with get_client() as client:
        # Create deployment without concurrency limit
        flow_id = await client.create_flow(long_running_flow)
        deployment_id = await client.create_deployment(
            flow_id=flow_id,
            name="test-deployment-19404",
            entrypoint=f"{__file__}:long_running_flow",
            enforce_parameter_schema=False,
        )

        # Create 5 flow runs and transition to RUNNING
        run_ids = []
        for i in range(5):
            run = await client.create_flow_run_from_deployment(deployment_id)
            run_ids.append(run.id)
            await client.set_flow_run_state(flow_run_id=run.id, state=states.Pending())
            await client.set_flow_run_state(flow_run_id=run.id, state=states.Running())

        # Check active slots BEFORE setting limit (should be 0)
        deployment_before = await client.read_deployment(deployment_id)
        print(f"\nBefore setting limit:")
        print(f"  Deployment has concurrency_limit: {deployment_before.concurrency_limit}")
        if deployment_before.global_concurrency_limit:
            print(f"  Active slots: {deployment_before.global_concurrency_limit.active_slots}")
            print(f"  Limit: {deployment_before.global_concurrency_limit.limit}")
        
        # Set deployment concurrency limit to 2 while flows are running
        from prefect.client.schemas.actions import DeploymentUpdate
        await client.update_deployment(
            deployment_id=deployment_id,
            deployment=DeploymentUpdate(concurrency_limit=2),
        )

        # Check active slots AFTER setting limit
        deployment_after = await client.read_deployment(deployment_id)
        print(f"\nAfter setting limit to 2:")
        print(f"  Deployment has concurrency_limit: {deployment_after.concurrency_limit}")
        if deployment_after.global_concurrency_limit:
            active_slots = deployment_after.global_concurrency_limit.active_slots
            limit = deployment_after.global_concurrency_limit.limit
            print(f"  Active slots: {active_slots}")
            print(f"  Limit: {limit}")
            
            # With the fix: should be 2 (first 2 RUNNING flows acquired slots)
            # Without the fix: should be 0 (RUNNING flows don't have slots)
            if active_slots == 2:
                print("  ✅ Active slots = 2 (fix is working! RUNNING flows acquired slots)")
            elif active_slots == 0:
                print("  ❌ Active slots = 0 (fix NOT working - RUNNING flows didn't acquire slots)")
            else:
                print(f"  ⚠️  Active slots = {active_slots} (unexpected)")

        # Result: All 5 flows remain RUNNING
        print(f"\nRUNNING flows:")
        for run_id in run_ids:
            run = await client.read_flow_run(run_id)
            print(f"  {run.name}: {run.state_type.value}")
        
        # Try to create a new flow run - it should be blocked or enqueued
        print("\nAttempting to create a new flow run after setting limit to 2...")
        new_run = await client.create_flow_run_from_deployment(deployment_id)
        new_run_state = await client.read_flow_run(new_run.id)
        print(f"New run state: {new_run_state.state_type.value}")
        
        # Check active slots after trying to create new run
        deployment_final = await client.read_deployment(deployment_id)
        if deployment_final.global_concurrency_limit:
            final_active = deployment_final.global_concurrency_limit.active_slots
            print(f"Active slots after new run attempt: {final_active}")
        
        if new_run_state.state_type.value == "SCHEDULED":
            if active_slots == 2:
                print("✅ New flow run is blocked AND RUNNING flows have slots (fix working!)")
            else:
                print("⚠️  New flow run is blocked, but RUNNING flows don't have slots (may be blocking for wrong reason)")
        else:
            print("⚠️  New flow run is not blocked (issue not fixed)")


if __name__ == "__main__":
    asyncio.run(main())

