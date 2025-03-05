import random

from prefect.utilities.annotations import freeze, unmapped


class TestUnmapped:
    def test_always_returns_same_value(self):
        thing = unmapped("hello")

        for _ in range(10):
            assert thing[random.randint(0, 100)] == "hello"


class TestFreeze:
    def test_round_trip(self):
        assert freeze("hello").unfreeze() == "hello"
