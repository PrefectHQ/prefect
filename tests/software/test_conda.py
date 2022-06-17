from contextlib import nullcontext

import pytest

from prefect.software.conda import CONDA_REQUIREMENT, CondaRequirement

CONDA_TEST_CASES = [
    ("x", {"name": "x"}),
    ("x=", None),
    ("x=1", {"name": "x", "version_specifier": "=1", "version": "1"}),
    ("x>=1", {"name": "x", "version_specifier": ">=1", "version": "1"}),
    ("x>1", {"name": "x", "version_specifier": ">1", "version": "1"}),
    ("x=1.2.3", {"name": "x", "version_specifier": "=1.2.3", "version": "1.2.3"}),
    ("x=1.2b1", {"name": "x", "version_specifier": "=1.2b1", "version": "1.2b1"}),
    ("x=1.2b1=", None),
    (
        "x=1.2b1=ashfa_0",
        {
            "name": "x",
            "version_specifier": "=1.2b1",
            "version": "1.2b1",
            "build_specifier": "=ashfa_0",
            "build": "ashfa_0",
        },
    ),
]


@pytest.mark.parametrize(
    "input,expected",
    CONDA_TEST_CASES,
)
def test_parsing(input, expected):
    result = CONDA_REQUIREMENT.match(input)
    if expected is None:
        assert (
            result is None
        ), f"Input {input!r} should not be valid, matched {result.groups()}"
    else:
        assert result is not None

        groups = result.groupdict()
        for key, value in tuple(groups.items()):
            if key not in expected:
                assert value is None, f"{key!r} should not have a match."
                groups.pop(key)

        assert groups == expected


class TestCondaRequirement:
    @pytest.mark.parametrize(
        "input,expected",
        CONDA_TEST_CASES,
    )
    def test_init(self, input, expected):
        raises_on_bad_match = (
            pytest.raises(ValueError, match="Invalid requirement")
            if expected is None
            else nullcontext()
        )

        with raises_on_bad_match:
            requirement = CondaRequirement(input)

        if expected:
            for key, value in expected.items():
                assert getattr(requirement, key) == value

    def test_to_string_is_original(self):
        assert str(CondaRequirement("x=1.2")) == "x=1.2"

    def test_equality(self):
        assert CondaRequirement("x=1.2") == CondaRequirement("x=1.2")

    def test_inequality(self):
        assert CondaRequirement("x") != CondaRequirement("x=1.2")
