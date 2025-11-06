"""Tests for environment variable parsing utilities."""

from prefect.utilities.env import parse_bool_env


class TestParseBoolEnv:
    """Tests for parse_bool_env function."""

    def test_truthy_values(self, monkeypatch):
        """Test that common truthy values are parsed correctly."""
        truthy_values = [
            "1",
            "true",
            "True",
            "TRUE",
            "t",
            "T",
            "yes",
            "Yes",
            "YES",
            "y",
            "Y",
            "on",
            "On",
            "ON",
        ]

        for value in truthy_values:
            monkeypatch.setenv("TEST_FLAG", value)
            assert parse_bool_env("TEST_FLAG") is True, (
                f"Expected {value!r} to be truthy"
            )

    def test_falsy_values(self, monkeypatch):
        """Test that common falsy values are parsed correctly."""
        falsy_values = [
            "0",
            "false",
            "False",
            "FALSE",
            "f",
            "F",
            "no",
            "No",
            "NO",
            "n",
            "N",
            "off",
            "Off",
            "OFF",
        ]

        for value in falsy_values:
            monkeypatch.setenv("TEST_FLAG", value)
            assert parse_bool_env("TEST_FLAG") is False, (
                f"Expected {value!r} to be falsy"
            )

    def test_unknown_values_default_to_false(self, monkeypatch):
        """Test that unknown values default to False."""
        unknown_values = ["2", "maybe", "unknown", "random"]

        for value in unknown_values:
            monkeypatch.setenv("TEST_FLAG", value)
            assert parse_bool_env("TEST_FLAG") is False, (
                f"Expected {value!r} to default to False"
            )

    def test_unset_variable_returns_default(self, monkeypatch):
        """Test that unset variables return the default value."""
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert parse_bool_env("TEST_FLAG") is False
        assert parse_bool_env("TEST_FLAG", default=True) is True
        assert parse_bool_env("TEST_FLAG", default=False) is False

    def test_empty_string_returns_default(self, monkeypatch):
        """Test that empty string returns the default value (Pydantic raises ValidationError)."""
        monkeypatch.setenv("TEST_FLAG", "")
        assert parse_bool_env("TEST_FLAG") is False
        assert parse_bool_env("TEST_FLAG", default=True) is True

    def test_case_insensitive(self, monkeypatch):
        """Test that parsing is case-insensitive."""
        test_cases = [
            ("TrUe", True),
            ("FaLsE", False),
            ("YeS", True),
            ("nO", False),
        ]

        for value, expected in test_cases:
            monkeypatch.setenv("TEST_FLAG", value)
            assert parse_bool_env("TEST_FLAG") is expected, (
                f"Expected {value!r} to be {expected}"
            )
