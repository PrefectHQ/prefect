"""The version assertion every Prefect integration package carries."""

from __future__ import annotations

from packaging.version import Version


def test_version() -> None:
    from prefect_sandbox import __version__

    assert isinstance(__version__, str)
    assert Version(__version__)
    assert __version__.startswith("0.")
