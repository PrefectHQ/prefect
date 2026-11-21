from collections.abc import AsyncIterator

import pytest
from prefect_shell.commands import (
    _decode_output,
    _is_windows_powershell,
    _receive_lines,
)


async def chunks(*items: bytes) -> AsyncIterator[bytes]:
    for item in items:
        yield item


@pytest.mark.parametrize(
    "shell,expected",
    [
        ("powershell", True),
        ("PowerShell.EXE", True),
        (r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", True),
        ("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", True),
        ("pwsh", False),
        ("pwsh.exe", False),
        ("bash", False),
        (r"C:\powershell\bash.exe", False),
    ],
)
def test_is_windows_powershell(shell: str, expected: bool):
    assert _is_windows_powershell(shell) is expected


@pytest.mark.parametrize("fallback", ["cp437", "cp932"])
def test_decode_output_reads_utf8_whatever_the_fallback(fallback: str):
    text = "café あ\r\n"
    assert _decode_output(text.encode(), fallback) == text


@pytest.mark.parametrize(
    "fallback,text",
    [("cp437", "café\r\n"), ("cp1252", "café\r\n"), ("cp932", "あいう\r\n")],
)
def test_decode_output_falls_back_for_invalid_utf8(fallback: str, text: str):
    assert _decode_output(text.encode(fallback), fallback) == text


def test_decode_output_decides_line_by_line():
    data = "café\r\n".encode() + "café\r\n".encode("cp437") + b"plain\r\n"
    assert _decode_output(data, "cp437") == "café\r\ncafé\r\nplain\r\n"


@pytest.mark.parametrize("encoding", ["utf-8", "cp932"])
async def test_receive_lines_character_split_across_chunks(encoding: str):
    text = "あいう\r\nえお\r\n"
    data = text.encode(encoding)
    for split in range(1, len(data)):
        source = chunks(data[:split], data[split:])
        received = [part async for part in _receive_lines(source, "cp932")]
        assert "".join(received) == text


async def test_receive_lines_yields_whole_lines():
    source = chunks(b"one\ntw", b"o\nthree\nfo", b"ur")
    received = [text async for text in _receive_lines(source, "cp437")]
    assert received == ["one\n", "two\nthree\n", "four"]
