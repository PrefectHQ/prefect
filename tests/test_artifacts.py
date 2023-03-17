from typing import List

import pytest

from prefect import flow, task
from prefect.artifacts import (
    create_link,
    create_markdown,
    create_table,
    read_link,
    read_markdown,
    read_table,
)
from prefect.context import get_run_context
from prefect.server.schemas.actions import ArtifactCreate
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS


class TestCreateArtifacts:
    @pytest.fixture(autouse=True)
    def auto_enable_artifacts(self, enable_artifacts):
        """
        Enable artifacts for testing
        """
        assert PREFECT_EXPERIMENTAL_ENABLE_ARTIFACTS.value() is True

    @pytest.fixture
    async def artifact(self):
        yield ArtifactCreate(
            key="voltaic",
            data=1,
            description="# This is a markdown description title",
            metadata_={"data": "opens many doors"},
        )

    async def test_create_and_read_link_artifact_succeeds(self, artifact):
        my_link = "prefect.io"
        artifact_id = await create_link(
            name=artifact.key,
            link=my_link,
            description=artifact.description,
            metadata=artifact.metadata_,
        )

        result = await read_link(artifact_id)
        assert result.data == my_link

    async def test_create_link_artifact_in_task_succeeds(self, orion_client):
        @task
        def my_special_task():
            task_run_id = get_run_context().task_run.id
            artifact_id = create_link(
                name="task-link-artifact-3",
                link="google.com",
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id, task_run_id = my_special_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        my_link_artifact = await read_link(my_artifact_id)

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id == task_run_id

    async def test_create_link_artifact_in_flow_succeeds(self, orion_client):
        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_link(
                name="task-link-artifact-4",
                link="google.com",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        my_link_artifact = await read_link(my_artifact_id)

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id is None

    async def test_create_link_artifact_in_subflow_succeeds(self, orion_client):
        @flow
        def my_subflow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id = create_link(
                name="task-link-artifact-5",
                link="google.com",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        @flow
        def my_flow():
            artifact_id, flow_run_id = my_subflow()

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        my_link_artifact = await read_link(my_artifact_id)

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id is None

    async def test_create_link_artifact_using_map_succeeds(self, orion_client):
        """
        Test that we can create a markdown artifact using map.
        """

        # An ode to prefect issue #5309.
        @task
        def add_ten(x):
            create_link(
                # TODO: uncomment this out once unique constraint is dropped on artifact name
                # name="new-markdown-artifact",
                link="s3://my-bucket/my-file",
                description="my-artifact-description",
            )
            return x + 10

        @flow
        def simple_map(nums: List[int]):
            big_nums = add_ten.map(nums)
            return [big_num.result() for big_num in big_nums]

        my_big_nums = simple_map([1, 2, 3])
        assert my_big_nums == [11, 12, 13]

    async def test_create_and_read_markdown_artifact_succeeds(self, artifact):
        my_markdown = "# This is a markdown description title"
        artifact_id = await create_markdown(
            name=artifact.key,
            markdown=my_markdown,
            description=artifact.description,
            metadata=artifact.metadata_,
        )

        result = await read_markdown(artifact_id)
        assert result.data == my_markdown

    async def test_create_markdown_artifact_in_task_succeeds(self, orion_client):
        @task
        def my_special_task():
            task_run_id = get_run_context().task_run.id
            artifact_id = create_markdown(
                name="task-link-artifact-3",
                markdown="my markdown",
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id, task_run_id = my_special_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        my_markdown_artifact = await read_markdown(my_artifact_id)

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id == task_run_id

    async def test_create_markdown_artifact_in_flow_succeeds(self, orion_client):
        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_markdown(
                name="task-link-artifact-4",
                markdown="my markdown",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        my_markdown_artifact = await read_markdown(my_artifact_id)

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id is None

    async def test_create_markdown_artifact_in_subflow_succeeds(self, orion_client):
        @flow
        def my_subflow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id = create_markdown(
                name="task-link-artifact-3",
                markdown="my markdown",
                description="my-artifact-description",
            )
            return artifact_id, flow_run_id

        @flow
        def my_flow():
            artifact_id, flow_run_id = my_subflow()

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        my_markdown_artifact = await read_markdown(my_artifact_id)

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id is None

    async def test_create_markdown_artifact_using_map_succeeds(self, orion_client):
        """
        Test that we can create a markdown artifact using map.
        """

        @task
        def add_ten(x):
            create_markdown(
                # TODO: uncomment this out once unique constraint is dropped on artifact name
                # name="new-markdown-artifact",
                markdown="my markdown",
                description="my-artifact-description",
            )
            return x + 10

        @flow
        def simple_map(nums: List[int]):
            big_nums = add_ten.map(nums)
            return [big_num.result() for big_num in big_nums]

        my_big_nums = simple_map([1, 2, 3])
        assert my_big_nums == [11, 12, 13]

    async def test_create_and_read_table_artifact_succeeds(self, artifact):
        my_table = {"a": [1, 3], "b": [2, 4]}

        artifact_id = await create_table(
            name=artifact.key,
            table=my_table,
            description=artifact.description,
            metadata=artifact.metadata_,
        )

        result = await read_table(artifact_id)
        assert result.data == my_table

    async def test_create_table_artifact_in_task_succeeds(self, orion_client):
        @task
        def my_special_task():
            my_table = {"a": [1, 3], "b": [2, 4]}
            task_run_id = get_run_context().task_run.id
            artifact_id = create_table(
                name="task-link-artifact-3",
                table=my_table,
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id, task_run_id = my_special_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        my_table_artifact = await read_table(my_artifact_id)

        assert my_table_artifact.flow_run_id == flow_run_id
        assert my_table_artifact.task_run_id == task_run_id
        assert my_table_artifact.data == {"a": [1, 3], "b": [2, 4]}

    async def test_create_table_artifact_in_flow_succeeds(self, orion_client):
        @flow
        def my_flow():
            my_table = {"a": [1, 3], "b": [2, 4]}
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_table(
                name="task-link-artifact-4",
                table=my_table,
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        my_table_artifact = await read_table(my_artifact_id)

        assert my_table_artifact.flow_run_id == flow_run_id
        assert my_table_artifact.task_run_id is None
        assert my_table_artifact.data == {"a": [1, 3], "b": [2, 4]}

    async def test_create_table_artifact_in_subflow_succeeds(self, orion_client):
        @flow
        def my_subflow():
            my_table = {"a": [1, 3], "b": [2, 4]}
            flow_run_id = get_run_context().flow_run.id
            artifact_id = create_table(
                name="task-link-artifact-3",
                table=my_table,
                description="my-artifact-description",
            )
            return artifact_id, flow_run_id

        @flow
        def my_flow():
            artifact_id, flow_run_id = my_subflow()

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        my_table_artifact = await read_table(my_artifact_id)

        assert my_table_artifact.flow_run_id == flow_run_id
        assert my_table_artifact.data == {"a": [1, 3], "b": [2, 4]}
        assert my_table_artifact.task_run_id is None

    async def test_create_table_artifact_using_map_succeeds(self, orion_client):
        """
        Test that we can create a table artifact using map.
        An ode to prefect issue
        """

        @task
        def add_ten(x):
            my_table = {"a": [1, 3], "b": [2, 4]}
            create_table(
                # TODO: uncomment this out once unique constraint is dropped on artifact name
                # name="task-link-artifact-3",
                table=my_table,
                description="my-artifact-description",
            )
            return x + 10

        @flow
        def simple_map(nums: List[int]):
            big_nums = add_ten.map(nums)
            return [big_num.result() for big_num in big_nums]

        my_big_nums = simple_map([1, 2, 3])
        assert my_big_nums == [11, 12, 13]
