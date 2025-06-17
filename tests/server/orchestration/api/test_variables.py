import uuid
from typing import Any, List

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.models.variables import create_variable
from prefect.server.schemas import core, sorting
from prefect.server.schemas.actions import VariableCreate, VariableUpdate
from prefect.server.schemas.filters import (
    VariableFilter,
    VariableFilterId,
    VariableFilterName,
    VariableFilterTags,
)
from prefect.types import MAX_VARIABLE_NAME_LENGTH, MAX_VARIABLE_VALUE_LENGTH
from prefect.utilities.pydantic import parse_obj_as


@pytest.fixture
async def variable(
    session: AsyncSession,
):
    model = await create_variable(
        session,
        VariableCreate(name="my_variable", value="my-value", tags=["123", "456"]),
    )
    await session.commit()

    return model


@pytest.fixture
async def variables(
    session: AsyncSession,
):
    variables = [
        VariableCreate(name="variable1", value="value1", tags=["tag1"]),
        VariableCreate(name="variable12", value="value12", tags=["tag2"]),
        VariableCreate(name="variable2", value="value2", tags=["tag1"]),
        VariableCreate(name="variable21", value="value21", tags=["tag2"]),
    ]
    models = []
    for variable in variables:
        model = await create_variable(session, variable)
        models.append(model)
    await session.commit()

    return models


class TestCreateVariable:
    async def test_create_variable(
        self,
        client: AsyncClient,
    ):
        variable = VariableCreate(
            name="my_variable", value="my-value", tags=["123", "456"]
        )
        res = await client.post(
            "/variables/",
            json=variable.model_dump(mode="json"),
        )
        assert res
        assert res.status_code == 201

        res = res.json()
        assert res["id"]
        assert res["created"]
        assert res["updated"]

        assert res["name"] == variable.name
        assert res["value"] == variable.value
        assert res["tags"] == variable.tags

    @pytest.mark.parametrize(
        "value",
        [
            "string-value",
            '"string-value"',
            123,
            12.3,
            True,
            False,
            None,
            {"key": "value"},
            ["value1", "value2"],
            {"key": ["value1", "value2"]},
        ],
    )
    async def test_create_variable_json_types(
        self,
        client: AsyncClient,
        value: Any,
    ):
        response = await client.post(
            "/variables/",
            json={"name": "my_variable", "value": value},
        )

        assert response
        assert response.status_code == 201

        res = response.json()
        assert res["id"]
        assert res["created"]
        assert res["updated"]

        assert res["value"] == value

    @pytest.mark.parametrize("variable_name", ["my-variable", "my_variable"])
    async def test_variable_name_may_contain_dashes_or_underscores(
        self,
        client: AsyncClient,
        variable_name: str,
    ):
        response = await client.post(
            "/variables/",
            json={"name": variable_name, "value": "my-value"},
        )
        assert response
        assert response.status_code == 201

        res = response.json()
        assert res["id"]
        assert res["created"]
        assert res["updated"]

        assert res["name"] == variable_name
        assert res["value"] == "my-value"
        assert res["tags"] == []

    @pytest.mark.parametrize("variable_name", ["MY_VARIABLE", "my variable", "!@#$%"])
    async def test_name_constraints(
        self,
        client: AsyncClient,
        variable_name: str,
    ):
        res = await client.post(
            "/variables/",
            json={"name": variable_name, "value": "my-value"},
        )
        assert res
        assert res.status_code == 422
        assert (
            "Variable name must only contain lowercase letters, numbers, and dashes or underscores."
            in res.json()["exception_detail"][0]["msg"]
        )

    async def test_name_unique(
        self,
        client: AsyncClient,
        variable,
    ):
        same_name_variable = VariableCreate(name=variable.name, value="other-value")
        res = await client.post(
            "/variables/",
            json=same_name_variable.model_dump(mode="json"),
        )
        assert res
        assert res.status_code == 409

    async def test_name_max_length(
        self,
        client: AsyncClient,
    ):
        max_length = 255

        res = await client.post(
            "/variables/",
            json={"name": "v" * max_length, "value": "value"},
        )
        assert res
        assert res.status_code == 201

        max_length_plus1 = max_length + 1

        res = await client.post(
            "/variables/",
            json={"name": "v" * max_length_plus1, "value": "value"},
        )
        assert res
        assert res.status_code == 422
        assert "String should have at most" in res.json()["exception_detail"][0]["msg"]

    async def test_value_max_length(
        self,
        client: AsyncClient,
    ):
        max_length = MAX_VARIABLE_VALUE_LENGTH - 2  # 2 characters for quotes

        res = await client.post(
            "/variables/",
            json={"name": "name", "value": "v" * max_length},
        )
        assert res
        assert res.status_code == 201

        max_length_plus1 = max_length + 1

        res = await client.post(
            "/variables/",
            json={"name": "name", "value": "v" * max_length_plus1},
        )
        assert res
        assert res.status_code == 422
        assert (
            "Variable value must be less than"
            in res.json()["exception_detail"][0]["msg"]
        )


