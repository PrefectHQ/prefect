"""Module handling Assume Role parameters"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from prefect_aws.utilities import hash_collection


class AssumeRoleParameters(BaseModel):
    """
    Model used to manage parameters for the AWS STS assume_role call.
    Refer to the
    [boto3 STS assume_role docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts/client/assume_role.html)
    for more information about the possible assume role configurations.

    Attributes:
        RoleSessionName: An identifier for the assumed role session.
            This value is used to uniquely identify a session when the same role
            is assumed by different principals or for different reasons.
            If not provided, a default will be generated.
        DurationSeconds: The duration, in seconds, of the role session.
            The value can range from 900 seconds (15 minutes) to 43,200 seconds (12 hours).
        Policy: An IAM policy in JSON format that you want to use as an inline session policy.
        PolicyArns: The ARNs of the IAM managed policies to use as managed session policies.
            Each item should be a dict with an 'arn' key.
        Tags: A list of session tags. Each tag should be a dict with 'Key' and 'Value' keys.
        TransitiveTagKeys: A list of keys for session tags that you want to set as transitive.
            Transitive tags persist during role chaining.
        ExternalId: A unique identifier that is used by third parties to assume a role
            in their customers' accounts.
        SerialNumber: The identification number of the MFA device that is associated
            with the user who is making the AssumeRole call.
        TokenCode: The value provided by the MFA device, if MFA authentication is required.
        SourceIdentity: The source identity specified by the principal that is calling
            the AssumeRole operation.
        ProvidedContexts: A list of context information. Each context should be a dict
            with 'ProviderArn' and 'ContextAssertion' keys.
    """  # noqa E501

    RoleSessionName: Optional[str] = Field(
        default=None,
        description=(
            "An identifier for the assumed role session. "
            "If not provided, a default will be generated."
        ),
        title="Role Session Name",
    )
    DurationSeconds: Optional[int] = Field(
        default=None,
        description=(
            "The duration, in seconds, of the role session. "
            "The value can range from 900 seconds (15 minutes) to 43,200 seconds (12 hours)."
        ),
        title="Duration Seconds",
    )
    Policy: Optional[str] = Field(
        default=None,
        description="An IAM policy in JSON format that you want to use as an inline session policy.",
        title="Policy",
    )
    PolicyArns: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description=(
            "The ARNs of the IAM managed policies to use as managed session policies. "
            "Each item should be a dict with an 'arn' key."
        ),
        title="Policy ARNs",
    )
    Tags: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description=(
            "A list of session tags. Each tag should be a dict with 'Key' and 'Value' keys."
        ),
        title="Tags",
    )
    TransitiveTagKeys: Optional[List[str]] = Field(
        default=None,
        description=(
            "A list of keys for session tags that you want to set as transitive. "
            "Transitive tags persist during role chaining."
        ),
        title="Transitive Tag Keys",
    )
    ExternalId: Optional[str] = Field(
        default=None,
        description=(
            "A unique identifier that is used by third parties to assume a role "
            "in their customers' accounts."
        ),
        title="External ID",
    )
    SerialNumber: Optional[str] = Field(
        default=None,
        description=(
            "The identification number of the MFA device that is associated "
            "with the user who is making the AssumeRole call."
        ),
        title="Serial Number",
    )
    TokenCode: Optional[str] = Field(
        default=None,
        description="The value provided by the MFA device, if MFA authentication is required.",
        title="Token Code",
    )
    SourceIdentity: Optional[str] = Field(
        default=None,
        description=(
            "The source identity specified by the principal that is calling "
            "the AssumeRole operation."
        ),
        title="Source Identity",
    )
    ProvidedContexts: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description=(
            "A list of context information. Each context should be a dict "
            "with 'ProviderArn' and 'ContextAssertion' keys."
        ),
        title="Provided Contexts",
    )

    def __hash__(self):
        """Compute hash of the assume role parameters."""
        return hash(
            (
                self.RoleSessionName,
                self.DurationSeconds,
                self.Policy,
                hash_collection(self.PolicyArns),
                hash_collection(self.Tags),
                hash_collection(self.TransitiveTagKeys),
                self.ExternalId,
                self.SerialNumber,
                self.TokenCode,
                self.SourceIdentity,
                hash_collection(self.ProvidedContexts),
            )
        )

    def get_params_override(self) -> Dict[str, Any]:
        """
        Return the dictionary of the parameters to override.
        The parameters to override are the ones which are not None.
        """
        params = self.model_dump()
        params_override = {}
        for key, value in params.items():
            if value is not None:
                params_override[key] = value
        return params_override
