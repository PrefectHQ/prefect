import uuid

import pytest
import sqlalchemy as sa

from prefect.server.models.variables import (
    count_variables,
    create_variable,
    delete_variable,
    delete_variable_by_name,
    read_variable,
    read_variable_by_name,
    read_variables,
    update_variable,
    update_variable_by_name,
)
from prefect.server.schemas.actions import VariableCreate, VariableUpdate
from prefect.server.schemas.filters import (
    VariableFilter,
    VariableFilterId,
    VariableFilterName,
    VariableFilterTags,
)
from prefect.server.schemas.sorting import VariableSort
from prefect.types._datetime import now


@pytest.fixture
async def variable(
    session,
):
    model = await create_variable(
        session,
        VariableCreate(name="my_variable", value="my-value", tags=["123", "456"]),
    )
    await session.commit()

    return model


@pytest.fixture
async def variables(
    session,
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
        session,
    ):
        current_time = now("UTC")

        variable = VariableCreate(
            name="my_variable", value="my-value", tags=["123", "456"]
        )
        model = await create_variable(session, variable)
        await session.commit()

        assert model
        assert model.id
        assert model.created and model.created > current_time
        assert model.updated and model.updated > current_time
        assert model.name == variable.name
        assert model.value == variable.value
        assert model.tags == variable.tags

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
    async def test_create_variable_json_types(self, session, value):
        variable = VariableCreate(name="my_variable", value=value, tags=["123", "456"])
        model = await create_variable(session, variable)
        await session.commit()
        assert model
        assert model.id
        assert model.value == variable.value == value

    async def test_create_variable_name_unique(
        self,
        session,
        variable,
    ):
        with pytest.raises(sa.exc.IntegrityError):
            await create_variable(
                session,
                VariableCreate(
                    name="my_variable", value="my-value", tags=["123", "456"]
                ),
            )


class TestReadVariable:
    async def test_read_variable(
        self,
        session,
        variable,
    ):
        model = await read_variable(session, variable.id)  # type: ignore
        assert model
        assert model.id == variable.id
        assert model.name == variable.name
        assert model.tags == variable.tags


class TestReadVariableByName:
    async def test_read_variable(
        self,
        session,
        variable,
    ):
        model = await read_variable_by_name(session, variable.name)
        assert model
        assert model.id == variable.id
        assert model.name == variable.name
        assert model.tags == variable.tags


class TestReadVariables:
    async def test_no_filter(
        self,
        session,
        variables,
    ):
        res = await read_variables(session)
        assert len(res) == 4
        assert {r.id for r in res} == {v.id for v in variables}

    async def test_filter_by_id(
        self,
        session,
        variables,
    ):
        variable = variables[0]

        res = await read_variables(
            session,
            variable_filter=VariableFilter(id=VariableFilterId(any_=[variable.id])),
        )
        assert len(res) == 1
        assert res[0].id == variable.id

    async def test_filter_by_any_name(
        self,
        session,
        variables,
    ):
        res = await read_variables(
            session,
            variable_filter=VariableFilter(name=VariableFilterName(any_=["variable1"])),
        )
        assert len(res) == 1
        assert {r.id for r in res} == {v.id for v in variables if "variable1" == v.name}

    async def test_filter_by_like_name(
        self,
        session,
        variables,
    ):
        res = await read_variables(
            session,
            variable_filter=VariableFilter(name=VariableFilterName(like_="variable1%")),
        )
        assert len(res) == 2
        assert {r.id for r in res} == {v.id for v in variables if "variable1" in v.name}

    async def test_filter_by_tag(
        self,
        session,
        variables,
    ):
        res = await read_variables(
            session,
            variable_filter=VariableFilter(tags=VariableFilterTags(all_=["tag1"])),
        )
        assert len(res) == 2
        assert {r.id for r in res} == {v.id for v in variables if "tag1" in v.tags}

    async def test_sorted_by_name_asc(
        self,
        session,
        variables,
    ):
        res = await read_variables(session, sort=VariableSort.NAME_ASC)
        assert len(res) == 4
        assert [r.name for r in res] == sorted([v.name for v in variables])

    async def test_sorted_by_name_desc(
        self,
        session,
        variables,
    ):
        res = await read_variables(session, sort=VariableSort.NAME_DESC)
        assert len(res) == 4
        assert [r.name for r in res] == sorted(
            [v.name for v in variables], reverse=True
        )


