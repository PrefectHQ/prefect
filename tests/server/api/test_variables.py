import uuid
from typing import List

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

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
    VariableFilterValue,
)


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
            json=variable.dict(json_compatible=True),
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
        "variable_name", ["MY_VARIABLE", "my variable", "my-variable", "!@#$%"]
    )
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
            res.json()["exception_detail"][0]["msg"]
            == "Variable name must only contain lowercase letters, numbers, and"
            " underscores."
        )

    async def test_name_unique(
        self,
        client: AsyncClient,
        variable,
    ):
        same_name_variable = VariableCreate(name=variable.name, value="other-value")
        res = await client.post(
            "/variables/",
            json=same_name_variable.dict(json_compatible=True),
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
        assert (
            "ensure this value has at most" in res.json()["exception_detail"][0]["msg"]
        )

    async def test_value_max_length(
        self,
        client: AsyncClient,
    ):
        max_length = 5000

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
            "ensure this value has at most" in res.json()["exception_detail"][0]["msg"]
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
        res = pydantic.parse_obj_as(core.Variable, res.json())
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
        res = pydantic.parse_obj_as(core.Variable, res.json())
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
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
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
                ).dict(json_compatible=True)
            ),
        )
        assert res.status_code == 200
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
        assert len(res) == 1
        assert {v.id for v in res} == {v.id for v in variables if v.name == "variable1"}

        # like filter
        res = await client.post(
            "/variables/filter",
            json=dict(
                variables=VariableFilter(
                    name=VariableFilterName(like_="variable1%")
                ).dict(json_compatible=True)
            ),
        )
        assert res.status_code == 200
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
        assert len(res) == 2
        assert {v.id for v in res} == {v.id for v in variables if "variable1" in v.name}

    async def test_filter_value(
        self,
        client: AsyncClient,
        variables,
    ):
        # any filter
        res = await client.post(
            "/variables/filter",
            json=dict(
                variables=VariableFilter(
                    value=VariableFilterValue(any_=["value1"])
                ).dict(json_compatible=True)
            ),
        )
        assert res.status_code == 200
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
        assert len(res) == 1
        assert {v.id for v in res} == {v.id for v in variables if v.value == "value1"}

        # like filter
        res = await client.post(
            "/variables/filter",
            json=dict(
                variables=VariableFilter(
                    value=VariableFilterValue(like_="value1%")
                ).dict(json_compatible=True)
            ),
        )
        assert res.status_code == 200
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
        assert len(res) == 2
        assert {v.id for v in res} == {v.id for v in variables if "value1" in v.value}

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
                variables=VariableFilter(id=VariableFilterId(any_=[variable.id])).dict(
                    json_compatible=True
                )
            ),
        )
        assert res.status_code == 200
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
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
                variables=VariableFilter(tags=VariableFilterTags(all_=["tag1"])).dict(
                    json_compatible=True
                )
            ),
        )
        assert res.status_code == 200
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
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
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
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
        res = pydantic.parse_obj_as(List[core.Variable], res.json())
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
                ).dict(json_compatible=True)
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
                ).dict(json_compatible=True)
            ),
        )
        assert res.status_code == 200
        assert res.json() == 2

    async def test_filter_value(
        self,
        client: AsyncClient,
        variables,
    ):
        # any filter
        res = await client.post(
            "/variables/count",
            json=dict(
                variables=VariableFilter(
                    value=VariableFilterValue(any_=["value1"])
                ).dict(json_compatible=True)
            ),
        )
        assert res.status_code == 200
        assert res.json() == 1

        # like filter
        res = await client.post(
            "/variables/count",
            json=dict(
                variables=VariableFilter(
                    value=VariableFilterValue(like_="value1%")
                ).dict(json_compatible=True)
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
                variables=VariableFilter(id=VariableFilterId(any_=[variable.id])).dict(
                    json_compatible=True
                )
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
                variables=VariableFilter(tags=VariableFilterTags(all_=["tag1"])).dict(
                    json_compatible=True
                )
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
            json=update.dict(json_compatible=True),
        )
        assert res.status_code == 204
        res = await client.get(
            f"/variables/{variable.id}",
        )
        assert res.status_code == 200
        res = pydantic.parse_obj_as(core.Variable, res.json())
        assert res.id == variable.id
        assert res.name == update.name
        assert res.value == update.value
        assert res.tags == update.tags

    async def test_does_not_exist(
        self,
        client: AsyncClient,
    ):
        update = VariableUpdate(
            name="updated_variable", value="updated-value", tags=["updated-tag"]
        )
        res = await client.patch(
            f"/variables/{uuid.uuid4()}",
            json=update.dict(json_compatible=True),
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
            json=same_name_update.dict(json_compatible=True),
        )
        assert res
        assert res.status_code == 409

    async def test_name_max_length(
        self,
        client: AsyncClient,
        variable,
    ):
        max_length = 255

        res = await client.patch(
            f"/variables/{variable.id}", json={"name": "v" * max_length}
        )
        assert res
        assert res.status_code == 204

        max_length_plus1 = max_length + 1

        res = await client.patch(
            f"/variables/{variable.id}", json={"name": "v" * max_length_plus1}
        )
        assert res
        assert res.status_code == 422
        assert (
            "ensure this value has at most" in res.json()["exception_detail"][0]["msg"]
        )

    async def test_value_max_length(
        self,
        client: AsyncClient,
        variable,
    ):
        max_length = 5000

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
            "ensure this value has at most" in res.json()["exception_detail"][0]["msg"]
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
            json=update.dict(json_compatible=True),
        )
        assert res.status_code == 204
        res = await client.get(
            f"/variables/{variable.id}",
        )
        assert res.status_code == 200
        res = pydantic.parse_obj_as(core.Variable, res.json())
        assert res.id == variable.id
        assert res.name == update.name
        assert res.value == update.value
        assert res.tags == update.tags

    async def test_does_not_exist(
        self,
        client: AsyncClient,
    ):
        update = VariableUpdate(
            name="updated_variable", value="updated-value", tags=["updated-tag"]
        )
        res = await client.patch(
            "/variables/name/doesnotexist",
            json=update.dict(json_compatible=True),
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
            json=same_name_update.dict(json_compatible=True),
        )
        assert res.status_code == 409

    async def test_name_max_length(
        self,
        client: AsyncClient,
        variable,
    ):
        max_length = 255

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
        assert (
            "ensure this value has at most" in res.json()["exception_detail"][0]["msg"]
        )

    async def test_value_max_length(
        self,
        client: AsyncClient,
        variable,
    ):
        max_length = 5000

        res = await client.patch(
            f"/variables/name/{variable.name}", json={"value": "v" * max_length}
        )
        assert res
        assert res.status_code == 204

        max_length_plus1 = max_length + 1

        res = await client.patch(
            f"/variables/name/{variable.name}", json={"value": "v" * max_length_plus1}
        )
        assert res
        assert res.status_code == 422
        assert (
            "ensure this value has at most" in res.json()["exception_detail"][0]["msg"]
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
