"""Tests for TerradevWorker and TerradevWorkerConfiguration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contrib.workers.terradev.worker import TerradevWorker, TerradevWorkerResult
from contrib.workers.terradev.worker_config import TerradevWorkerConfiguration


def make_cfg(**kwargs) -> TerradevWorkerConfiguration:
    defaults = {
        "gpu_type": "A100",
        "provider": "runpod",
        "credentials": {"runpod": {"api_key": "test-key"}},
    }
    defaults.update(kwargs)
    return TerradevWorkerConfiguration(**defaults)


def make_flow_run(fid: str = "flow-run-123") -> MagicMock:
    fr = MagicMock()
    fr.id = fid
    return fr


def make_worker() -> TerradevWorker:
    w = TerradevWorker.__new__(TerradevWorker)
    w._logger = MagicMock()
    return w


# ── _provision ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_provision_returns_triple() -> None:
    mock_provider = AsyncMock()
    mock_provider.provision_instance.return_value = MagicMock(
        instance_id="inst-abc", address="1.2.3.4"
    )
    with patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory:
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = make_worker()
        instance_id, address, provider_name = await worker._provision(make_cfg())

    assert instance_id == "inst-abc"
    assert address == "1.2.3.4"
    assert provider_name == "runpod"
    MockFactory.return_value.create_provider.assert_called_once_with(
        "runpod", {"api_key": "test-key"}
    )
    mock_provider.aclose.assert_called_once()


# ── _wait_for_address ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wait_for_address_polls_until_ip() -> None:
    mock_provider = AsyncMock()
    mock_provider.get_instance_status.side_effect = [
        MagicMock(address=""),
        MagicMock(address="5.6.7.8"),
    ]
    with (
        patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = make_worker()
        address = await worker._wait_for_address("inst-xyz", "runpod", make_cfg())

    assert address == "5.6.7.8"


@pytest.mark.asyncio
async def test_wait_for_address_raises_on_timeout() -> None:
    mock_provider = AsyncMock()
    mock_provider.get_instance_status.return_value = MagicMock(address="")
    with (
        patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = make_worker()
        with pytest.raises(RuntimeError, match="did not receive an IP"):
            await worker._wait_for_address("inst-timeout", "runpod", make_cfg())


# ── _terminate ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_terminate_uses_correct_provider_and_credentials() -> None:
    mock_provider = AsyncMock()
    cfg = make_cfg(
        provider=None,
        credentials={
            "runpod": {"api_key": "rp-key"},
            "vastai": {"api_key": "va-key"},
        },
    )
    with patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory:
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = make_worker()
        await worker._terminate("inst-abc", "vastai", cfg)

    MockFactory.return_value.create_provider.assert_called_once_with(
        "vastai", {"api_key": "va-key"}
    )
    mock_provider.terminate_instance.assert_awaited_once_with("inst-abc")


@pytest.mark.asyncio
async def test_terminate_reraises_on_failure() -> None:
    mock_provider = AsyncMock()
    mock_provider.terminate_instance.side_effect = RuntimeError("provider error")
    with patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory:
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = make_worker()
        with pytest.raises(RuntimeError, match="provider error"):
            await worker._terminate("inst-abc", "runpod", make_cfg())


# ── kill_infrastructure ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kill_infrastructure_parses_identifier() -> None:
    worker = make_worker()
    worker._work_pool = None
    with patch.object(worker, "_terminate", new_callable=AsyncMock) as mock_term:
        await worker.kill_infrastructure("runpod:inst-xyz")

    mock_term.assert_awaited_once()
    args = mock_term.call_args[0]
    assert args[0] == "inst-xyz"
    assert args[1] == "runpod"


@pytest.mark.asyncio
async def test_kill_infrastructure_bad_id_logs_warning() -> None:
    worker = make_worker()
    await worker.kill_infrastructure("bad-identifier-no-colon")
    worker._logger.warning.assert_called_once()


# ── configuration ─────────────────────────────────────────────────────────────


def test_config_defaults() -> None:
    cfg = TerradevWorkerConfiguration(credentials={"runpod": {"api_key": "k"}})
    assert cfg.gpu_type == "A100"
    assert cfg.spot is False
    assert cfg.ssh_user == "ubuntu"
    assert cfg.provider is None


def test_config_credentials_default_empty() -> None:
    cfg = TerradevWorkerConfiguration()
    assert cfg.credentials == {}
