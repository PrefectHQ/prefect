"""
Backward-compatibility tests for the plugin system GA migration.

The plugin system was promoted from `prefect._experimental.plugins` to
`prefect.plugins` and from `PREFECT_EXPERIMENTS_PLUGINS_*` env vars to
`PREFECT_PLUGINS_*`. The old paths must continue to work but emit
`DeprecationWarning`s pointing at the new locations.
"""

from __future__ import annotations

import importlib
import warnings

import pytest

import prefect.plugins as new_module

PUBLIC_NAMES = (
    "run_startup_hooks",
    "HookContext",
    "SetupResult",
    "HookSpec",
    "SetupSummary",
    "PREFECT_PLUGIN_API_VERSION",
    "register_hook",
)


class TestImportPathDeprecation:
    """Old `prefect._experimental.plugins.*` import paths emit DeprecationWarning."""

    @pytest.mark.parametrize("name", PUBLIC_NAMES)
    def test_top_level_attribute_warns_and_redirects(self, name: str):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            from prefect import _experimental as experimental_pkg

            experimental_plugins = importlib.import_module(
                f"{experimental_pkg.__name__}.plugins"
            )
            value = getattr(experimental_plugins, name)

        assert any(
            issubclass(w.category, DeprecationWarning)
            and "prefect.plugins" in str(w.message)
            and name in str(w.message)
            for w in caught
        ), (
            f"expected DeprecationWarning for {name}, got: {[str(w.message) for w in caught]}"
        )
        assert value is getattr(new_module, name)

    @pytest.mark.parametrize(
        "submodule, names",
        [
            (
                "spec",
                (
                    "HookContext",
                    "SetupResult",
                    "HookSpec",
                    "PREFECT_PLUGIN_API_VERSION",
                ),
            ),
            ("manager", ("register_hook",)),
            ("diagnostics", ("SetupSummary",)),
        ],
    )
    def test_submodule_redirects(self, submodule: str, names: tuple[str, ...]):
        mod = importlib.import_module(f"prefect._experimental.plugins.{submodule}")
        for name in names:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                value = getattr(mod, name)
            assert any(issubclass(w.category, DeprecationWarning) for w in caught), (
                f"no DeprecationWarning for {submodule}.{name}"
            )
            assert value is getattr(new_module, name)

    def test_internal_symbol_on_old_path_raises(self):
        """Names that were never public must not be redirected — clean AttributeError."""
        from prefect._experimental.plugins import manager as old_manager

        with pytest.raises(AttributeError):
            old_manager.build_manager  # noqa: B018


class TestEnvVarDeprecation:
    """Legacy PREFECT_EXPERIMENTS_PLUGINS_* env vars resolve and emit warnings."""

    def test_legacy_env_var_resolves_and_warns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PREFECT_EXPERIMENTS_PLUGINS_ENABLED", "1")
        # Force a re-import so the module-level warning check runs again
        # (Python's warning dedup is per-source-location, so a fresh
        # interpreter would also emit it).
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            import prefect.settings.models.plugins as plugins_module

            importlib.reload(plugins_module)

            # Re-instantiate settings to pick up the env var via AliasChoices
            from prefect.settings import Settings

            settings = Settings()

            assert settings.plugins.enabled is True

        assert any(
            issubclass(w.category, DeprecationWarning)
            and "PREFECT_EXPERIMENTS_PLUGINS_" in str(w.message)
            for w in caught
        ), (
            f"expected legacy env-var DeprecationWarning, got: {[str(w.message) for w in caught]}"
        )


