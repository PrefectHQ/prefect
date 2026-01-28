"""
Tests for CI environment detection.
"""

import pytest


class TestCIDetection:
    """Test CI environment detection."""

    def test_not_ci_by_default(self, monkeypatch: pytest.MonkeyPatch):
        """Should not detect CI when no CI variables are set."""
        # Clear all known CI variables
        from prefect.sdk_analytics._ci_detection import CI_ENV_VARS

        for var in CI_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        from prefect.sdk_analytics._ci_detection import is_ci_environment

        assert is_ci_environment() is False

    @pytest.mark.parametrize(
        "env_var",
        [
            "CI",
            "GITHUB_ACTIONS",
            "GITLAB_CI",
            "JENKINS_URL",
            "TRAVIS",
            "CIRCLECI",
            "BUILDKITE",
            "TF_BUILD",
            "CODEBUILD_BUILD_ID",
            "BITBUCKET_COMMIT",
            "TEAMCITY_VERSION",
            "DRONE",
            "SEMAPHORE",
            "APPVEYOR",
            "BUDDY",
            "CI_NAME",
        ],
    )
    def test_detects_ci_environments(
        self, env_var: str, monkeypatch: pytest.MonkeyPatch
    ):
        """Should detect various CI environments."""
        # Clear all CI variables first
        from prefect.sdk_analytics._ci_detection import CI_ENV_VARS

        for var in CI_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        # Set the specific CI variable
        monkeypatch.setenv(env_var, "true")

        from prefect.sdk_analytics._ci_detection import is_ci_environment

        assert is_ci_environment() is True

    def test_ci_variable_with_any_value(self, monkeypatch: pytest.MonkeyPatch):
        """CI should be detected regardless of variable value."""
        # Clear all CI variables first
        from prefect.sdk_analytics._ci_detection import CI_ENV_VARS

        for var in CI_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv("CI", "1")

        from prefect.sdk_analytics._ci_detection import is_ci_environment

        assert is_ci_environment() is True
