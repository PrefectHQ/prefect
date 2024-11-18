import pytest
from tests.telemetry.instrumentation_tester import InstrumentationTester


@pytest.fixture
def instrumentation():
    instrumentation_tester = InstrumentationTester()
    yield instrumentation_tester
    instrumentation_tester.reset()
