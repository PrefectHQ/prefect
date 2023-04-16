import pytest
import warnings


def test_example_one():
    with pytest.warns(UserWarning):
        warnings.warn(1)

    # This test passes but should raise a `TypeError` as demonstrated in `example_two`


def test_example_two():
    with pytest.raises(TypeError):
        warnings.warn(1)