class TestReadVariable:
    async def test_read_variable(
        self,
        client: AsyncClient,
        variable,
    ):
        res = await client.get(
            f"/variables/{variable.id}",
        )
        assert res.status_code == 200
        res = parse_obj_as(core.Variable, res.json())
        assert res.id == variable.id
        assert res.name == variable.name
        assert res.tags == variable.tags

    async def test_does_not_exist(
        self,
        client: AsyncClient,
    ):
        res = await client.get(
            f"/variables/{uuid.uuid4()}",
        )
        assert res.status_code == 404


class TestReadVariableByName:
    async def test_read_variable(
        self,
        client: AsyncClient,
        variable,
    ):
        res = await client.get(
            f"/variables/name/{variable.name}",
        )
        assert res.status_code == 200
        res = parse_obj_as(core.Variable, res.json())
        assert res.id == variable.id
        assert res.name == variable.name
        assert res.tags == variable.tags

    async def test_does_not_exist(
        self,
        client: AsyncClient,
    ):
        res = await client.get(
            "/variables/name/doesntexist",
        )
        assert res.status_code == 404


class TestReadVariables:
    async def test_no_results(
        self,
        client: AsyncClient,
    ):
        res = await client.post(
            "/variables/filter",
        )
        assert res.status_code == 200
        assert len(res.json()) == 0

    async def test_no_filter(
        self,
        client: AsyncClient,
        variables,
    ):
        res = await client.post(
            "/variables/filter",
        )
        assert res.status_code == 200
        res = parse_obj_as(List[core.Variable], res.json())
        assert len(res) == len(variables)
        assert {v.id for v in res} == {v.id for v in variables}

    async def test_filter_name(
        self,
        client: AsyncClient,
        variables,
    ):
        # any filter
        res = await client.post(
            "/variables/filter",
            json=dict(
                variables=VariableFilter(
                    name=VariableFilterName(any_=["variable1"])
                ).model_dump(mode="json")
            ),
        )
        assert res.status_code == 200
        res = parse_obj_as(List[core.Variable], res.json())
        assert len(res) == 1
        assert {v.id for v in res} == {v.id for v in variables if v.name == "variable1"}

        # like filter
        res = await client.post(
            "/variables/filter",
            json=dict(
                variables=VariableFilter(
                    name=VariableFilterName(like_="variable1%")
                ).model_dump(mode="json")
            ),
        )
        assert res.status_code == 200
        res = parse_obj_as(List[core.Variable], res.json())
        assert len(res) == 2
        assert {v.id for v in res} == {v.id for v in variables if "variable1" in v.name}

    async def test_filter_id(
        self,
        client: AsyncClient,
        variables,
    ):
        variable = variables[0]
        # any filter
        res = await client.post(
            "/variables/filter",
            json=dict(
                variables=VariableFilter(
                    id=VariableFilterId(any_=[variable.id])
                ).model_dump(mode="json")
            ),
        )
        assert res.status_code == 200
        res = parse_obj_as(List[core.Variable], res.json())
        assert len(res) == 1
        assert {v.id for v in res} == {variable.id}

    async def test_filter_tags(
        self,
        client: AsyncClient,
        variables,
    ):
        # any filter
        res = await client.post(
            "/variables/filter",
            json=dict(
                variables=VariableFilter(
                    tags=VariableFilterTags(all_=["tag1"])
                ).model_dump(mode="json")
            ),
        )
        assert res.status_code == 200
        res = parse_obj_as(List[core.Variable], res.json())
        assert len(res) == 2
        assert {v.id for v in res} == {v.id for v in variables if "tag1" in v.tags}

    async def test_name_sorted_forwards(
        self,
        client: AsyncClient,
        variables,
    ):
        # name sorted forwards
        res = await client.post(
            "/variables/filter",
            json={"sort": sorting.VariableSort.NAME_ASC},
        )
        assert res.status_code == 200
        res = parse_obj_as(List[core.Variable], res.json())
        assert len(res) == len(variables)
        assert [v.name for v in res] == sorted([v.name for v in variables])

    async def test_name_sorted_backwards(
        self,
        client: AsyncClient,
        variables,
    ):
        # name sorted backwards
        res = await client.post(
            "/variables/filter",
            json={"sort": sorting.VariableSort.NAME_DESC},
        )
        assert res.status_code == 200
        res = parse_obj_as(List[core.Variable], res.json())
        assert len(res) == len(variables)
        assert [v.name for v in res] == sorted(
            [v.name for v in variables], reverse=True
        )


