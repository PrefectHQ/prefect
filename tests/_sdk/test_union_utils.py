"""Tests for union utility functions."""

from prefect._sdk._union import split_union_top_level


class TestSplitUnionTopLevel:
    """Test the split_union_top_level helper function directly."""

    def test_simple_union(self):
        """Simple union should split correctly."""
        assert split_union_top_level("str | int") == ["str", "int"]

    def test_no_union(self):
        """Non-union should return single element."""
        assert split_union_top_level("str") == ["str"]

    def test_union_inside_brackets_not_split(self):
        """Union inside brackets should not be split."""
        assert split_union_top_level("list[str | int]") == ["list[str | int]"]

    def test_union_inside_nested_brackets_not_split(self):
        """Union inside nested brackets should not be split."""
        result = split_union_top_level("dict[str, list[int | float]]")
        assert result == ["dict[str, list[int | float]]"]

    def test_top_level_with_nested_brackets(self):
        """Top-level union with nested brackets should split correctly."""
        result = split_union_top_level("list[str | int] | None")
        assert result == ["list[str | int]", "None"]

    def test_union_inside_single_quotes_not_split(self):
        """Union inside single quotes should not be split."""
        result = split_union_top_level("Literal['a | b']")
        assert result == ["Literal['a | b']"]

    def test_union_inside_double_quotes_not_split(self):
        """Union inside double quotes should not be split."""
        result = split_union_top_level('Literal["a | b"]')
        assert result == ['Literal["a | b"]']

    def test_escaped_quotes_handled(self):
        """Escaped quotes inside strings should be handled."""
        result = split_union_top_level(r"Literal['it\'s | ok'] | int")
        assert result == [r"Literal['it\'s | ok']", "int"]

    def test_multiple_literals_in_union(self):
        """Multiple Literals in a union should work."""
        result = split_union_top_level("Literal['a | b', 'c'] | int | None")
        assert result == ["Literal['a | b', 'c']", "int", "None"]

    def test_empty_string(self):
        """Empty string should return empty list."""
        assert split_union_top_level("") == []

    def test_whitespace_handling(self):
        """Whitespace should be trimmed from parts."""
        result = split_union_top_level("  str  |  int  ")
        assert result == ["str", "int"]

    def test_trailing_backslash(self):
        """Trailing backslash should be handled gracefully."""
        # Edge case: backslash at end of string
        result = split_union_top_level("Literal['test\\")
        assert result == ["Literal['test\\"]
