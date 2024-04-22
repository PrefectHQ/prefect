import pytest
from prefect_databricks.models.jobs import (
    AccessControlRequest,
    AccessControlRequestForGroup,
    AccessControlRequestForUser,
    CanManage,
)
from prefect_databricks.rest import serialize_model


class TestModelsJobs:
    @pytest.mark.parametrize(
        "value, expected",
        [
            [
                AccessControlRequest(
                    group_name="foo", permission_level=CanManage.canmanage
                ),
                {
                    "group_name": "foo",
                    "permission_level": "CAN_MANAGE",
                    "user_name": None,
                },
            ],
            [
                AccessControlRequest(
                    user_name="foo", permission_level=CanManage.canmanage
                ),
                {
                    "user_name": "foo",
                    "permission_level": "CAN_MANAGE",
                    "group_name": None,
                },
            ],
            [
                AccessControlRequestForGroup(
                    group_name="foo", permission_level=CanManage.canmanage
                ),
                {"group_name": "foo", "permission_level": "CAN_MANAGE"},
            ],
            [
                AccessControlRequestForUser(
                    user_name="foo", permission_level=CanManage.canmanage
                ),
                {"user_name": "foo", "permission_level": "CAN_MANAGE"},
            ],
        ],
        ids=["acr_group", "acr_user", "acrg", "acru"],
    )
    def test_access_control_request_serialization(self, value, expected):
        serialized = serialize_model(value)
        assert serialized == expected
