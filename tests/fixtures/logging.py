import pytest

from prefect.logging.handlers import APILogHandler
from prefect.settings import PREFECT_LOGGING_TO_API_ENABLED, temporary_settings


@pytest.fixture(autouse=True)
def reset_api_log_handler():
    """
    Since we have a singleton worker for the runtime of the process, we must reset
    it to `None` between tests and we should flush logs before each test exits to
    stop the logging thread.
    """
    yield
    APILogHandler.flush()
    APILogHandler.workers = {}


@pytest.fixture(autouse=True)
def enable_api_log_handler_if_marked(request):
    """
    The `APILogHandler` is disabled during testing by default to reduce overhead.

    Test functions or classes can be marked with `@pytest.mark.enable_api_log_handler`
    to indicate that they need the handler to be reenabled because they are testing
    its functionality.
    """
    marker = request.node.get_closest_marker("enable_api_log_handler")
    if marker is not None:
        with temporary_settings(updates={PREFECT_LOGGING_TO_API_ENABLED: True}):
            yield True
    else:
        yield False
