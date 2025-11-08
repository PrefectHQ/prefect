import pytest
from prefect.transformations.round_decimal_transform import round_decimal_transform

def test_round_decimal_to_two_places():
    assert round_decimal_transform(3.14159) == 3.14

def test_round_decimal_to_three_places():
    assert round_decimal_transform(2.71828, 3) == 2.718

def test_round_decimal_negative_value():
    assert round_decimal_transform(-1.2345, 2) == -1.23

def test_round_decimal_none_value():
    assert round_decimal_transform(None) is None

