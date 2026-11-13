from contextlib import ExitStack

import pytest
from docket import Docket
from docket.dependencies import current_docket

from prefect.server.utilities._docket import get_docket, serving_docket


@pytest.mark.parametrize("first_to_stop", [0, 1])
def test_overlapping_serving_dockets(first_to_stop: int):
    dockets = [
        Docket(name="first", url="memory://"),
        Docket(name="second", url="memory://"),
    ]
    assert get_docket() is None

    with ExitStack() as first, ExitStack() as second:
        first.enter_context(serving_docket(dockets[0]))
        second.enter_context(serving_docket(dockets[1]))
        assert get_docket() is dockets[1]

        (first, second)[first_to_stop].close()
        assert get_docket() is dockets[1 - first_to_stop]

    assert get_docket() is None


def test_overlapping_lifespans_of_the_same_docket():
    docket = Docket(name="shared", url="memory://")

    with ExitStack() as first, ExitStack() as second:
        first.enter_context(serving_docket(docket))
        second.enter_context(serving_docket(docket))
        first.close()
        assert get_docket() is docket

    assert get_docket() is None


def test_serving_docket_is_removed_on_error():
    docket = Docket(name="failing", url="memory://")

    with pytest.raises(RuntimeError, match="lifespan failed"), serving_docket(docket):
        assert get_docket() is docket
        raise RuntimeError("lifespan failed")

    assert get_docket() is None


def test_task_docket_takes_precedence():
    server_docket = Docket(name="server", url="memory://")
    task_docket = Docket(name="task", url="memory://")

    with serving_docket(server_docket):
        token = current_docket.set(task_docket)
        try:
            assert get_docket() is task_docket
        finally:
            current_docket.reset(token)

        assert get_docket() is server_docket

    assert get_docket() is None
