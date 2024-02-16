import random

import pytest

from prefect.utilities.annotations import unmapped

pytestmark = pytest.mark.disable_clear_db


class TestUnmapped:
    def test_always_returns_same_value(self):
        thing = unmapped("hello")

        for _ in range(10):
            assert thing[random.randint(0, 100)] == "hello"
