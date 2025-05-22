import asyncio
import time

import pytest

from prefect._internal.concurrency.calls import Call
from prefect._internal.concurrency.cancellation import CancelledError


def identity(x):
    return x


async def aidentity(x):
    return x


def raises(exc):
    raise exc


async def araises(exc):
    raise exc


@pytest.mark.parametrize("fn", [identity, aidentity])
def test_sync_call(fn):
    call = Call.new(fn, 1)
    assert call() == 1


async def test_async_call_sync_function():
    call = Call.new(identity, 1)
    assert call() == 1


async def test_async_call_async_function():
    call = Call.new(aidentity, 1)
    assert await call() == 1


@pytest.mark.parametrize("fn", [identity, aidentity])
def test_call_result(fn):
    call = Call.new(fn, 1)
    call.run()
    assert call.result() == 1


@pytest.mark.parametrize("fn", [raises, araises])
def test_call_result_exception(fn):
    call = Call.new(fn, ValueError("test"))
    call.run()
    with pytest.raises(ValueError, match="test"):
        call.result()


@pytest.mark.parametrize("fn", [raises, araises])
def test_call_result_base_exception(fn):
    call = Call.new(fn, BaseException("test"))
    call.run()
    with pytest.raises(BaseException, match="test"):
        call.result()


@pytest.mark.parametrize(
    "exception_cls", [BaseException, KeyboardInterrupt, SystemExit]
)
async def test_async_call_result_base_exception_with_event_loop(exception_cls):
    call = Call.new(araises, exception_cls("test"))
    await call.run()
    with pytest.raises(exception_cls, match="test"):
        call.result()


@pytest.mark.parametrize("fn", [time.sleep, asyncio.sleep], ids=["sync", "async"])
def test_call_timeout(fn):
    call = Call.new(fn, 2)
    call.set_timeout(1)
    call.run()
    with pytest.raises(CancelledError):
        call.result()
    assert call.cancelled()


def test_call_future_cancelled():
    call = Call.new(identity, 2)
    call.future.cancel()
    call.run()
    with pytest.raises(CancelledError):
        call.result()
    assert call.cancelled()


def test_call_equality_after_args_kwargs_deletion_targets():
    """
    Tests Call.__eq__ behavior after args/kwargs deletion, focusing on:
        1. No AttributeError is raised
        2. A Call object with deleted args/kwargs compares as unequal to
       an otherwise identical Call that still has them
        3. A Call object (with or without args/kwargs) compares equal to itself
        4. Two distinct Call objects, both with args/kwargs deleted but otherwise
       identical before deletion, will compare as unequal with this __eq__ logic
       (because they are not the same instance and the try-except path is hit)

    This is a regression test for https://github.com/PrefectHQ/prefect/issues/18080
    """

    def create_call(val, kwarg_val="default"):
        return Call.new(identity, val, k=kwarg_val)

    # Scenario 1: Baseline - original call and a structurally similar one
    call_orig_A = create_call(1, kwarg_val="A")
    call_structurally_same_as_A = create_call(1, kwarg_val="A")

    # With the current simple __eq__, these will be unequal due to different Future instances.
    assert call_orig_A != call_structurally_same_as_A, (
        "Newly created identical calls should differ due to Future identity"
    )

    # Scenario 2: Mutate a call by deleting args/kwargs
    call_mutated_A = create_call(1, kwarg_val="A")
    del call_mutated_A.args
    del call_mutated_A.kwargs

    assert not hasattr(call_mutated_A, "args")
    assert not hasattr(call_mutated_A, "kwargs")

    try:
        assert call_mutated_A != call_orig_A, (
            "Mutated call (no args/kwargs) should be unequal to original call (with args/kwargs)"
        )
        assert not (call_mutated_A == call_orig_A)
    except AttributeError:
        pytest.fail("AttributeError during comparison: mutated_call vs original_call")

    # Test Point 3: Self-comparison (with and without args/kwargs)
    try:
        assert call_orig_A == call_orig_A, "Original call should be equal to itself"
        assert call_mutated_A == call_mutated_A, (
            "Mutated call should be equal to itself"
        )
    except AttributeError:
        pytest.fail("AttributeError during self-comparison")

    # Test Point 4: Two distinct calls, both mutated similarly
    call_mutated_B = create_call(1, kwarg_val="A")
    del call_mutated_B.args
    del call_mutated_B.kwargs

    assert call_mutated_A is not call_mutated_B  # Ensure they are different instances

    try:
        # With the current __eq__, these are unequal because `call_mutated_A.args` (or `call_mutated_B.args`)
        # will raise AttributeError in the try block, leading to `return False`.
        assert call_mutated_A != call_mutated_B, (
            "Two distinct, similarly mutated calls should be unequal with this __eq__ logic"
        )
    except AttributeError:
        pytest.fail("AttributeError during comparison of two distinct mutated calls")

    # Test a different scenario: one call with args, one without args, different original values
    call_C_has_args = create_call(3, kwarg_val="C")
    call_D_no_args = create_call(4, kwarg_val="D")  # different original content
    del call_D_no_args.args
    del call_D_no_args.kwargs

    try:
        assert call_C_has_args != call_D_no_args
    except AttributeError:
        pytest.fail("AttributeError: call_C_has_args vs call_D_no_args")
