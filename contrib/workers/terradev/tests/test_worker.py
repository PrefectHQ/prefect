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


def make_flow_run(id="flow-run-123"):
    fr = MagicMock()
    fr.id = id
    return fr


# ── _provision ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provision_returns_instance_id_and_address():
    mock_provider = AsyncMock()
    mock_provider.provision_instance.return_value = MagicMock(
        instance_id="inst-abc", address="1.2.3.4"
    )

    with patch(
        "contrib.workers.terradev.worker.ProviderFactory"
    ) as MockFactory:
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = TerradevWorker.__new__(TerradevWorker)
        instance_id, address = await worker._provision(make_cfg())

    assert instance_id == "inst-abc"
    assert address == "1.2.3.4"
    mock_provider.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_provision_polls_for_ip_when_missing():
    mock_provider = AsyncMock()
    mock_provider.provision_instance.return_value = MagicMock(
        instance_id="inst-xyz", address=""
    )
    # First poll returns nothing; second returns the IP.
    mock_provider.get_instance_status.side_effect = [
        MagicMock(address=""),
        MagicMock(address="5.6.7.8"),
    ]

    with patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory,          patch("asyncio.sleep", new_callable=AsyncMock):
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = TerradevWorker.__new__(TerradevWorker)
        instance_id, address = await worker._provision(make_cfg())

    assert address == "5.6.7.8"


@pytest.mark.asyncio
async def test_provision_raises_when_no_ip_after_timeout():
    mock_provider = AsyncMock()
    mock_provider.provision_instance.return_value = MagicMock(
        instance_id="inst-timeout", address=""
    )
    mock_provider.get_instance_status.return_value = MagicMock(address="")

    with patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory,          patch("asyncio.sleep", new_callable=AsyncMock):
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = TerradevWorker.__new__(TerradevWorker)
        with pytest.raises(RuntimeError, match="did not receive an IP"):
            await worker._provision(make_cfg())


# ── _terminate ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_terminate_calls_provider():
    mock_provider = AsyncMock()

    with patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory:
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = TerradevWorker.__new__(TerradevWorker)
        worker._logger = MagicMock()
        await worker._terminate("inst-abc", make_cfg())

    mock_provider.terminate_instance.assert_awaited_once_with("inst-abc")
    mock_provider.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_terminate_reraises_on_failure():
    mock_provider = AsyncMock()
    mock_provider.terminate_instance.side_effect = RuntimeError("provider error")

    with patch("contrib.workers.terradev.worker.ProviderFactory") as MockFactory:
        MockFactory.return_value.create_provider.return_value = mock_provider
        worker = TerradevWorker.__new__(TerradevWorker)
        worker._logger = MagicMock()
        with pytest.raises(RuntimeError, match="provider error"):
            await worker._terminate("inst-abc", make_cfg())


# ── configuration ─────────────────────────────────────────────────────────────

def test_config_defaults():
    cfg = TerradevWorkerConfiguration(
        credentials={"runpod": {"api_key": "k"}},
    )
    assert cfg.gpu_type == "A100"
    assert cfg.spot is False
    assert cfg.ssh_user == "ubuntu"
    assert cfg.provider is None


def test_config_rejects_negative_price():
    with pytest.raises(Exception):
        TerradevWorkerConfiguration(
            credentials={},
            max_price_per_hour=-1.0,
        )
