import pytest
from prefect.utilities.logging import OrionHandler


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