class TestCountVariables:
    async def test_count_zero_variables(
        self,
        session,
    ):
        res = await count_variables(session)
        assert res == 0

    async def test_count_one_variables(
        self,
        session,
        variable,
    ):
        res = await count_variables(session)
        assert res == 1

    async def test_count_variables_with_filter(
        self,
        session,
        variables,
    ):
        res = await count_variables(
            session,
            variable_filter=VariableFilter(name=VariableFilterName(like_="variable1%")),
        )
        assert res == 2


class TestUpdateVariable:
    async def test_update_name(
        self,
        session,
        variable,
    ):
        new_name = "another_name"
        updated = await update_variable(
            session,
            variable.id,
            VariableUpdate(name=new_name),  # type: ignore
        )
        assert updated

        updated_variable = await read_variable(session, variable.id)  # type: ignore
        assert updated_variable
        assert updated_variable.name == new_name

    async def test_update_value(
        self,
        session,
        variable,
    ):
        new_value = "another_name"
        updated = await update_variable(
            session,
            variable.id,
            VariableUpdate(value=new_value),  # type: ignore
        )
        assert updated

        updated_variable = await read_variable(session, variable.id)  # type: ignore
        assert updated_variable
        assert updated_variable.value == new_value

    async def test_update_tags(
        self,
        session,
        variable,
    ):
        new_tags = ["new-tag-123"]
        updated = await update_variable(
            session,
            variable.id,
            VariableUpdate(tags=new_tags),  # type: ignore
        )
        assert updated

        updated_variable = await read_variable(session, variable.id)  # type: ignore
        assert updated_variable
        assert updated_variable.tags == new_tags


class TestUpdateVariableByName:
    async def test_update_name(
        self,
        session,
        variable,
    ):
        new_name = "another_name"
        updated = await update_variable_by_name(
            session, variable.name, VariableUpdate(name=new_name)
        )
        assert updated
        updated_variable = await read_variable(session, variable.id)  # type: ignore
        assert updated_variable
        assert updated_variable.name == new_name

    async def test_update_value(
        self,
        session,
        variable,
    ):
        new_value = "another_name"
        updated = await update_variable_by_name(
            session, variable.name, VariableUpdate(value=new_value)
        )
        assert updated
        updated_variable = await read_variable(session, variable.id)  # type: ignore
        assert updated_variable
        assert updated_variable.value == new_value

    async def test_update_tags(
        self,
        session,
        variable,
    ):
        new_tags = ["new-tag-123"]
        updated = await update_variable_by_name(
            session, variable.name, VariableUpdate(tags=new_tags)
        )
        assert updated

        updated_variable = await read_variable(session, variable.id)  # type: ignore
        assert updated_variable
        assert updated_variable.tags == new_tags


class TestDeleteVariable:
    async def test_delete_variable(
        self,
        session,
        variable,
    ):
        deleted = await delete_variable(session, variable.id)  # type: ignore
        assert deleted

        model = await read_variable(session, variable.id)  # type: ignore
        assert not model

    async def test_variable_doesnt_exist(
        self,
        session,
        variable,
    ):
        deleted = await delete_variable(session, uuid.uuid4())
        assert not deleted


class TestDeleteVariableByName:
    async def test_delete_variable_by_name(
        self,
        session,
        variable,
    ):
        deleted = await delete_variable_by_name(session, variable.name)
        assert deleted

        model = await read_variable(session, variable.id)  # type: ignore
        assert not model

    async def test_variable_doesnt_exist(
        self,
        session,
        variable,
    ):
        deleted = await delete_variable_by_name(session, "doesntexist")
        assert not deleted
