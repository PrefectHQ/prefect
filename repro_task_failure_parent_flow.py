"""
Reproduction script demonstrating behavior differences when child flows/tasks fail.

SCENARIO 1: Direct subflow call - Failure DOES propagate to parent
SCENARIO 2: run_deployment() - Failure does NOT automatically propagate to parent

This script demonstrates the confusing behavior reported in:
- https://github.com/PrefectHQ/prefect/discussions/19500
- https://github.com/PrefectHQ/prefect/issues/19479
"""

from prefect import flow, task


# =============================================================================
# SCENARIO 1: Direct subflow - Failure propagates automatically
# =============================================================================

@flow
def child_flow_that_fails():
    """A child flow that always fails."""
    raise ValueError("Child flow failed!")


@flow
def parent_flow_direct_subflow():
    """
    Parent flow that calls a child flow directly.

    When the child flow fails, this parent WILL be marked as FAILED
    because of the "aggregate rule" in Prefect's state handling.
    """
    print("Parent: calling child flow directly...")
    child_flow_that_fails()
    print("Parent: this line won't be reached if child fails")
    return "Success"


# =============================================================================
# SCENARIO 2: run_deployment() - Failure does NOT propagate automatically
# =============================================================================

@flow
def child_flow_for_deployment():
    """A child flow deployed separately that fails."""
    raise ValueError("Deployed child flow failed!")


@flow
def parent_flow_via_deployment():
    """
    Parent flow that triggers a child via run_deployment().

    When the child deployment fails:
    - The run_deployment() call returns a FlowRun object
    - The parent flow does NOT automatically fail
    - The parent completes "successfully" even though child failed
    - User must manually check flow_run.state.is_failed()
    """
    from prefect.deployments import run_deployment

    print("Parent: triggering child deployment...")

    # This returns the child flow run, but does NOT raise on failure!
    child_run = run_deployment(
        name="child-flow-for-deployment/child-deployment",
        timeout=60,
    )

    print(f"Parent: child run state = {child_run.state}")
    print(f"Parent: child run is_failed = {child_run.state.is_failed()}")

    # Parent continues and completes successfully even if child failed!
    return "Parent completed (even if child failed)"


# =============================================================================
# SCENARIO 3: Task that fails - Understanding the "aggregate rule"
# =============================================================================

@task
def task_that_fails():
    """A task that always fails."""
    raise ValueError("Task failed!")


@flow
def parent_flow_with_failing_task():
    """
    Parent flow with a failing task.

    When a task raises an exception, the parent flow WILL fail because
    the exception propagates up and is not caught.
    """
    print("Parent: calling task...")
    task_that_fails()  # This raises, parent fails
    return "Success"


@flow
def parent_flow_with_submitted_task():
    """
    Parent flow that submits a task and gets its result.

    When using .submit(), you get a future. The parent flow's final state
    depends on whether you call .result() or return the future.
    """
    print("Parent: submitting task...")
    future = task_that_fails.submit()

    # Option 1: Call .result() - this raises the exception
    # result = future.result()  # Would raise ValueError

    # Option 2: Return the future - parent checks aggregate state
    # If you return the future/state, parent applies the "aggregate rule"
    return future  # Parent will be FAILED because child state is FAILED


# =============================================================================
# WORKAROUND for run_deployment(): Manual failure check
# =============================================================================

@flow
def parent_flow_deployment_with_manual_check():
    """
    Workaround: Manually check and raise if child deployment fails.

    This is what users must do today to propagate deployment failures.
    The feature request (#19479) asks for this to be a parameter.
    """
    from prefect.deployments import run_deployment

    print("Parent: triggering child deployment...")

    child_run = run_deployment(
        name="child-flow-for-deployment/child-deployment",
        timeout=60,
    )

    # Manual check - THIS IS THE WORKAROUND
    if child_run.state.is_failed() or child_run.state.is_crashed():
        raise RuntimeError(
            f"Child deployment failed with state: {child_run.state.name}"
        )

    return "Parent completed successfully"


# =============================================================================
# Summary explanation
# =============================================================================

if __name__ == "__main__":
    print("""
=============================================================================
SUMMARY: Why parent flows don't automatically fail when deployments fail
=============================================================================

The confusion comes from TWO DIFFERENT BEHAVIORS:

1. DIRECT SUBFLOWS (child_flow() called directly):
   - The child flow runs in the SAME process as parent
   - Exceptions propagate up naturally (Python behavior)
   - Prefect's "aggregate rule" marks parent as FAILED if any child states
     are not COMPLETED
   - This is the EXPECTED behavior users anticipate

2. DEPLOYMENT SUBFLOWS (run_deployment()):
   - The child flow runs in a DIFFERENT process/worker
   - run_deployment() just returns the FlowRun metadata
   - NO automatic exception is raised if child fails
   - Parent continues executing and may complete "successfully"
   - The "dummy task" created to track the subflow is not updated

WHY THE DIFFERENCE?
   - run_deployment() was designed for async orchestration
   - Sometimes you want to fire-and-forget (timeout=0)
   - Sometimes you want to handle failures gracefully
   - The current design gives flexibility but causes confusion

THE FEATURE REQUEST (#19479):
   - Add `raise_on_failure=True` parameter to run_deployment()
   - When True, automatically raise exception if child fails
   - Similar to how PrefectFuture.result(raise_on_failure=True) works

WORKAROUND TODAY:
   child_run = run_deployment(...)
   if child_run.state.is_failed():
       raise RuntimeError(f"Child failed: {child_run.state}")

=============================================================================
""")
