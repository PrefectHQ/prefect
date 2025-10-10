"""
Tests for the experimental plugin system.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from prefect._experimental.plugins import config, run_startup_hooks
from prefect._experimental.plugins.apply import redact, summarize_env
from prefect._experimental.plugins.diagnostics import SetupSummary
from prefect._experimental.plugins.manager import (
    build_manager,
    call_async_hook,
    load_entry_point_plugins,
    register_hook,
)
from prefect._experimental.plugins.spec import HookContext, HookSpec, SetupResult
from prefect.settings import (
    PREFECT_EXPERIMENTS_PLUGINS_ALLOW,
    PREFECT_EXPERIMENTS_PLUGINS_DENY,
    PREFECT_EXPERIMENTS_PLUGINS_ENABLED,
    PREFECT_EXPERIMENTS_PLUGINS_SAFE_MODE,
    PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS,
    PREFECT_EXPERIMENTS_PLUGINS_STRICT,
    temporary_settings,
)


@pytest.fixture
def mock_ctx():
    """Create a mock HookContext for testing."""
    return HookContext(
        prefect_version="3.0.0",
        api_url="http://localhost:4200/api",
        logger_factory=lambda name: logging.getLogger(name),
    )


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Clean environment variables for plugin tests."""
    monkeypatch.delenv("PREFECT_EXPERIMENTS_PLUGINS_ENABLED", raising=False)
    monkeypatch.delenv("PREFECT_EXPERIMENTS_PLUGINS_ALLOW", raising=False)
    monkeypatch.delenv("PREFECT_EXPERIMENTS_PLUGINS_DENY", raising=False)
    monkeypatch.delenv(
        "PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS", raising=False
    )
    monkeypatch.delenv("PREFECT_EXPERIMENTS_PLUGINS_STRICT", raising=False)
    monkeypatch.delenv("PREFECT_EXPERIMENTS_PLUGINS_SAFE_MODE", raising=False)


class TestPluginConfig:
    """Tests for plugin configuration."""

    @pytest.mark.usefixtures("clean_env")
    def test_feature_flag_off(self):
        """Test that plugins are disabled by default."""
        from prefect._experimental.plugins import config

        assert config.enabled() is False

    @pytest.mark.usefixtures("clean_env")
    def test_feature_flag_on(self):
        """Test that plugins can be enabled."""

        with temporary_settings(updates={PREFECT_EXPERIMENTS_PLUGINS_ENABLED: True}):
            assert config.enabled() is True

    @pytest.mark.usefixtures("clean_env")
    def test_timeout_default(self):
        """Test default timeout value."""
        assert config.timeout_seconds() == 20.0

    @pytest.mark.usefixtures("clean_env")
    def test_timeout_custom(self):
        """Test custom timeout value."""
        with temporary_settings(
            updates={PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS: 10.0}
        ):
            assert config.timeout_seconds() == 10.0

    @pytest.mark.usefixtures("clean_env")
    def test_allow_deny_lists(self):
        """Test allow and deny list parsing."""

        with temporary_settings(
            updates={
                PREFECT_EXPERIMENTS_PLUGINS_ALLOW: "plugin1,plugin2",
                PREFECT_EXPERIMENTS_PLUGINS_DENY: "plugin3",
            }
        ):
            allow, deny = config.lists()
            assert allow == {"plugin1", "plugin2"}
            assert deny == {"plugin3"}

    @pytest.mark.usefixtures("clean_env")
    def test_strict_mode(self):
        """Test strict mode flag."""
        with temporary_settings(updates={PREFECT_EXPERIMENTS_PLUGINS_STRICT: True}):
            assert config.strict() is True

    @pytest.mark.usefixtures("clean_env")
    def test_safe_mode(self):
        """Test safe mode flag."""
        with temporary_settings(updates={PREFECT_EXPERIMENTS_PLUGINS_SAFE_MODE: True}):
            assert config.safe_mode() is True


