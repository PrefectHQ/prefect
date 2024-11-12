import pytest

from prefect.telemetry.test_utils import InstrumentationTester


@pytest.fixture
def instrumentation():
    instrumentation_tester = InstrumentationTester()
    yield instrumentation_tester
    instrumentation_tester.reset()
