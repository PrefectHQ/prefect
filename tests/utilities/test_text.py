import io

import pytest
from rich.table import Table

from prefect.utilities.text import _SafeFileWrapper, fuzzy_match_string, get_console


@pytest.mark.parametrize(
    "word, possibilities, expected",
    [
        ("hello", ["hello", "world"], "hello"),
        ("Hello", ["hello", "world"], "hello"),
        ("colour", ["color", "flavour"], "color"),
        ("progam", ["program", "progress"], "program"),  # noqa
        ("pythn", ["python", "cython"], "python"),
        ("cat", ["dog", "pig", "cow"], None),
    ],
    ids=[
        "Exact match",
        "Case insensitive match",
        "Close match - British vs American spelling",
        "Missing character",
        "Multiple close matches",
        "No close matches within threshold",
    ],
)
def test_fuzzy_match_string(word, possibilities, expected):
    assert fuzzy_match_string(word, possibilities) == expected


class TestSafeFileWrapper:
    """Tests for _SafeFileWrapper which handles UnicodeEncodeError on write."""

    def test_normal_write_passes_through(self):
        buf = io.StringIO()
        wrapper = _SafeFileWrapper(buf)
        wrapper.write("hello world")
        assert buf.getvalue() == "hello world"

    def test_unicode_write_passes_through_on_utf8(self):
        buf = io.StringIO()
        wrapper = _SafeFileWrapper(buf)
        wrapper.write("─┌┐└┘")
        assert buf.getvalue() == "─┌┐└┘"

    def test_encoding_property_defaults_to_utf8(self):
        buf = io.StringIO()
        wrapper = _SafeFileWrapper(buf)
        # StringIO.encoding is None; the wrapper falls back to 'utf-8'
        assert wrapper.encoding == "utf-8"

    def test_encoding_property_delegates_when_present(self):
        class FakeStream:
            encoding = "cp1252"

            def write(self, s: str) -> int:
                return len(s)

        wrapper = _SafeFileWrapper(FakeStream())
        assert wrapper.encoding == "cp1252"

    def test_flush_delegates(self):
        buf = io.StringIO()
        wrapper = _SafeFileWrapper(buf)
        wrapper.write("test")
        wrapper.flush()
        assert buf.getvalue() == "test"

    def test_writable_returns_true(self):
        buf = io.StringIO()
        wrapper = _SafeFileWrapper(buf)
        assert wrapper.writable() is True

    def test_readable_returns_false(self):
        buf = io.StringIO()
        wrapper = _SafeFileWrapper(buf)
        assert wrapper.readable() is False

    def test_seekable_returns_false(self):
        buf = io.StringIO()
        wrapper = _SafeFileWrapper(buf)
        assert wrapper.seekable() is False

    def test_getattr_forwards_unknown_attributes(self):
        buf = io.StringIO()
        wrapper = _SafeFileWrapper(buf)
        # StringIO has getvalue, which should be forwarded
        wrapper.write("hello")
        assert wrapper.getvalue() == "hello"

    def test_catches_unicode_encode_error_and_degrades(self):
        """Simulate pywin32 scenario: write raises UnicodeEncodeError."""

        class FakeCp1252Writer:
            encoding = "cp1252"

            def __init__(self):
                self.written: list[str] = []

            def write(self, s: str) -> int:
                # cp1252 can't encode box-drawing characters
                s.encode("cp1252")
                self.written.append(s)
                return len(s)

            def flush(self) -> None:
                pass

            @property
            def closed(self) -> bool:
                return False

            def isatty(self) -> bool:
                return False

        fake = FakeCp1252Writer()
        wrapper = _SafeFileWrapper(fake)

        # Box-drawing characters that cp1252 can't encode
        wrapper.write("─┌┐└┘│├┤┬┴┼")

        # Should have written replacement characters instead of crashing
        assert len(fake.written) > 0
        # The replaced string should not contain the original box chars
        result = "".join(fake.written)
        assert "─" not in result
        # Should contain replacement characters
        assert "?" in result


class TestGetConsole:
    """Tests for get_console() factory."""

    def test_returns_console_instance(self):
        console = get_console()
        from rich.console import Console

        assert isinstance(console, Console)

    def test_console_can_print_table_without_error(self):
        console = get_console()
        table = Table(title="Test", show_lines=True)
        table.add_column("Name")
        table.add_column("Status")
        table.add_row("test/deploy", "applied")
        # Should not raise
        console.print(table)

    def test_console_with_broken_stdout_does_not_crash(self, monkeypatch):
        """Simulate pywin32 wrapping stdout with cp1252 tee writer."""
        import sys

        class FakeCp1252Stdout:
            encoding = "utf-8"  # lies about encoding

            def __init__(self):
                self.data = io.BytesIO()

            def write(self, s: str) -> int:
                encoded = s.encode("cp1252")  # will fail on box chars
                self.data.write(encoded)
                return len(s)

            def flush(self) -> None:
                pass

            def fileno(self) -> int:
                raise io.UnsupportedOperation("fileno")

            def isatty(self) -> bool:
                return False

            @property
            def closed(self) -> bool:
                return False

        fake_stdout = FakeCp1252Stdout()
        monkeypatch.setattr(sys, "stdout", fake_stdout)

        console = get_console()
        table = Table(title="Deployments", show_lines=True)
        table.add_column("Name")
        table.add_column("Status")
        table.add_row("my_flow/my_deploy", "applied")

        # This would crash with bare Console() but should succeed with get_console()
        console.print(table)