class TestRedaction:
    """Tests for secret redaction."""

    def test_redact_secret_key(self):
        """Test that AWS_SECRET_ACCESS_KEY is redacted."""
        result = redact("AWS_SECRET_ACCESS_KEY", "supersecret123")
        assert result == "••••••"

    def test_redact_token(self):
        """Test that TOKEN is redacted."""
        result = redact("GITHUB_TOKEN", "ghp_abcdefghijklmnop")
        assert result == "••••••"

    def test_redact_password(self):
        """Test that PASSWORD is redacted."""
        result = redact("DATABASE_PASSWORD", "mypassword")
        assert result == "••••••"

    def test_no_redaction_normal_key(self):
        """Test that normal keys are not redacted (but truncated if long)."""
        result = redact("AWS_REGION", "us-east-1")
        assert result == "us-east-1"

    def test_truncate_long_value(self):
        """Test that long values are truncated."""
        long_value = "x" * 100
        result = redact("SOME_VALUE", long_value)
        assert len(result) < len(long_value)
        assert result.endswith("…")

    def test_summarize_env(self):
        """Test that environment summary redacts secrets."""
        env = {
            "AWS_SECRET_ACCESS_KEY": "supersecret",
            "AWS_REGION": "us-east-1",
        }
        summary = summarize_env(env)
        assert summary["AWS_SECRET_ACCESS_KEY"] == "••••••"
        assert summary["AWS_REGION"] == "us-east-1"


class TestPluginManager:
    """Tests for plugin discovery and management."""

    def test_build_manager(self):
        """Test that we can build a plugin manager."""
        pm = build_manager(HookSpec)
        assert pm is not None
        assert pm.project_name == "prefect-experimental"

    @pytest.mark.asyncio
    async def test_async_hook_call_sync(self, mock_ctx: HookContext):
        """Test calling a sync hook implementation."""

        class TestPlugin:
            @register_hook
            def setup_environment(self, *, ctx: HookContext):
                return SetupResult(env={"TEST": "value"})

        pm = build_manager(HookSpec)
        pm.register(TestPlugin(), name="test-plugin")

        results = await call_async_hook(pm, "setup_environment", ctx=mock_ctx)
        assert len(results) == 1
        name, result, error = results[0]
        assert name == "test-plugin"
        assert error is None
        assert result.env["TEST"] == "value"

    @pytest.mark.asyncio
    async def test_async_hook_call_async(self, mock_ctx: HookContext):
        """Test calling an async hook implementation."""

        class TestPlugin:
            @register_hook
            async def setup_environment(self, *, ctx: HookContext):
                await asyncio.sleep(0.001)
                return SetupResult(env={"TEST": "async_value"})

        pm = build_manager(HookSpec)
        pm.register(TestPlugin(), name="test-plugin")

        results = await call_async_hook(pm, "setup_environment", ctx=mock_ctx)
        assert len(results) == 1
        name, result, error = results[0]
        assert name == "test-plugin"
        assert error is None
        assert result.env["TEST"] == "async_value"

    @pytest.mark.asyncio
    async def test_hook_error_handling(self, mock_ctx: HookContext):
        """Test that hook errors are captured per plugin."""

        class GoodPlugin:
            @register_hook
            def setup_environment(self, *, ctx: HookContext):
                return SetupResult(env={"GOOD": "value"})

        class BadPlugin:
            @register_hook
            def setup_environment(self, *, ctx: HookContext):
                raise ValueError("Plugin failed!")

        pm = build_manager(HookSpec)
        pm.register(GoodPlugin(), name="good-plugin")
        pm.register(BadPlugin(), name="bad-plugin")

        results = await call_async_hook(pm, "setup_environment", ctx=mock_ctx)
        assert len(results) == 2

        # Check good plugin
        good_result = next(r for r in results if r[0] == "good-plugin")
        assert good_result[1].env["GOOD"] == "value"
        assert good_result[2] is None

        # Check bad plugin
        bad_result = next(r for r in results if r[0] == "bad-plugin")
        assert bad_result[1] is None
        assert isinstance(bad_result[2], ValueError)

    def test_load_entry_point_plugins_with_allow_list(self):
        """Test that allow list filters plugins."""
        pm = build_manager(HookSpec)
        logger = logging.getLogger("test")

        # Mock entry points
        mock_plugin1 = Mock()
        mock_plugin1.PREFECT_PLUGIN_API_REQUIRES = ">=0.1,<1"
        mock_ep1 = Mock()
        mock_ep1.name = "plugin1"
        mock_ep1.load.return_value = mock_plugin1

        mock_plugin2 = Mock()
        mock_plugin2.PREFECT_PLUGIN_API_REQUIRES = ">=0.1,<1"
        mock_ep2 = Mock()
        mock_ep2.name = "plugin2"
        mock_ep2.load.return_value = mock_plugin2

        with patch(
            "importlib.metadata.entry_points", return_value=[mock_ep1, mock_ep2]
        ):
            load_entry_point_plugins(pm, allow={"plugin1"}, deny=None, logger=logger)

        # Only plugin1 should be registered
        assert len(pm.get_plugins()) == 1

    def test_load_entry_point_plugins_with_deny_list(self):
        """Test that deny list filters plugins."""
        pm = build_manager(HookSpec)
        logger = logging.getLogger("test")

        # Mock entry points
        mock_plugin1 = Mock()
        mock_plugin1.PREFECT_PLUGIN_API_REQUIRES = ">=0.1,<1"
        mock_ep1 = Mock()
        mock_ep1.name = "plugin1"
        mock_ep1.load.return_value = mock_plugin1

        mock_plugin2 = Mock()
        mock_plugin2.PREFECT_PLUGIN_API_REQUIRES = ">=0.1,<1"
        mock_ep2 = Mock()
        mock_ep2.name = "plugin2"
        mock_ep2.load.return_value = mock_plugin2

        with patch(
            "importlib.metadata.entry_points", return_value=[mock_ep1, mock_ep2]
        ):
            load_entry_point_plugins(pm, allow=None, deny={"plugin2"}, logger=logger)

        # Only plugin1 should be registered
        assert len(pm.get_plugins()) == 1

    def test_load_entry_point_plugins_version_validation_compatible(self):
        """Test that plugins with compatible API versions are loaded."""
        pm = build_manager(HookSpec)
        logger = logging.getLogger("test")

        # Mock a plugin with compatible version requirement
        mock_plugin = Mock()
        mock_plugin.PREFECT_PLUGIN_API_REQUIRES = ">=0.1,<1"

        mock_ep = Mock()
        mock_ep.name = "compatible-plugin"
        mock_ep.load.return_value = mock_plugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            load_entry_point_plugins(pm, allow=None, deny=None, logger=logger)

        # Plugin should be registered
        assert len(pm.get_plugins()) == 1

    def test_load_entry_point_plugins_version_validation_incompatible(self):
        """Test that plugins with incompatible API versions are skipped."""
        pm = build_manager(HookSpec)
        logger = logging.getLogger("test")

        # Mock a plugin with incompatible version requirement
        mock_plugin = Mock()
        mock_plugin.PREFECT_PLUGIN_API_REQUIRES = ">=1.0"

        mock_ep = Mock()
        mock_ep.name = "incompatible-plugin"
        mock_ep.load.return_value = mock_plugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            load_entry_point_plugins(pm, allow=None, deny=None, logger=logger)

        # Plugin should NOT be registered due to version mismatch
        assert len(pm.get_plugins()) == 0

    def test_load_entry_point_plugins_invalid_version_specifier(self):
        """Test that plugins with invalid version specifiers are loaded with warning."""
        pm = build_manager(HookSpec)
        logger = logging.getLogger("test")

        # Mock a plugin with invalid version specifier
        mock_plugin = Mock()
        mock_plugin.PREFECT_PLUGIN_API_REQUIRES = "this-is-not-valid"

        mock_ep = Mock()
        mock_ep.name = "invalid-spec-plugin"
        mock_ep.load.return_value = mock_plugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            load_entry_point_plugins(pm, allow=None, deny=None, logger=logger)

        # Plugin should still be registered (we log but don't block)
        assert len(pm.get_plugins()) == 1


