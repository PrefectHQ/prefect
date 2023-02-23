from unittest.mock import MagicMock

import pytest

from prefect._internal.concurrency.runtime import RuntimeThread


def test_runtime_with_failure_in_loop_start():
    runtime = RuntimeThread()

    # Simulate a failure during loop thread start
    runtime._ready_future.set_result = MagicMock(side_effect=ValueError("test"))

    # The error should propagate to the main thread
    with pytest.raises(ValueError, match="test"):
        runtime.start()
