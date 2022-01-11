import pytest
from prefect.logging.handlers import OrionHandler
from prefect.utilities.settings import temporary_settings


@pytest.fixture(autouse=True)
def reset_orion_handler():
    """
    Since we have a singleton worker for the runtime of the process, we must reset
    it to `None` between tests and we should flush logs before each test exits to
    stop the logging thread.
    """
    yield
    if OrionHandler.worker:
        OrionHandler.flush()
        OrionHandler.worker = None


@pytest.fixture(autouse=True)
def enable_orion_handler_if_marked(request):
    """
    The `OrionHandler` is disabled during testing by default to reduce overhead.

    Test functions or classes can be marked with `@pytest.mark.enable_orion_handler`
    to indicate that they need the handler to be reenabled because they are testing
    its functionality.
    """
    marker = request.node.get_closest_marker("enable_orion_handler")
    if marker is not None:
        with temporary_settings(PREFECT_LOGGING_ORION_ENABLED="True"):
            yield True
    else:
        yield False