class TestCountVariables:
    async def test_no_results(
        self,
        client: AsyncClient,
    ):
        res = await client.post(
            "/variables/count",
        )
        assert res.status_code == 200
        assert res.json() == 0

    async def test_no_filter(
        self,
        client: AsyncClient,
        variables,
    ):
        res = await client.post(
            "/variables/count",
        )
        assert res.status_code == 200
        assert res.json() == 4

    async def test_filter_name(
        self,
        client: AsyncClient,
        variables,
    ):
        # any filter
        res = await client.post(
            "/variables/count",
            json=dict(
                variables=VariableFilter(
                    name=VariableFilterName(any_=["variable1"])
                ).model_dump(mode="json")
            ),
        )
        assert res.status_code == 200
        assert res.json() == 1

        # like filter
        res = await client.post(
            "/variables/count",
            json=dict(
                variables=VariableFilter(
                    name=VariableFilterName(like_="variable1%")
                ).model_dump(mode="json")
            ),
        )
        assert res.status_code == 200
        assert res.json() == 2

    async def test_filter_id(
        self,
        client: AsyncClient,
        variables,
    ):
        variable = variables[0]
        # any filter
        res = await client.post(
            "/variables/count",
            json=dict(
                variables=VariableFilter(
                    id=VariableFilterId(any_=[variable.id])
                ).model_dump(mode="json")
            ),
        )
        assert res.json() == 1

    async def test_filter_tags(
        self,
        client: AsyncClient,
        variables,
    ):
        # any filter
        res = await client.post(
            "/variables/count",
            json=dict(
                variables=VariableFilter(
                    tags=VariableFilterTags(all_=["tag1"])
                ).model_dump(mode="json")
            ),
        )
        assert res.status_code == 200
        assert res.json() == 2


