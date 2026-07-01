from typing import Any, Dict

import pytest
from botocore import UNSIGNED
from botocore.client import Config
from prefect_aws import __version__ as PREFECT_AWS_VERSION
from prefect_aws.client_parameters import AwsClientParameters


class TestAwsClientParameters:
    @pytest.mark.parametrize(
        "params,result",
        [
            (AwsClientParameters(), {"use_ssl": True}),
            (
                AwsClientParameters(
                    use_ssl=False, verify=False, endpoint_url="http://localhost:9000"
                ),
                {
                    "use_ssl": False,
                    "verify": False,
                    "endpoint_url": "http://localhost:9000",
                },
            ),
            (
                AwsClientParameters(endpoint_url="https://localhost:9000"),
                {"use_ssl": True, "endpoint_url": "https://localhost:9000"},
            ),
            (
                AwsClientParameters(api_version="1.0.0"),
                {"use_ssl": True, "api_version": "1.0.0"},
            ),
        ],
    )
    def test_get_params_override_expected_output(
        self, params: AwsClientParameters, result: Dict[str, Any], tmp_path
    ):
        override = params.get_params_override()
        # A default prefect-aws User-Agent Config is always injected.
        assert isinstance(override.pop("config"), Config)
        assert override == result

    @pytest.mark.parametrize(
        "params,result",
        [
            (
                AwsClientParameters(
                    config=dict(
                        region_name="eu_west_1",
                        retries={"max_attempts": 10, "mode": "standard"},
                        signature_version="unsigned",
                    )
                ),
                {
                    "config": {
                        "region_name": "eu_west_1",
                        "retries": {"max_attempts": 10, "mode": "standard"},
                        "signature_version": UNSIGNED,
                    },
                },
            ),
        ],
    )
    def test_with_custom_config(
        self, params: AwsClientParameters, result: Dict[str, Any]
    ):
        assert (
            result["config"]["region_name"]
            == params.get_params_override()["config"].region_name
        )
        assert (
            result["config"]["retries"]
            == params.get_params_override()["config"].retries
        )

    def test_with_not_verify_and_verify_cert_path(self, tmp_path):
        cert_path = tmp_path / "ca-bundle.crt"
        cert_path.touch()
        with pytest.warns(
            UserWarning, match="verify_cert_path is set but verify is False"
        ):
            params = AwsClientParameters(verify=False, verify_cert_path=cert_path)
        assert params.verify_cert_path is None
        assert not params.verify

    def test_get_params_override_with_config_with_deprecated_verify(self, tmp_path):
        cert_path = tmp_path / "ca-bundle.crt"
        cert_path.touch()
        with pytest.warns(DeprecationWarning, match="verify should be a boolean"):
            params = AwsClientParameters(verify=cert_path)
        assert params.verify
        assert not params.verify_cert_path
        override_params = params.get_params_override()
        override_params["verify"] == cert_path

    def test_get_params_override_with_config(self, tmp_path):
        cert_path = tmp_path / "ca-bundle.crt"
        cert_path.touch()
        params = AwsClientParameters(
            config=Config(
                region_name="eu_west_1",
                retries={"max_attempts": 10, "mode": "standard"},
            ),
            verify_cert_path=cert_path,
        )
        override_params = params.get_params_override()
        override_params["config"].region_name == "eu_west_1"
        override_params["config"].retries == {
            "max_attempts": 10,
            "mode": "standard",
        }

    def test_get_params_override_with_verify_cert_path(self, tmp_path):
        cert_path = tmp_path / "ca-bundle.crt"
        cert_path.touch()
        params = AwsClientParameters(verify_cert_path=cert_path)
        override_params = params.get_params_override()
        assert override_params["verify"] == cert_path

    def test_get_params_override_with_both_cert_path(self, tmp_path):
        old_cert_path = tmp_path / "old-ca-bundle.crt"
        old_cert_path.touch()

        cert_path = tmp_path / "ca-bundle.crt"
        cert_path.touch()
        with pytest.warns(
            UserWarning, match="verify_cert_path is set but verify is also set"
        ):
            params = AwsClientParameters(
                verify=old_cert_path, verify_cert_path=cert_path
            )
        override_params = params.get_params_override()
        assert override_params["verify"] == cert_path

    def test_get_params_override_with_default_verify(self):
        params = AwsClientParameters()
        override_params = params.get_params_override()
        assert "verify" not in override_params, (
            "verify should not be in params_override when not explicitly set"
        )

    def test_default_user_agent_extra_includes_prefect_aws(self):
        # Every constructed boto3 client should advertise prefect-aws so
        # operators can attribute traffic back to Prefect workloads.
        override = AwsClientParameters().get_params_override()
        assert (
            f"prefect-aws/{PREFECT_AWS_VERSION}" in override["config"].user_agent_extra
        )

    def test_caller_user_agent_extra_is_preserved(self):
        # If a caller already set user_agent_extra, the prefect-aws token is
        # appended without dropping the caller's value.
        params = AwsClientParameters(config=Config(user_agent_extra="my-app/1.0"))
        override = params.get_params_override()
        ua_extra = override["config"].user_agent_extra
        assert "my-app/1.0" in ua_extra
        assert f"prefect-aws/{PREFECT_AWS_VERSION}" in ua_extra

    def test_user_agent_extra_is_idempotent(self):
        # Calling get_params_override repeatedly must not duplicate the token.
        params = AwsClientParameters()
        first = params.get_params_override()["config"].user_agent_extra
        second = params.get_params_override()["config"].user_agent_extra
        assert first == second
        assert first.count(f"prefect-aws/{PREFECT_AWS_VERSION}") == 1

    def test_unsigned_signature_version_preserved_with_user_agent(self):
        # Regression: the UA-tagging step must not undo the manual
        # signature_version=UNSIGNED conversion that get_params_override
        # performs after constructing the Config.
        params = AwsClientParameters(config=Config(signature_version="unsigned"))
        override = params.get_params_override()
        assert override["config"].signature_version is UNSIGNED
        assert (
            f"prefect-aws/{PREFECT_AWS_VERSION}" in override["config"].user_agent_extra
        )

    def test_get_params_override_with_explicit_verify(self):
        params_true = AwsClientParameters(verify=True)
        params_false = AwsClientParameters(verify=False)

        override_params_true = params_true.get_params_override()
        override_params_false = params_false.get_params_override()

        assert "verify" in override_params_true, (
            "verify should be in params_override when explicitly set to True"
        )
        assert override_params_true["verify"] is True

        assert "verify" in override_params_false, (
            "verify should be in params_override when explicitly set to False"
        )
        assert override_params_false["verify"] is False
