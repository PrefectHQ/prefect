"""
MRE for GitHub Issue #20558: False task dependency tracking due to Python object id() reuse

This test demonstrates that Prefect incorrectly creates task dependencies when Python
reuses memory addresses (object `id()`) for new objects after previous objects are
garbage collected.

Root Cause:
- `src/prefect/utilities/engine.py` line 584: stores task results keyed by `id(obj)`
- `src/prefect/utilities/engine.py` line 154: `get_state_for_result` looks up by `id(obj)`
- `src/prefect/utilities/engine.py` line 117: `collect_task_run_inputs_sync` uses this
  to determine task dependencies stored in `task_inputs`

When a task completes and its result gets garbage collected, Python can reuse that
memory address for a new object. If a new task is submitted with a parameter that
happens to be allocated at the same memory address, Prefect incorrectly records
a dependency between the tasks in the `task_inputs` field.
"""

import gc
from typing import Any
from uuid import UUID

from prefect import flow, task
from prefect.client.schemas.objects import RunType
from prefect.context import FlowRunContext
from prefect.states import Completed


@task
def simple_task(payload: dict[str, Any]) -> dict[str, Any]:
    """A simple task that returns its input."""
    return {"processed": True, "input": payload}


@task
def identity_task(x: Any) -> Any:
    """Returns input unchanged."""
    return x


class TestFalseDependencyTracking:
    """Tests demonstrating false dependency tracking due to id() reuse."""

    def test_run_results_uses_id_for_tracking(self):
        """
        Demonstrates that run_results uses id() for tracking, which is the root cause.

        This test shows that:
        1. Task results are stored in run_results keyed by id(result)
        2. When a new object gets the same id(), it incorrectly matches the old entry
        """

        @flow
        def test_flow():
            ctx = FlowRunContext.get()
            assert ctx is not None

            # Submit a task and get its result
            future1 = simple_task.submit({"data": "first"})
            result1 = future1.result()

            # The result should be tracked in run_results by its id()
            result1_id = id(result1)
            assert result1_id in ctx.run_results, (
                "Task result should be tracked in run_results by id()"
            )

            # Get the state that was stored
            stored_state, run_type = ctx.run_results[result1_id]
            assert stored_state.state_details.task_run_id == future1.task_run_id

            return {
                "result1_id": result1_id,
                "stored_task_run_id": stored_state.state_details.task_run_id,
                "actual_task_run_id": future1.task_run_id,
            }

        result = test_flow()
        assert result["stored_task_run_id"] == result["actual_task_run_id"]

    def test_stale_entries_cause_false_task_inputs(self):
        """
        Demonstrates that stale entries in run_results cause false task_inputs.

        This test directly simulates what happens when id() is reused:
        1. A task completes and its result is stored in run_results
        2. We simulate id() reuse by manually inserting a stale entry
        3. collect_task_run_inputs_sync incorrectly finds a dependency
        """
        from prefect.utilities.engine import collect_task_run_inputs_sync

        @flow
        def test_flow():
            ctx = FlowRunContext.get()
            assert ctx is not None

            # Create a fake "completed" task state to simulate a previous task
            fake_task_run_id = UUID("12345678-1234-1234-1234-123456789abc")
            fake_state = Completed()
            fake_state.state_details.task_run_id = fake_task_run_id

            # Create a new payload for a task we're about to submit
            new_payload = {"data": "new task payload"}
            payload_id = id(new_payload)

            # Simulate id() reuse: insert a stale entry at the same id
            # This is what happens when Python reuses a memory address
            ctx.run_results[payload_id] = (fake_state, RunType.TASK_RUN)

            # Now check what collect_task_run_inputs_sync returns
            # It should return empty (no dependencies) but due to the bug,
            # it will return the fake task as an input
            task_inputs = collect_task_run_inputs_sync(new_payload)

            # Extract task run IDs from inputs
            input_task_ids = [inp.id for inp in task_inputs]

            return {
                "payload_id": payload_id,
                "fake_task_run_id": fake_task_run_id,
                "collected_input_ids": input_task_ids,
                "has_false_dependency": fake_task_run_id in input_task_ids,
            }

        result = test_flow()

        # This assertion demonstrates the bug:
        # The new payload incorrectly shows as depending on the fake task
        # because it happened to have the same id() as a previous result
        assert result["has_false_dependency"], (
            "BUG: Expected false dependency to be collected due to id() collision. "
            f"Payload id: {result['payload_id']}, "
            f"Fake task run id: {result['fake_task_run_id']}, "
            f"Collected inputs: {result['collected_input_ids']}"
        )

        print(f"\n{'=' * 70}")
        print("BUG DEMONSTRATED: False task_input collected due to id() reuse")
        print(f"{'=' * 70}")
        print(f"New payload's id():     {hex(result['payload_id'])}")
        print(f"Fake task run ID:       {result['fake_task_run_id']}")
        print(f"Collected input IDs:    {result['collected_input_ids']}")
        print(f"False dependency found: {result['has_false_dependency']}")
        print(f"{'=' * 70}")

    def test_id_reuse_with_garbage_collection(self):
        """
        Attempts to demonstrate id() reuse through actual garbage collection.

        Note: This test may be flaky because Python's memory allocator doesn't
        guarantee id() reuse. The test_stale_entries_cause_false_task_inputs
        test above is more reliable for demonstrating the bug.
        """

        @flow
        def test_flow():
            ctx = FlowRunContext.get()
            assert ctx is not None

            # Create and immediately delete many objects to encourage id reuse
            seen_ids: set[int] = set()
            reused_id = None

            # First pass: create objects and record their ids
            for i in range(1000):
                obj = {"iteration": i, "data": "x" * 100}
                obj_id = id(obj)
                if obj_id in seen_ids:
                    reused_id = obj_id
                    break
                seen_ids.add(obj_id)
                del obj
                gc.collect()

            # Second pass: try to find reuse after GC
            if reused_id is None:
                gc.collect()
                for i in range(1000):
                    obj = {"iteration": i + 1000, "data": "y" * 100}
                    obj_id = id(obj)
                    if obj_id in seen_ids:
                        reused_id = obj_id
                        break
                    del obj

            return {
                "total_ids_seen": len(seen_ids),
                "found_reuse": reused_id is not None,
                "reused_id": reused_id,
            }

        result = test_flow()

        print(f"\n{'=' * 70}")
        print("Memory ID Reuse Detection")
        print(f"{'=' * 70}")
        print(f"Total unique IDs seen: {result['total_ids_seen']}")
        print(f"Found ID reuse:        {result['found_reuse']}")
        if result["reused_id"]:
            print(f"Reused ID:             {hex(result['reused_id'])}")
        print(f"{'=' * 70}")

        # This test documents the behavior but doesn't fail if reuse isn't found
        # The important test is test_stale_entries_cause_false_task_inputs

    def test_run_results_grows_unboundedly(self):
        """
        Demonstrates that run_results grows without bound during flow execution.

        This is a secondary issue: even if id() reuse doesn't happen immediately,
        the run_results dict accumulates entries for all task results, which:
        1. Consumes memory
        2. Increases the chance of id() collision over time
        """

        @flow
        def test_flow():
            ctx = FlowRunContext.get()
            assert ctx is not None

            initial_size = len(ctx.run_results)

            # Submit many tasks
            futures = []
            for i in range(20):
                f = simple_task.submit({"index": i})
                futures.append(f)

            # Wait for all to complete
            for f in futures:
                f.result()

            final_size = len(ctx.run_results)

            return {
                "initial_size": initial_size,
                "final_size": final_size,
                "tasks_submitted": len(futures),
                "entries_added": final_size - initial_size,
            }

        result = test_flow()

        print(f"\n{'=' * 70}")
        print("run_results Growth Analysis")
        print(f"{'=' * 70}")
        print(f"Initial run_results size: {result['initial_size']}")
        print(f"Final run_results size:   {result['final_size']}")
        print(f"Tasks submitted:          {result['tasks_submitted']}")
        print(f"Entries added:            {result['entries_added']}")
        print(f"{'=' * 70}")

        # run_results should have grown (entries are never cleaned up)
        assert result["entries_added"] > 0, (
            "run_results should accumulate entries for task results"
        )


