from typing import Any, Dict

import pytest
from botocore import UNSIGNED
from botocore.client import Config
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
        assert result == params.get_params_override()

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
        assert (
            "verify" not in override_params
        ), "verify should not be in params_override when not explicitly set"

    def test_get_params_override_with_explicit_verify(self):
        params_true = AwsClientParameters(verify=True)
        params_false = AwsClientParameters(verify=False)

        override_params_true = params_true.get_params_override()
        override_params_false = params_false.get_params_override()

        assert (
            "verify" in override_params_true
        ), "verify should be in params_override when explicitly set to True"
        assert override_params_true["verify"] is True

        assert (
            "verify" in override_params_false
        ), "verify should be in params_override when explicitly set to False"
        assert override_params_false["verify"] is False
