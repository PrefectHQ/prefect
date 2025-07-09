import os
from pathlib import Path

import pytest
import toml
from prefect_aws.settings import AwsSettings


def test_set_values_via_environment_variables(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_AWS_ECS_WORKER_API_SECRET_ARN",
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key",
    )

    settings = AwsSettings()

    assert (
        settings.ecs_worker.api_secret_arn
        == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key"
    )


def test_set_values_via_dot_env_file(tmp_path: Path):
    dot_env_path = tmp_path / ".env"
    with open(dot_env_path, "w") as f:
        f.write(
            "PREFECT_INTEGRATIONS_AWS_ECS_WORKER_API_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key\n"
        )

    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        settings = AwsSettings()
    finally:
        os.chdir(original_dir)

    assert (
        settings.ecs_worker.api_secret_arn
        == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key"
    )


def test_set_values_via_prefect_toml_file(tmp_path: Path):
    toml_path = tmp_path / "prefect.toml"
    toml_data = {
        "integrations": {
            "aws": {
                "ecs_worker": {
                    "api_secret_arn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key",
                },
            },
        },
    }
    toml_path.write_text(toml.dumps(toml_data))

    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        settings = AwsSettings()
    finally:
        os.chdir(original_dir)

    assert (
        settings.ecs_worker.api_secret_arn
        == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key"
    )


def test_set_values_via_pyproject_toml_file(tmp_path: Path):
    pyproject_toml_path = tmp_path / "pyproject.toml"
    pyproject_toml_data = {
        "tool": {
            "prefect": {
                "integrations": {
                    "aws": {
                        "ecs_worker": {
                            "api_secret_arn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key",
                        },
                    },
                },
            },
        },
    }
    pyproject_toml_path.write_text(toml.dumps(pyproject_toml_data))

    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        settings = AwsSettings()
    finally:
        os.chdir(original_dir)

    assert (
        settings.ecs_worker.api_secret_arn
        == "arn:aws:secretsmanager:us-east-1:123456789012:secret:prefect-worker-api-key"
    )