class TestLegacyTomlSection:
    """`[experiments.plugins]` in `prefect.toml` keeps populating settings.plugins."""

    def test_legacy_prefect_toml_section_is_read(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Isolate the test: clean env, fresh CWD with our prefect.toml.
        for var in (
            "PREFECT_PLUGINS_ENABLED",
            "PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS",
            "PREFECT_EXPERIMENTS_PLUGINS_ENABLED",
            "PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(var, raising=False)

        toml = tmp_path / "prefect.toml"
        toml.write_text(
            "[experiments.plugins]\nenabled = true\nsetup_timeout_seconds = 7.5\n"
        )
        monkeypatch.chdir(tmp_path)

        from prefect.settings import Settings

        plugins = Settings().plugins
        assert plugins.enabled is True
        assert plugins.setup_timeout_seconds == 7.5

    def test_new_prefect_toml_section_wins_over_legacy(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for var in (
            "PREFECT_PLUGINS_ENABLED",
            "PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS",
            "PREFECT_EXPERIMENTS_PLUGINS_ENABLED",
            "PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(var, raising=False)

        toml = tmp_path / "prefect.toml"
        toml.write_text(
            "[plugins]\n"
            "enabled = true\n"
            "setup_timeout_seconds = 12.0\n"
            "\n"
            "[experiments.plugins]\n"
            "enabled = false\n"
            "setup_timeout_seconds = 5.0\n"
        )
        monkeypatch.chdir(tmp_path)

        from prefect.settings import Settings

        plugins = Settings().plugins
        assert plugins.enabled is True
        assert plugins.setup_timeout_seconds == 12.0


class TestLegacyConstructorPayload:
    """Legacy `Settings(experiments={"plugins": {...}})` calls hoist into settings.plugins."""

    def test_legacy_nested_payload_hoisted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for var in (
            "PREFECT_PLUGINS_ENABLED",
            "PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS",
            "PREFECT_EXPERIMENTS_PLUGINS_ENABLED",
            "PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(var, raising=False)

        from prefect.settings import Settings

        settings = Settings(
            experiments={"plugins": {"enabled": True, "setup_timeout_seconds": 7.0}}
        )
        assert settings.plugins.enabled is True
        assert settings.plugins.setup_timeout_seconds == 7.0

    def test_legacy_typed_experiments_payload_hoisted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`Settings(experiments=ExperimentsSettings(plugins=...))` works too."""
        for var in (
            "PREFECT_PLUGINS_ENABLED",
            "PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS",
            "PREFECT_EXPERIMENTS_PLUGINS_ENABLED",
            "PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(var, raising=False)

        from prefect.settings import Settings
        from prefect.settings.models.experiments import ExperimentsSettings

        settings = Settings(
            experiments=ExperimentsSettings(
                plugins={"enabled": True, "setup_timeout_seconds": 9.0}
            )
        )
        assert settings.plugins.enabled is True
        assert settings.plugins.setup_timeout_seconds == 9.0

    def test_canonical_wins_over_legacy_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for var in (
            "PREFECT_PLUGINS_ENABLED",
            "PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS",
            "PREFECT_EXPERIMENTS_PLUGINS_ENABLED",
            "PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(var, raising=False)

        from prefect.settings import Settings

        settings = Settings(
            plugins={"enabled": True, "setup_timeout_seconds": 12.0},
            experiments={
                "plugins": {"enabled": False, "setup_timeout_seconds": 5.0},
            },
        )
        assert settings.plugins.enabled is True
        assert settings.plugins.setup_timeout_seconds == 12.0


class TestExperimentsAttributeDeprecation:
    """`settings.experiments.plugins` continues to resolve and emit a warning."""

    def test_experiments_plugins_proxy(self) -> None:
        from prefect.settings import get_current_settings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            value = get_current_settings().experiments.plugins.enabled

        assert isinstance(value, bool)
        assert any(
            issubclass(w.category, DeprecationWarning)
            and "settings.experiments.plugins" in str(w.message)
            for w in caught
        ), (
            f"expected experiments.plugins DeprecationWarning, got: {[str(w.message) for w in caught]}"
        )

    def test_standalone_experiments_plugins_payload_visible(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`ExperimentsSettings(plugins={...}).plugins` returns the override."""
        for var in (
            "PREFECT_PLUGINS_ENABLED",
            "PREFECT_PLUGINS_SETUP_TIMEOUT_SECONDS",
            "PREFECT_EXPERIMENTS_PLUGINS_ENABLED",
            "PREFECT_EXPERIMENTS_PLUGINS_SETUP_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(var, raising=False)

        from prefect.settings.models.experiments import ExperimentsSettings

        experiments = ExperimentsSettings(
            plugins={"enabled": True, "setup_timeout_seconds": 11.0}
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            plugins = experiments.plugins
        assert plugins.enabled is True
        assert plugins.setup_timeout_seconds == 11.0