class TestUpdateVariable:
    async def test_update_variable(
        self,
        client: AsyncClient,
        variable,
    ):
        update = VariableUpdate(
            name="updated_variable", value="updated-value", tags=["updated-tag"]
        )
        res = await client.patch(
            f"/variables/{variable.id}",
            json=update.model_dump(mode="json"),
        )
        assert res.status_code == 204
        res = await client.get(
            f"/variables/{variable.id}",
        )
        assert res.status_code == 200
        res = parse_obj_as(core.Variable, res.json())
        assert res.id == variable.id
        assert res.name == update.name
        assert res.value == update.value
        assert res.tags == update.tags

    @pytest.mark.parametrize(
        "value",
        [
            "string-value",
            '"string-value"',
            123,
            12.3,
            True,
            False,
            None,
            {"key": "value"},
            ["value1", "value2"],
            {"key": ["value1", "value2"]},
        ],
    )
    async def test_update_variable_json_types(
        self,
        client: AsyncClient,
        variable,
        value: Any,
    ):
        response = await client.patch(
            f"/variables/{variable.id}",
            json={"value": value},
        )
        assert response.status_code == 204

        response = await client.get(
            f"/variables/{variable.id}",
        )
        assert response.status_code == 200
        res = response.json()
        assert res["value"] == value

    async def test_does_not_exist(
        self,
        client: AsyncClient,
    ):
        update = VariableUpdate(
            name="updated_variable", value="updated-value", tags=["updated-tag"]
        )
        res = await client.patch(
            f"/variables/{uuid.uuid4()}",
            json=update.model_dump(mode="json"),
        )
        assert res.status_code == 404

    async def test_name_unique(
        self,
        client: AsyncClient,
        variable,
    ):
        same_name_update = VariableUpdate(name=variable.name)
        res = await client.patch(
            f"/variables/{variable.id}",
            json=same_name_update.model_dump(mode="json"),
        )
        assert res
        assert res.status_code == 409

    async def test_name_max_length(
        self,
        client: AsyncClient,
        variable,
    ):
        res = await client.patch(
            f"/variables/{variable.id}", json={"name": "v" * MAX_VARIABLE_NAME_LENGTH}
        )
        assert res
        assert res.status_code == 204

        max_length_plus1 = MAX_VARIABLE_NAME_LENGTH + 1

        res = await client.patch(
            f"/variables/{variable.id}", json={"name": "v" * max_length_plus1}
        )
        assert res
        assert res.status_code == 422
        assert "Value should have at most" in res.json()["exception_detail"][0]["msg"]

    async def test_value_max_length(
        self,
        client: AsyncClient,
        variable,
    ):
        max_length = MAX_VARIABLE_VALUE_LENGTH - 2  # 2 characters for quotes

        res = await client.patch(
            f"/variables/{variable.id}", json={"value": "v" * max_length}
        )
        assert res
        assert res.status_code == 204

        max_length_plus1 = max_length + 1

        res = await client.patch(
            f"/variables/{variable.id}", json={"value": "v" * max_length_plus1}
        )
        assert res
        assert res.status_code == 422
        assert (
            "Variable value must be less than"
            in res.json()["exception_detail"][0]["msg"]
        )


