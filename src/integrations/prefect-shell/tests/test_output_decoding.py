import codecs
from collections.abc import AsyncIterator

import pytest
from prefect_shell import commands
from prefect_shell.commands import (
    _console_encoding,
    _decode_output,
    _is_windows_powershell,
    _receive_text,
)


async def chunks(*items: bytes) -> AsyncIterator[bytes]:
    for item in items:
        yield item


@pytest.fixture
def console_encoding(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    monkeypatch.setattr(commands, "_console_encoding", lambda: request.param)
    return request.param


@pytest.mark.parametrize(
    "shell",
    [
        "powershell",
        "PowerShell",
        "powershell.exe",
        "POWERSHELL.EXE",
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
    ],
)
def test_is_windows_powershell(shell: str):
    assert _is_windows_powershell(shell)


@pytest.mark.parametrize(
    "shell",
    [
        "pwsh",
        "pwsh.exe",
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        "bash",
        "/usr/bin/bash",
        "cmd.exe",
        r"C:\powershell\bash.exe",
    ],
)
def test_is_not_windows_powershell(shell: str):
    assert not _is_windows_powershell(shell)


def test_console_encoding_is_a_known_codec():
    codecs.lookup(_console_encoding())


@pytest.mark.parametrize(
    "console_encoding", ["cp437", "cp1252", "cp932", "cp949"], indirect=True
)
def test_decode_output_reads_utf8_whatever_the_console_encoding(
    console_encoding: str,
):
    text = "café あ 가\r\n"
    assert _decode_output(text.encode()) == text


@pytest.mark.parametrize(
    "console_encoding,text",
    [
        ("cp437", "café\r\n"),
        ("cp1252", "café\r\n"),
        ("cp932", "あいう\r\n"),
        ("cp949", "가나다\r\n"),
    ],
    indirect=["console_encoding"],
)
def test_decode_output_falls_back_to_the_console_encoding(
    console_encoding: str, text: str
):
    assert _decode_output(text.encode(console_encoding)) == text


@pytest.mark.parametrize("console_encoding", ["cp437"], indirect=True)
def test_decode_output_decides_line_by_line(console_encoding: str):
    data = "café\r\n".encode() + "café\r\n".encode("cp437") + b"plain\r\n"
    assert _decode_output(data) == "café\r\ncafé\r\nplain\r\n"


@pytest.mark.parametrize("console_encoding", ["cp1252"], indirect=True)
def test_decode_output_replaces_undecodable_bytes(console_encoding: str):
    assert _decode_output(b"\x81\x8d\n") == "\ufffd\ufffd\n"


@pytest.mark.parametrize("console_encoding", ["cp437"], indirect=True)
async def test_receive_text_utf8_character_split_across_chunks(
    console_encoding: str,
):
    data = "café\r\nあ\r\n".encode()
    for split in range(1, len(data)):
        received = [
            text async for text in _receive_text(chunks(data[:split], data[split:]))
        ]
        assert "".join(received) == "café\r\nあ\r\n"


@pytest.mark.parametrize("console_encoding", ["cp932"], indirect=True)
async def test_receive_text_console_encoding_character_split_across_chunks(
    console_encoding: str,
):
    data = "あいう\r\nえお\r\n".encode("cp932")
    for split in range(1, len(data)):
        received = [
            text async for text in _receive_text(chunks(data[:split], data[split:]))
        ]
        assert "".join(received) == "あいう\r\nえお\r\n"


async def test_receive_text_yields_whole_lines():
    received = [
        text async for text in _receive_text(chunks(b"one\ntw", b"o\nthree\nfo", b"ur"))
    ]
    assert received == ["one\n", "two\nthree\n", "four"]


async def test_receive_text_empty_stream():
    assert [text async for text in _receive_text(chunks())] == []
