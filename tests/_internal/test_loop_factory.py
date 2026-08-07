import asyncio

import pytest

from prefect._internal.loop_factory import (
    get_loop_factory,
    run_with_selected_loop,
    uvicorn_loop,
)


async def _loop_module() -> str:
    return type(asyncio.get_running_loop()).__module__


def test_default_is_stdlib_asyncio(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PREFECT_EVENT_LOOP", raising=False)
    assert get_loop_factory() is None
    assert uvicorn_loop() == "asyncio"
    assert run_with_selected_loop(_loop_module()).startswith("asyncio.")


def test_explicit_asyncio(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PREFECT_EVENT_LOOP", "asyncio")
    assert get_loop_factory() is None
    assert uvicorn_loop() == "asyncio"


def test_unknown_loop_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PREFECT_EVENT_LOOP", "trio")
    with pytest.raises(RuntimeError, match="unknown PREFECT_EVENT_LOOP"):
        get_loop_factory()


def test_missing_loop_raises_not_falls_back(monkeypatch: pytest.MonkeyPatch):
    try:
        import zuvloop  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("only meaningful when zuvloop is absent")
    monkeypatch.setenv("PREFECT_EVENT_LOOP", "zuvloop")
    with pytest.raises(RuntimeError, match="zuvloop is not installed"):
        get_loop_factory()


def test_zuvloop_selected(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("zuvloop")
    monkeypatch.setenv("PREFECT_EVENT_LOOP", "zuvloop")
    assert get_loop_factory() is not None
    assert uvicorn_loop() == "zuvloop:new_event_loop"
    assert run_with_selected_loop(_loop_module()) == "zuvloop._loop"


def test_uvloop_selected(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("uvloop")
    monkeypatch.setenv("PREFECT_EVENT_LOOP", "uvloop")
    assert get_loop_factory() is not None
    assert run_with_selected_loop(_loop_module()).startswith("uvloop")
