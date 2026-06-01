"""Tests for helper functions in prefect.cli.deploy._config."""

import pytest

from prefect.cli.deploy._config import _filter_matching_deploy_config


def test_filter_matching_deploy_config_multiple_slashes_no_valueerror():
    """Name with multiple slashes must not raise ValueError on unpack."""
    deploy_configs = [{"name": "deployment", "entrypoint": "path.py:flow"}]
    result = _filter_matching_deploy_config("flow/extra/deployment", deploy_configs)
    assert isinstance(result, list)