class TestUpdateVariableByName:
    async def test_update_variable(
        self,
        client: AsyncClient,
        variable,
    ):
        update = VariableUpdate(
            name="updated_variable", value="updated-value", tags=["updated-tag"]
        )
        res = await client.patch(
            f"/variables/name/{variable.name}",
            json=update.model_dump(mode="json"),
        )
        assert res.status_code == 204
        res = await client.get(
            f"/variables/{variable.id}",
        )
        assert res.status_code == 200
        res = parse_obj_as(core.Variable, res.json())
        assert res.id == variable.id
        assert res.name == update.name
        assert res.value == update.value
        assert res.tags == update.tags

    @pytest.mark.parametrize(
        "value",
        [
            "string-value",
            '"string-value"',
            123,
            12.3,
            True,
            False,
            None,
            {"key": "value"},
            ["value1", "value2"],
            {"key": ["value1", "value2"]},
        ],
    )
    async def test_update_variable_json_types(
        self,
        client: AsyncClient,
        variable,
        value: Any,
    ):
        response = await client.patch(
            f"/variables/name/{variable.name}",
            json={"value": value},
        )
        assert response.status_code == 204

        response = await client.get(
            f"/variables/{variable.id}",
        )
        assert response.status_code == 200
        res = response.json()
        assert res["value"] == value

    async def test_does_not_exist(
        self,
        client: AsyncClient,
    ):
        update = VariableUpdate(
            name="updated_variable", value="updated-value", tags=["updated-tag"]
        )
        res = await client.patch(
            "/variables/name/doesnotexist",
            json=update.model_dump(mode="json"),
        )
        assert res.status_code == 404

    async def test_name_unique(
        self,
        client: AsyncClient,
        variable,
    ):
        same_name_update = VariableUpdate(name=variable.name)
        res = await client.patch(
            f"/variables/name/{variable.name}",
            json=same_name_update.model_dump(mode="json"),
        )
        assert res.status_code == 409

    async def test_name_max_length(
        self,
        client: AsyncClient,
        variable,
    ):
        max_length = MAX_VARIABLE_NAME_LENGTH

        res = await client.patch(
            f"/variables/name/{variable.name}", json={"name": "v" * max_length}
        )
        assert res
        assert res.status_code == 204

        max_length_plus1 = max_length + 1

        res = await client.patch(
            f"/variables/name/{variable.name}", json={"name": "v" * max_length_plus1}
        )
        assert res
        assert res.status_code == 422
        assert "Value should have at most" in res.json()["exception_detail"][0]["msg"]

    async def test_value_max_length(
        self,
        client: AsyncClient,
        variable,
    ):
        max_length = MAX_VARIABLE_VALUE_LENGTH - 2  # 2 characters for quotes

        res = await client.patch(
            f"/variables/name/{variable.name}", json={"value": "v" * max_length}
        )
        assert res
        assert res.status_code == 204

        max_length_plus1 = MAX_VARIABLE_VALUE_LENGTH + 1

        res = await client.patch(
            f"/variables/name/{variable.name}", json={"value": "v" * max_length_plus1}
        )
        assert res
        assert res.status_code == 422
        assert (
            "Variable value must be less than"
            in res.json()["exception_detail"][0]["msg"]
        )


class TestDeleteVariable:
    async def test_delete_variable(
        self,
        client: AsyncClient,
        variable,
    ):
        res = await client.delete(
            f"/variables/{variable.id}",
        )
        assert res.status_code == 204
        res = await client.get(
            f"/variables/{variable.id}",
        )
        assert res.status_code == 404

    async def test_does_not_exist(
        self,
        client: AsyncClient,
    ):
        res = await client.delete(
            f"/variables/{uuid.uuid4()}",
        )
        assert res.status_code == 404


class TestDeleteVariableByName:
    async def test_delete_variable(
        self,
        client: AsyncClient,
        variable,
    ):
        res = await client.delete(
            f"/variables/name/{variable.name}",
        )
        assert res.status_code == 204
        res = await client.get(
            f"/variables/name/{variable.name}",
        )
        assert res.status_code == 404

    async def test_does_not_exist(
        self,
        client: AsyncClient,
    ):
        res = await client.delete(
            "/variables/name/doesntexist",
        )
        assert res.status_code == 404