class TestStartupHooks:
    """Tests for the full startup hook system."""

    @pytest.mark.usefixtures("clean_env")
    async def test_disabled_plugins_no_execution(self, mock_ctx: HookContext):
        """Test that plugins don't run when disabled."""
        summaries = await run_startup_hooks(mock_ctx)
        assert summaries == []

    @pytest.mark.usefixtures("clean_env")
    async def test_safe_mode_no_execution(self, mock_ctx: HookContext):
        """Test that safe mode loads plugins but doesn't execute hooks."""

        with temporary_settings(
            updates={
                PREFECT_EXPERIMENTS_PLUGINS_ENABLED: True,
                PREFECT_EXPERIMENTS_PLUGINS_SAFE_MODE: True,
            }
        ):
            summaries = await run_startup_hooks(mock_ctx)
            # Should return empty list in safe mode
            assert summaries == []

    @pytest.mark.asyncio
    async def test_timeout_handling(self, clean_env, mock_ctx):
        """Test that slow plugins time out gracefully."""
        from prefect.settings import Settings, _get_settings_fields

        fields = _get_settings_fields(Settings)
        timeout_setting = fields["PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS"]

        class SlowPlugin:
            async def setup_environment(self, *, ctx: HookContext):
                await asyncio.sleep(1.0)
                return SetupResult(env={"SLOW": "value"})

        pm = build_manager(HookSpec)
        pm.register(SlowPlugin(), name="slow-plugin")

        with temporary_settings(
            updates={PREFECT_EXPERIMENTS_PLUGINS_ENABLED: True, timeout_setting: 0.1}
        ):
            with patch("prefect._experimental.plugins.build_manager", return_value=pm):
                with patch(
                    "prefect._experimental.plugins.manager.load_entry_point_plugins"
                ):
                    summaries = await run_startup_hooks(mock_ctx)
                    # Should complete without crashing
                    assert isinstance(summaries, list)

    @pytest.mark.asyncio
    async def test_strict_mode_required_failure(self, clean_env, mock_ctx):
        """Test that strict mode exits on required plugin failure."""
        from prefect.settings import Settings, _get_settings_fields

        fields = _get_settings_fields(Settings)
        strict_setting = fields["PREFECT_EXPERIMENTS_PLUGINS_STRICT"]

        class RequiredPlugin:
            @register_hook
            def setup_environment(self, *, ctx: HookContext):
                raise ValueError("Required plugin failed!")

        pm = build_manager(HookSpec)
        pm.register(RequiredPlugin(), name="required-plugin")

        with temporary_settings(
            updates={PREFECT_EXPERIMENTS_PLUGINS_ENABLED: True, strict_setting: True}
        ):
            with patch("prefect._experimental.plugins.build_manager", return_value=pm):
                with patch(
                    "prefect._experimental.plugins.manager.load_entry_point_plugins"
                ):
                    with pytest.raises(SystemExit):
                        await run_startup_hooks(mock_ctx)

    @pytest.mark.asyncio
    async def test_successful_plugin_execution(self, clean_env, mock_ctx):
        """Test that successful plugins apply environment variables."""

        class TestPlugin:
            @register_hook
            def setup_environment(self, *, ctx: HookContext):
                return SetupResult(
                    env={"TEST_VAR": "test_value"},
                    note="Test plugin ran",
                    expires_at=datetime.now(timezone.utc),
                )

        pm = build_manager(HookSpec)
        pm.register(TestPlugin(), name="test-plugin")

        with temporary_settings(updates={PREFECT_EXPERIMENTS_PLUGINS_ENABLED: True}):
            with patch("prefect._experimental.plugins.build_manager", return_value=pm):
                with patch(
                    "prefect._experimental.plugins.manager.load_entry_point_plugins"
                ):
                    summaries = await run_startup_hooks(mock_ctx)

                    assert len(summaries) == 1
                    assert summaries[0].plugin == "test-plugin"
                    assert summaries[0].error is None
                    assert summaries[0].note == "Test plugin ran"
                    assert "TEST_VAR" in summaries[0].env_preview

                    # Check that env var was actually set
                    assert os.environ.get("TEST_VAR") == "test_value"

    @pytest.mark.asyncio
    async def test_plugin_returning_none(self, clean_env, mock_ctx):
        """Test that plugins can return None to indicate no changes."""

        class NoOpPlugin:
            @register_hook
            def setup_environment(self, *, ctx: HookContext):
                return None

        pm = build_manager(HookSpec)
        pm.register(NoOpPlugin(), name="noop-plugin")

        with temporary_settings(updates={PREFECT_EXPERIMENTS_PLUGINS_ENABLED: True}):
            with patch("prefect._experimental.plugins.build_manager", return_value=pm):
                with patch(
                    "prefect._experimental.plugins.manager.load_entry_point_plugins"
                ):
                    summaries = await run_startup_hooks(mock_ctx)

                    assert len(summaries) == 1
                    assert summaries[0].plugin == "noop-plugin"
                    assert summaries[0].error is None
                    assert summaries[0].env_preview == {}


class TestSetupSummary:
    """Tests for SetupSummary data structure."""

    def test_setup_summary_creation(self):
        """Test creating a SetupSummary."""
        summary = SetupSummary(
            plugin="test-plugin",
            env_preview={"KEY": "value"},
            note="Test note",
            expires_at=None,
            error=None,
        )
        assert summary.plugin == "test-plugin"
        assert summary.env_preview == {"KEY": "value"}
        assert summary.note == "Test note"
        assert summary.error is None
