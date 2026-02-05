"""
Regression test for GitHub Issue #20558: False task dependency tracking due to Python object id() reuse

This test verifies that Prefect does NOT incorrectly create task dependencies when Python
reuses memory addresses (object `id()`) for new objects after previous objects are
garbage collected.

The bug was in:
- `src/prefect/utilities/engine.py`: stores task results keyed by `id(obj)` in `run_results`
- When a task completes and its result gets garbage collected, Python can reuse that memory address
- If a new task is submitted with a parameter at the same memory address, Prefect incorrectly
  recorded a dependency between the tasks

The fix stores a reference to the object and verifies identity on lookup, preventing false
dependencies when id() is reused.

This test asserts the CORRECT behavior: no false dependencies should be collected.
"""

from typing import Any
from uuid import UUID

from prefect import flow, task
from prefect.client.schemas.objects import RunType
from prefect.context import FlowRunContext
from prefect.states import Completed
from prefect.utilities.engine import collect_task_run_inputs_sync


@task
def simple_task(payload: dict[str, Any]) -> dict[str, Any]:
    """A simple task that returns its input."""
    return {"processed": True, "input": payload}


class TestNoFalseDependencyFromIdReuse:
    """
    Regression tests ensuring no false dependencies are created due to id() reuse.

    These tests assert the CORRECT behavior - they should FAIL before the fix
    and PASS after the fix is applied.
    """

    def test_no_false_dependency_when_id_is_reused(self):
        """
        Regression test: When a new object happens to have the same id() as a
        previous task result, it should NOT be incorrectly identified as depending
        on that task.

        This test simulates id() reuse by manually inserting a stale entry into
        run_results at the same id as a new payload, but with a DIFFERENT object
        reference. The correct behavior is that collect_task_run_inputs_sync
        should NOT return false dependencies because the object identity check
        will fail.
        """

        @flow
        def test_flow():
            ctx = FlowRunContext.get()
            assert ctx is not None

            # Create a fake "completed" task state to simulate a previous task
            fake_task_run_id = UUID("12345678-1234-1234-1234-123456789abc")
            fake_state = Completed()
            fake_state.state_details.task_run_id = fake_task_run_id

            # Create a "previous" object that we'll pretend was garbage collected
            old_object = {"data": "old task result"}

            # Create a new payload for a task we're about to submit
            new_payload = {"data": "new task payload"}
            payload_id = id(new_payload)

            # Simulate id() reuse: insert a stale entry at the new payload's id
            # but with a reference to the OLD object (simulating what would happen
            # if the old object was at this address before being GC'd)
            # The key insight: the entry points to old_object, not new_payload
            ctx.run_results[payload_id] = (fake_state, RunType.TASK_RUN, old_object)

            # Collect task inputs for the new payload
            task_inputs = collect_task_run_inputs_sync(new_payload)

            # Extract task run IDs from inputs
            input_task_ids = [inp.id for inp in task_inputs]

            return {
                "fake_task_run_id": fake_task_run_id,
                "collected_input_ids": input_task_ids,
            }

        result = test_flow()

        # CORRECT BEHAVIOR: The new payload should NOT depend on the fake task
        # because the identity check (stored_obj is not obj) will fail
        assert result["fake_task_run_id"] not in result["collected_input_ids"], (
            f"False dependency detected! New payload incorrectly depends on task "
            f"{result['fake_task_run_id']} due to id() reuse. "
            f"Collected inputs: {result['collected_input_ids']}"
        )

    def test_no_false_dependency_after_task_completion(self):
        """
        Regression test: After a task completes and we create a new independent
        object that happens to reuse the same memory address, submitting a new
        task with that object should NOT create a false dependency.

        This test uses actual task execution and then simulates id() reuse by
        copying the stale entry to the new object's id. The identity check
        should prevent the false dependency.
        """

        @flow
        def test_flow():
            ctx = FlowRunContext.get()
            assert ctx is not None

            # Step 1: Run a task and get its result
            future1 = simple_task.submit({"task": "first"})
            result1 = future1.result()
            first_task_id = future1.task_run_id

            # Verify the result is tracked
            assert id(result1) in ctx.run_results

            # Step 2: Create a completely independent payload
            independent_payload = {"task": "second", "no_relation": True}

            # Step 3: Simulate id() reuse by copying the stale entry
            # This simulates: result1 gets GC'd, Python reuses its address
            # The entry still references result1, not independent_payload
            state_entry = ctx.run_results[id(result1)]
            ctx.run_results[id(independent_payload)] = state_entry

            # Step 4: Check what task_inputs would be collected
            collected_inputs = collect_task_run_inputs_sync(independent_payload)
            collected_task_ids = [inp.id for inp in collected_inputs]

            return {
                "first_task_id": first_task_id,
                "collected_task_ids": collected_task_ids,
            }

        result = test_flow()

        # CORRECT BEHAVIOR: The independent payload should NOT depend on the first task
        # because the identity check will fail (stored object is result1, not independent_payload)
        assert result["first_task_id"] not in result["collected_task_ids"], (
            f"False dependency detected! Independent payload incorrectly depends on "
            f"first task {result['first_task_id']} due to id() reuse. "
            f"Collected inputs: {result['collected_task_ids']}"
        )

    def test_correct_dependency_when_same_object(self):
        """
        Verify that legitimate dependencies are still tracked correctly.

        When the SAME object is passed to collect_task_run_inputs_sync that was
        originally stored, it should correctly identify the dependency.
        """

        @flow
        def test_flow():
            ctx = FlowRunContext.get()
            assert ctx is not None

            # Run a task and get its result
            future1 = simple_task.submit({"task": "first"})
            result1 = future1.result()
            first_task_id = future1.task_run_id

            # Verify the result is tracked
            assert id(result1) in ctx.run_results

            # Collect task inputs for the SAME result object
            # This should correctly identify the dependency
            collected_inputs = collect_task_run_inputs_sync(result1)
            collected_task_ids = [inp.id for inp in collected_inputs]

            return {
                "first_task_id": first_task_id,
                "collected_task_ids": collected_task_ids,
            }

        result = test_flow()

        # CORRECT BEHAVIOR: The same object should be recognized as a dependency
        assert result["first_task_id"] in result["collected_task_ids"], (
            f"Legitimate dependency not detected! Result object should depend on "
            f"task {result['first_task_id']}. "
            f"Collected inputs: {result['collected_task_ids']}"
        )