class TestDuplicateVariable:
    async def test_duplicate_variable_basic(
        self,
        client: AsyncClient,
        variable,
    ):
        duplicate_data = {
            "name": f"{variable.name}_copy",
            "value": variable.value,
            "tags": variable.tags,
        }
        res = await client.post(
            "/variables/",
            json=duplicate_data,
        )
        assert res.status_code == 201

        res_data = res.json()
        assert res_data["id"] != str(variable.id)
        assert res_data["name"] == duplicate_data["name"]
        assert res_data["value"] == duplicate_data["value"]
        assert res_data["tags"] == duplicate_data["tags"]

    async def test_duplicate_variable_fails_same_name(
        self,
        client: AsyncClient,
        variable,
    ):
        duplicate_data = {
            "name": variable.name,
            "value": variable.value,
            "tags": variable.tags,
        }
        res = await client.post(
            "/variables/",
            json=duplicate_data,
        )
        assert res.status_code == 409

    async def test_duplicate_variable_preserves_original(
        self,
        client: AsyncClient,
        variable,
    ):
        duplicate_data = {
            "name": f"{variable.name}_copy",
            "value": variable.value,
            "tags": variable.tags,
        }
        await client.post("/variables/", json=duplicate_data)

        original_res = await client.get(f"/variables/{variable.id}")
        original_data = original_res.json()
        assert original_data["id"] == str(variable.id)
        assert original_data["name"] == variable.name
        assert original_data["value"] == variable.value
        assert original_data["tags"] == variable.tags

    async def test_duplicate_variable_multiple_copies(
        self,
        client: AsyncClient,
        variable,
    ):
        copies = []
        for i in range(3):
            duplicate_data = {
                "name": f"{variable.name}_copy_{i}",
                "value": variable.value,
                "tags": variable.tags,
            }
            res = await client.post(
                "/variables/",
                json=duplicate_data,
            )
            assert res.status_code == 201
            copies.append(res.json())

        for i, copy in enumerate(copies):
            assert copy["name"] == f"{variable.name}_copy_{i}"
            assert copy["id"] != str(variable.id)
            for j, other_copy in enumerate(copies):
                if i != j:
                    assert copy["id"] != other_copy["id"]

    async def test_duplicate_variable_chain_duplication(
        self,
        client: AsyncClient,
        variable,
    ):
        first_duplicate_data = {
            "name": f"{variable.name}_copy",
            "value": variable.value,
            "tags": variable.tags,
        }
        first_res = await client.post(
            "/variables/",
            json=first_duplicate_data,
        )
        assert first_res.status_code == 201
        first_duplicate = first_res.json()

        second_duplicate_data = {
            "name": f"{variable.name}_copy_of_copy",
            "value": first_duplicate["value"],
            "tags": first_duplicate["tags"],
        }
        second_res = await client.post(
            "/variables/",
            json=second_duplicate_data,
        )
        assert second_res.status_code == 201
        second_duplicate = second_res.json()

        assert second_duplicate["id"] != first_duplicate["id"]
        assert second_duplicate["id"] != str(variable.id)
        assert second_duplicate["name"] == f"{variable.name}_copy_of_copy"

    async def test_duplicate_variable_with_json_value(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ):
        json_value = {"config": {"timeout": 300, "retries": 3}, "enabled": True}
        await create_variable(
            session,
            VariableCreate(name="json_variable", value=json_value, tags=["json"]),
        )
        await session.commit()

        duplicate_data = {
            "name": "json_variable_copy",
            "value": json_value,
            "tags": ["json", "duplicated"],
        }
        res = await client.post(
            "/variables/",
            json=duplicate_data,
        )
        assert res.status_code == 201

        res_data = res.json()
        assert res_data["value"] == json_value
        assert res_data["tags"] == ["json", "duplicated"]

    async def test_duplicate_variable_with_null_value(
        self,
        client: AsyncClient,
        session: AsyncSession,
    ):
        await create_variable(
            session,
            VariableCreate(name="null_variable", value=None, tags=["null"]),
        )
        await session.commit()

        duplicate_data = {
            "name": "null_variable_copy",
            "value": None,
            "tags": ["null", "duplicated"],
        }
        res = await client.post(
            "/variables/",
            json=duplicate_data,
        )
        assert res.status_code == 201

        res_data = res.json()
        assert res_data["value"] is None
        assert res_data["name"] == "null_variable_copy"
