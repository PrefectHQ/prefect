"""
CI environment detection for SDK telemetry.

Telemetry is automatically disabled in CI environments.
"""

import os

# Common CI environment variables
CI_ENV_VARS = frozenset(
    {
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "TRAVIS",
        "CIRCLECI",
        "BUILDKITE",
        "TF_BUILD",  # Azure DevOps
        "CODEBUILD_BUILD_ID",  # AWS CodeBuild
        "BITBUCKET_COMMIT",
        "TEAMCITY_VERSION",
        "DRONE",
        "SEMAPHORE",
        "APPVEYOR",
        "BUDDY",
        "CI_NAME",  # Generic CI indicator
    }
)


def is_ci_environment() -> bool:
    """
    Check if the current environment is a CI environment.

    Returns:
        True if any known CI environment variable is set
    """
    return any(os.environ.get(var) for var in CI_ENV_VARS)