def test_false_dependency_from_id_reuse_direct():
    """
    Direct demonstration of the false dependency bug.

    This test bypasses the randomness of Python's memory allocator by
    directly manipulating run_results to simulate id() reuse.
    """
    from prefect.utilities.engine import collect_task_run_inputs_sync

    @flow
    def demo_flow():
        ctx = FlowRunContext.get()
        assert ctx is not None

        # Step 1: Run a task and get its result
        future1 = simple_task.submit({"task": "first"})
        result1 = future1.result()
        first_task_id = future1.task_run_id

        # Verify the result is tracked
        assert id(result1) in ctx.run_results

        # Step 2: Create a completely independent payload for a new task
        independent_payload = {"task": "second", "no_relation": True}

        # Step 3: Simulate what happens when id() is reused
        # Copy the entry from result1's id to independent_payload's id
        # This simulates: result1 gets GC'd, Python reuses its address for independent_payload
        state_entry = ctx.run_results[id(result1)]
        ctx.run_results[id(independent_payload)] = state_entry

        # Step 4: Check what task_inputs would be collected for independent_payload
        collected_inputs = collect_task_run_inputs_sync(independent_payload)
        collected_task_ids = [inp.id for inp in collected_inputs]

        return {
            "first_task_id": first_task_id,
            "independent_payload_id": id(independent_payload),
            "collected_task_ids": collected_task_ids,
            "incorrectly_depends_on_first": first_task_id in collected_task_ids,
        }

    result = demo_flow()

    print(f"\n{'=' * 70}")
    print("DIRECT DEMONSTRATION OF FALSE DEPENDENCY BUG")
    print(f"{'=' * 70}")
    print(f"First task ID:                    {result['first_task_id']}")
    print(f"Independent payload memory addr:  {hex(result['independent_payload_id'])}")
    print(f"Collected task input IDs:         {result['collected_task_ids']}")
    print(f"Incorrectly depends on first:     {result['incorrectly_depends_on_first']}")
    print(f"{'=' * 70}")
    print()
    print("EXPLANATION:")
    print("The 'independent_payload' dict has NO relationship to the first task.")
    print("However, because its memory address (id()) matches a stale entry in")
    print("run_results, Prefect incorrectly records it as a task input dependency.")
    print()
    print("In production, this happens when:")
    print("1. Task A completes, result stored in run_results[id(result_a)]")
    print("2. result_a gets garbage collected, freeing memory address 0x1234")
    print("3. New payload_b is allocated at address 0x1234")
    print("4. Task B submitted with payload_b incorrectly depends on Task A")
    print(f"{'=' * 70}")

    assert result["incorrectly_depends_on_first"], (
        "Bug not demonstrated: expected false dependency to be collected"
    )


if __name__ == "__main__":
    print("=" * 70)
    print("MRE for GitHub Issue #20558")
    print("False task dependency tracking due to Python object id() reuse")
    print("=" * 70)
    print()

    # Run the direct demonstration
    test_false_dependency_from_id_reuse_direct()

    print("\n" + "=" * 70)
    print("Additional tests available via pytest:")
    print("  pytest tests/test_false_dependency_tracking.py -v")
    print("=" * 70)
