# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import uuid

import pytest

import prefect
from prefect.utilities.graphql import compress
from prefect_server import api
from prefect_server.database import models


class TestCreateFlow:
    create_flow_mutation = """
        mutation($input: create_flow_input!) {
            create_flow(input: $input) {
                id
            }
        }
    """

    create_compressed_flow_mutation = """
        mutation($input: create_flow_from_compressed_string_input!) {
            create_flow_from_compressed_string(input: $input) {
                id
            }
        }
    """

    async def test_create_flow(self, run_query):
        serialized_flow = prefect.Flow(
            name="test", tasks=[prefect.Task(), prefect.Task()]
        ).serialize(build=False)

        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(input=dict(serialized_flow=serialized_flow)),
        )
        assert await models.Flow.exists(result.data.create_flow.id)

    async def test_create_flow_with_project(self, run_query):
        """
        Checks Cloud-compatible API
        """
        serialized_flow = prefect.Flow(
            name="test", tasks=[prefect.Task(), prefect.Task()]
        ).serialize(build=False)

        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=serialized_flow, project_id=str(uuid.uuid4())
                )
            ),
        )
        assert await models.Flow.exists(result.data.create_flow.id)

    @pytest.mark.parametrize("settings", [{"a": "b"}, {}])
    async def test_create_flow_copies_settings_between_versions(
        self, run_query, settings
    ):
        # create a flow
        serialized_flow = prefect.Flow(
            name="My Flow", tasks=[prefect.Task(), prefect.Task()]
        ).serialize(build=False)
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(input=dict(serialized_flow=serialized_flow)),
        )
        flow_id = result.data.create_flow.id
        # set an arbitrary setting
        await models.Flow.where(id=flow_id).update(set=dict(settings=settings))
        # grab the name and register a new version
        flow = await models.Flow.where(id=flow_id).first({"name", "version_group_id"})

        # create version two of this flow
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(input=dict(serialized_flow=serialized_flow)),
        )
        new_flow = await models.Flow.where(id=result.data.create_flow.id).first(
            {"version", "version_group_id", "settings"}
        )
        # confirm the flow we're inspecting is, in fact, a new version of the old flow
        assert new_flow.version_group_id == flow.version_group_id
        assert new_flow.version == 2
        # confirm the settings were persisted between versions of flows
        assert new_flow.settings == settings

    async def test_create_compressed_flow(self, run_query):
        serialized_flow = compress(prefect.Flow(name="test").serialize(build=False))
        result = await run_query(
            query=self.create_compressed_flow_mutation,
            variables=dict(input=dict(serialized_flow=serialized_flow)),
        )
        assert await models.Flow.exists(
            result.data.create_flow_from_compressed_string.id
        )
        flow = await models.Flow.where(
            id=result.data.create_flow_from_compressed_string.id
        ).first({"name"})
        assert flow.name == "test"

    async def test_create_compressed_flow_with_invalid_string(
        self, run_query,
    ):
        serialized_flow = "42"
        result = await run_query(
            query=self.create_compressed_flow_mutation,
            variables=dict(input=dict(serialized_flow=serialized_flow)),
        )
        assert result.errors
        assert "Unable to decompress" in result.errors[0]["message"]

    async def test_create_flow_with_version_group(self, run_query):
        serialized_flow = prefect.Flow(name="test").serialize(build=False)
        version_group_id = "hello"
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=serialized_flow, version_group_id=version_group_id,
                )
            ),
        )
        flow = await models.Flow.where(id=result.data.create_flow.id).first(
            selection_set={"version_group_id"}
        )
        assert flow.version_group_id == version_group_id

    async def test_create_flow_respects_core_version(self, run_query):
        serialized_flow = prefect.Flow(name="test").serialize(build=False)
        serialized_flow["environment"]["__version__"] = "0.7.0+g5892"
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(input=dict(serialized_flow=serialized_flow)),
        )
        flow = await models.Flow.where(id=result.data.create_flow.id).first(
            {"core_version"}
        )
        assert flow.core_version == "0.7.0+g5892"

    async def test_create_flow_with_description(self, run_query):
        serialized_flow = prefect.Flow(name="test").serialize(build=False)
        description = "test"
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(serialized_flow=serialized_flow, description=description,)
            ),
        )
        flow = await models.Flow.where(id=result.data.create_flow.id).first(
            {"description"}
        )
        assert flow.description == description

    async def test_create_flow_autodetects_version_group(
        self, run_query,
    ):
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                )
            ),
        )
        result2 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                )
            ),
        )

        # different name!
        result3 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test-different").serialize(
                        build=False
                    ),
                )
            ),
        )

        flow1 = await models.Flow.where(id=result1.data.create_flow.id).first(
            {"version_group_id"}
        )
        flow2 = await models.Flow.where(id=result2.data.create_flow.id).first(
            {"version_group_id"}
        )
        flow3 = await models.Flow.where(id=result3.data.create_flow.id).first(
            {"version_group_id"}
        )
        assert flow1.version_group_id == flow2.version_group_id
        assert flow1.version_group_id != flow3.version_group_id

    async def test_old_versions_are_automatically_archived(self, run_query):
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                )
            ),
        )
        result2 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                )
            ),
        )

        flow1 = await models.Flow.where(id=result1.data.create_flow.id).first(
            selection_set={"archived", "version_group_id"}
        )
        flow2 = await models.Flow.where(id=result2.data.create_flow.id).first(
            selection_set={"archived"}
        )

        assert flow1.archived
        assert not flow2.archived

        result3 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    version_group_id=flow1.version_group_id,
                )
            ),
        )

        flow1 = await models.Flow.where(id=result1.data.create_flow.id).first(
            selection_set={"archived", "version_group_id"}
        )
        flow2 = await models.Flow.where(id=result2.data.create_flow.id).first(
            selection_set={"archived"}
        )
        flow3 = await models.Flow.where(id=result3.data.create_flow.id).first(
            selection_set={"archived"}
        )
        assert flow1.archived
        assert flow2.archived
        assert not flow3.archived

    async def test_schedule_is_activated(self, run_query):
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(
                        name="test",
                        schedule=prefect.schedules.CronSchedule("0 0 * * *"),
                    ).serialize(build=False),
                )
            ),
        )
        schedule = await models.Schedule.where(
            {"flow_id": {"_eq": result1.data.create_flow.id}}
        ).first(selection_set={"active"})
        assert schedule.active

    async def test_schedule_is_not_activated_if_param_passed(
        self, run_query,
    ):
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(
                        name="test",
                        schedule=prefect.schedules.CronSchedule("0 0 * * *"),
                    ).serialize(build=False),
                    set_schedule_active=False,
                )
            ),
        )
        schedule = await models.Schedule.where(
            {"flow_id": {"_eq": result1.data.create_flow.id}}
        ).first(selection_set={"active"})
        assert not schedule.active

    async def test_create_flow_allows_setting_version_group_explicitly(
        self, run_query,
    ):
        version_group_id = str(uuid.uuid4())
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    version_group_id=version_group_id,
                )
            ),
        )
        result2 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test-different").serialize(
                        build=False
                    ),
                    version_group_id=version_group_id,
                )
            ),
        )
        flow1 = await models.Flow.where(id=result1.data.create_flow.id).first(
            {"version_group_id", "archived"}
        )
        flow2 = await models.Flow.where(id=result2.data.create_flow.id).first(
            {"version_group_id", "archived"}
        )
        assert flow1.version_group_id == flow2.version_group_id
        assert flow1.archived
        assert not flow2.archived


class TestDeleteFlow:
    mutation = """
        mutation($input: delete_flow_input!) {
            delete_flow(input: $input) {
                success
            }
        }
    """

    async def test_delete_flow(self, run_query, flow_id):
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(flow_id=flow_id))
        )
        assert not await models.Flow.exists(flow_id)


class Testarchive_flow:
    mutation = """
        mutation($input: archive_flow_input!) {
            archive_flow(input: $input) {
                success
            }
        }
    """

    async def test_archive_flow(self, run_query, flow_id):
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(flow_id=flow_id))
        )
        # confirm the payload is as expected
        assert result.data.archive_flow.success is True
        # confirm that success is reflected in the DB as well
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived

    async def test_archive_nonexistent_flow(self, run_query):
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(flow_id=str(uuid.uuid4())))
        )
        # confirm the payload is as expected
        assert result.data.archive_flow.success is False

    async def test_archive_flow_with_none_flow_id(self, run_query):
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(flow_id=None))
        )
        assert (
            "Expected non-nullable type UUID! not to be None."
            in result.errors[0].message
        )
