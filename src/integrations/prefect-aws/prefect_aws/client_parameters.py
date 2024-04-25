"""Module handling Client parameters"""

import warnings
from typing import Any, Dict, Optional, Union

from botocore import UNSIGNED
from botocore.client import Config
from pydantic import VERSION as PYDANTIC_VERSION

from prefect_aws.utilities import hash_collection

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import BaseModel, Field, FilePath, root_validator, validator
else:
    from pydantic import BaseModel, Field, FilePath, root_validator, validator


class AwsClientParameters(BaseModel):
    """
    Model used to manage extra parameters that you can pass when you initialize
    the Client. If you want to find more information, see
    [boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/core/session.html)
    for more info about the possible client configurations.

    Attributes:
        api_version: The API version to use. By default, botocore will
            use the latest API version when creating a client. You only need
            to specify this parameter if you want to use a previous API version
            of the client.
        use_ssl: Whether or not to use SSL. By default, SSL is used.
            Note that not all services support non-ssl connections.
        verify: Whether or not to verify SSL certificates. By default
            SSL certificates are verified. If False, SSL will still be used
            (unless use_ssl is False), but SSL certificates
            will not be verified. Passing a file path to this is deprecated.
        verify_cert_path: A filename of the CA cert bundle to
            use. You can specify this argument if you want to use a
            different CA cert bundle than the one used by botocore.
        endpoint_url: The complete URL to use for the constructed
            client. Normally, botocore will automatically construct the
            appropriate URL to use when communicating with a service. You
            can specify a complete URL (including the "http/https" scheme)
            to override this behavior. If this value is provided,
            then ``use_ssl`` is ignored.
        config: Advanced configuration for Botocore clients. See
            [botocore docs](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html)
            for more details.
    """  # noqa E501

    api_version: Optional[str] = Field(
        default=None, description="The API version to use.", title="API Version"
    )
    use_ssl: bool = Field(
        default=True, description="Whether or not to use SSL.", title="Use SSL"
    )
    verify: Union[bool, FilePath] = Field(
        default=True, description="Whether or not to verify SSL certificates."
    )
    verify_cert_path: Optional[FilePath] = Field(
        default=None,
        description="Path to the CA cert bundle to use.",
        title="Certificate Authority Bundle File Path",
    )
    endpoint_url: Optional[str] = Field(
        default=None,
        description="The complete URL to use for the constructed client.",
        title="Endpoint URL",
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Advanced configuration for Botocore clients.",
        title="Botocore Config",
    )

    def __hash__(self):
        return hash(
            (
                self.api_version,
                self.use_ssl,
                self.verify,
                self.verify_cert_path,
                self.endpoint_url,
                hash_collection(self.config),
            )
        )

    @validator("config", pre=True)
    def instantiate_config(cls, value: Union[Config, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Casts lists to Config instances.
        """
        if isinstance(value, Config):
            return value.__dict__["_user_provided_options"]
        return value

    @root_validator
    def deprecated_verify_cert_path(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        If verify is not a bool, raise a warning.
        """
        verify = values.get("verify")

        # deprecate using verify in favor of verify_cert_path
        # so the UI looks nicer
        if verify is not None and not isinstance(verify, bool):
            warnings.warn(
                (
                    "verify should be a boolean. "
                    "If you want to use a CA cert bundle, use verify_cert_path instead."
                ),
                DeprecationWarning,
            )
        return values

    @root_validator
    def verify_cert_path_and_verify(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        If verify_cert_path is set but verify is False, raise a warning.
        """
        verify = values.get("verify", True)
        verify_cert_path = values.get("verify_cert_path")

        if not verify and verify_cert_path:
            warnings.warn(
                "verify_cert_path is set but verify is False. "
                "verify_cert_path will be ignored."
            )
            values["verify_cert_path"] = None
        elif not isinstance(verify, bool) and verify_cert_path:
            warnings.warn(
                "verify_cert_path is set but verify is also set as a file path. "
                "verify_cert_path will take precedence."
            )
            values["verify"] = True
        return values

    def get_params_override(self) -> Dict[str, Any]:
        """
        Return the dictionary of the parameters to override.
        The parameters to override are the one which are not None.
        """
        params = self.dict()
        if params.get("verify_cert_path"):
            # to ensure that verify doesn't re-overwrite verify_cert_path
            params.pop("verify")

        params_override = {}
        for key, value in params.items():
            if value is None:
                continue
            elif key == "config":
                params_override[key] = Config(**value)
                # botocore UNSIGNED is an instance while actual signers can
                # be fetched as strings
                if params_override[key].signature_version == "unsigned":
                    params_override[key].signature_version = UNSIGNED
            elif key == "verify_cert_path":
                params_override["verify"] = value
            else:
                params_override[key] = value
        return params_override
