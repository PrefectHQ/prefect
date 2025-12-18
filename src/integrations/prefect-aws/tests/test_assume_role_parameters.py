from typing import Any, Dict

import pytest
from prefect_aws.assume_role_parameters import AssumeRoleParameters


class TestAssumeRoleParameters:
    @pytest.mark.parametrize(
        "params,result",
        [
            (AssumeRoleParameters(), {}),
            (
                AssumeRoleParameters(
                    RoleSessionName="my-session",
                    DurationSeconds=3600,
                ),
                {
                    "RoleSessionName": "my-session",
                    "DurationSeconds": 3600,
                },
            ),
            (
                AssumeRoleParameters(
                    RoleSessionName="test-session",
                    ExternalId="unique-external-id",
                ),
                {
                    "RoleSessionName": "test-session",
                    "ExternalId": "unique-external-id",
                },
            ),
            (
                AssumeRoleParameters(
                    DurationSeconds=7200,
                    SourceIdentity="test-identity",
                ),
                {
                    "DurationSeconds": 7200,
                    "SourceIdentity": "test-identity",
                },
            ),
        ],
    )
    def test_get_params_override_expected_output(
        self, params: AssumeRoleParameters, result: Dict[str, Any]
    ):
        assert result == params.get_params_override()

    @pytest.mark.parametrize(
        "params,result",
        [
            (
                AssumeRoleParameters(
                    Tags=[
                        {"Key": "Project", "Value": "MyProject"},
                        {"Key": "Environment", "Value": "Production"},
                    ],
                ),
                {
                    "Tags": [
                        {"Key": "Project", "Value": "MyProject"},
                        {"Key": "Environment", "Value": "Production"},
                    ],
                },
            ),
            (
                AssumeRoleParameters(
                    PolicyArns=[
                        {"arn": "arn:aws:iam::aws:policy/ReadOnlyAccess"},
                        {"arn": "arn:aws:iam::aws:policy/PowerUserAccess"},
                    ],
                ),
                {
                    "PolicyArns": [
                        {"arn": "arn:aws:iam::aws:policy/ReadOnlyAccess"},
                        {"arn": "arn:aws:iam::aws:policy/PowerUserAccess"},
                    ],
                },
            ),
            (
                AssumeRoleParameters(
                    TransitiveTagKeys=["Project", "Environment"],
                ),
                {
                    "TransitiveTagKeys": ["Project", "Environment"],
                },
            ),
            (
                AssumeRoleParameters(
                    ProvidedContexts=[
                        {
                            "ProviderArn": "arn:aws:iam::123456789012:oidc-provider/example",
                            "ContextAssertion": "example-assertion",
                        }
                    ],
                ),
                {
                    "ProvidedContexts": [
                        {
                            "ProviderArn": "arn:aws:iam::123456789012:oidc-provider/example",
                            "ContextAssertion": "example-assertion",
                        }
                    ],
                },
            ),
        ],
    )
    def test_get_params_override_with_list_parameters(
        self, params: AssumeRoleParameters, result: Dict[str, Any]
    ):
        override_params = params.get_params_override()
        assert override_params == result

    def test_get_params_override_with_policy(self):
        policy = '{"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]}'
        params = AssumeRoleParameters(Policy=policy)
        override_params = params.get_params_override()
        assert override_params["Policy"] == policy

    def test_get_params_override_with_mfa(self):
        params = AssumeRoleParameters(
            SerialNumber="arn:aws:iam::123456789012:mfa/user",
            TokenCode="123456",
        )
        override_params = params.get_params_override()
        assert override_params["SerialNumber"] == "arn:aws:iam::123456789012:mfa/user"
        assert override_params["TokenCode"] == "123456"

    def test_get_params_override_with_all_parameters(self):
        params = AssumeRoleParameters(
            RoleSessionName="comprehensive-session",
            DurationSeconds=3600,
            Policy='{"Version": "2012-10-17", "Statement": []}',
            PolicyArns=[{"arn": "arn:aws:iam::aws:policy/ReadOnlyAccess"}],
            Tags=[{"Key": "Project", "Value": "Test"}],
            TransitiveTagKeys=["Project"],
            ExternalId="external-123",
            SerialNumber="arn:aws:iam::123456789012:mfa/user",
            TokenCode="123456",
            SourceIdentity="source-identity",
            ProvidedContexts=[
                {
                    "ProviderArn": "arn:aws:iam::123456789012:oidc-provider/example",
                    "ContextAssertion": "assertion",
                }
            ],
        )
        override_params = params.get_params_override()
        assert len(override_params) == 11
        assert override_params["RoleSessionName"] == "comprehensive-session"
        assert override_params["DurationSeconds"] == 3600
        assert override_params["Policy"] == '{"Version": "2012-10-17", "Statement": []}'
        assert len(override_params["PolicyArns"]) == 1
        assert len(override_params["Tags"]) == 1
        assert len(override_params["TransitiveTagKeys"]) == 1
        assert override_params["ExternalId"] == "external-123"
        assert override_params["SerialNumber"] == "arn:aws:iam::123456789012:mfa/user"
        assert override_params["TokenCode"] == "123456"
        assert override_params["SourceIdentity"] == "source-identity"
        assert len(override_params["ProvidedContexts"]) == 1

    def test_get_params_override_with_default_values(self):
        params = AssumeRoleParameters()
        override_params = params.get_params_override()
        assert override_params == {}, (
            "get_params_override should return empty dict when all values are None"
        )

    def test_get_params_override_excludes_none_values(self):
        params = AssumeRoleParameters(
            RoleSessionName="test-session",
            DurationSeconds=None,
            ExternalId=None,
        )
        override_params = params.get_params_override()
        assert "RoleSessionName" in override_params
        assert "DurationSeconds" not in override_params
        assert "ExternalId" not in override_params
        assert override_params["RoleSessionName"] == "test-session"

    def test_hash_with_nested_structures(self):
        params1 = AssumeRoleParameters(
            Tags=[
                {"Key": "Project", "Value": "MyProject"},
                {"Key": "Environment", "Value": "Production"},
            ],
            PolicyArns=[{"arn": "arn:aws:iam::aws:policy/ReadOnlyAccess"}],
        )
        params2 = AssumeRoleParameters(
            Tags=[
                {"Key": "Project", "Value": "MyProject"},
                {"Key": "Environment", "Value": "Production"},
            ],
            PolicyArns=[{"arn": "arn:aws:iam::aws:policy/ReadOnlyAccess"}],
        )
        params3 = AssumeRoleParameters(
            Tags=[
                {"Key": "Project", "Value": "MyProject"},
                {"Key": "Environment", "Value": "Development"},
            ],
            PolicyArns=[{"arn": "arn:aws:iam::aws:policy/ReadOnlyAccess"}],
        )

        # Same parameters should have same hash
        assert hash(params1) == hash(params2)

        # Different parameters should have different hash
        assert hash(params1) != hash(params3)

    def test_hash_with_different_parameters(self):
        params1 = AssumeRoleParameters(RoleSessionName="session1")
        params2 = AssumeRoleParameters(RoleSessionName="session2")
        params3 = AssumeRoleParameters(DurationSeconds=3600)
        params4 = AssumeRoleParameters(DurationSeconds=7200)

        # Different RoleSessionName should have different hash
        assert hash(params1) != hash(params2)

        # Different DurationSeconds should have different hash
        assert hash(params3) != hash(params4)

        # Different field types should have different hash
        assert hash(params1) != hash(params3)

    def test_hash_with_empty_parameters(self):
        params1 = AssumeRoleParameters()
        params2 = AssumeRoleParameters()

        # Empty parameters should have same hash
        assert hash(params1) == hash(params2)

    def test_hash_with_none_and_empty_lists(self):
        params1 = AssumeRoleParameters(Tags=None, TransitiveTagKeys=None)
        params2 = AssumeRoleParameters(Tags=None, TransitiveTagKeys=None)
        params3 = AssumeRoleParameters(Tags=[], TransitiveTagKeys=[])

        # None values should have same hash
        assert hash(params1) == hash(params2)

        # Empty list should have different hash than None
        assert hash(params1) != hash(params3)
