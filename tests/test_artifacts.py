import json
from typing import List

import pydantic
import pytest

from prefect import flow, task
from prefect.artifacts import (
    create_link_artifact,
    create_markdown_artifact,
    create_table_artifact,
)
from prefect.context import get_run_context
from prefect.server import schemas
from prefect.server.schemas.actions import ArtifactCreate


class TestCreateArtifacts:
    @pytest.fixture
    async def artifact(self):
        yield ArtifactCreate(
            key="voltaic",
            data=1,
            description="# This is a markdown description title",
        )

    async def test_create_and_read_link_artifact_succeeds(self, artifact, client):
        my_link = "prefect.io"
        artifact_id = await create_link_artifact(
            key=artifact.key,
            link=my_link,
            description=artifact.description,
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        result = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        assert result.data == f"[{my_link}]({my_link})"

    async def test_create_and_read_link_artifact_with_linktext_succeeds(
        self, artifact, client
    ):
        my_link = "prefect.io"
        link_text = "Prefect"
        artifact_id = await create_link_artifact(
            key=artifact.key,
            link=my_link,
            link_text=link_text,
            description=artifact.description,
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        result = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        assert result.data == f"[{link_text}]({my_link})"

    async def test_create_link_artifact_in_task_succeeds(self, client):
        @task
        def my_special_task():
            task_run_id = get_run_context().task_run.id
            artifact_id = create_link_artifact(
                key="task-link-artifact-3",
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

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_link_artifact = pydantic.parse_obj_as(schemas.core.Artifact, response.json())

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id == task_run_id

    async def test_create_link_artifact_in_flow_succeeds(self, client):
        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_link_artifact(
                key="task-link-artifact-4",
                link="google.com",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_link_artifact = pydantic.parse_obj_as(schemas.core.Artifact, response.json())

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id is None

    async def test_create_link_artifact_in_subflow_succeeds(self, client):
        @flow
        def my_subflow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id = create_link_artifact(
                key="task-link-artifact-5",
                link="google.com",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        @flow
        def my_flow():
            artifact_id, flow_run_id = my_subflow()

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_link_artifact = pydantic.parse_obj_as(schemas.core.Artifact, response.json())

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id is None

    async def test_create_link_artifact_using_map_succeeds(self):
        """
        Test that we can create a markdown artifact using map.
        """

        # An ode to prefect issue #5309.
        @task
        def add_ten(x):
            create_link_artifact(
                # TODO: uncomment this out once unique constraint is dropped on artifact key
                # key="new-markdown-artifact",
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

    async def test_create_and_read_markdown_artifact_succeeds(self, artifact, client):
        my_markdown = "# This is a markdown description title"
        artifact_id = await create_markdown_artifact(
            key=artifact.key,
            markdown=my_markdown,
            description=artifact.description,
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        result = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        assert result.data == my_markdown

    async def test_create_markdown_artifact_in_task_succeeds(self, client):
        @task
        def my_special_task():
            task_run_id = get_run_context().task_run.id
            artifact_id = create_markdown_artifact(
                key="task-link-artifact-3",
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

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_markdown_artifact = pydantic.parse_obj_as(
            schemas.core.Artifact, response.json()
        )

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id == task_run_id

    async def test_create_markdown_artifact_in_flow_succeeds(self, client):
        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_markdown_artifact(
                key="task-link-artifact-4",
                markdown="my markdown",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_markdown_artifact = pydantic.parse_obj_as(
            schemas.core.Artifact, response.json()
        )

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id is None

    async def test_create_markdown_artifact_in_subflow_succeeds(self, client):
        @flow
        def my_subflow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id = create_markdown_artifact(
                key="task-link-artifact-3",
                markdown="my markdown",
                description="my-artifact-description",
            )
            return artifact_id, flow_run_id

        @flow
        def my_flow():
            artifact_id, flow_run_id = my_subflow()

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_markdown_artifact = pydantic.parse_obj_as(
            schemas.core.Artifact, response.json()
        )

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id is None

    async def test_create_markdown_artifact_using_map_succeeds(self):
        """
        Test that we can create a markdown artifact using map.
        """

        @task
        def add_ten(x):
            create_markdown_artifact(
                # TODO: uncomment this out once unique constraint is dropped on artifact key
                # key="new-markdown-artifact",
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

    async def test_create_and_read_dict_of_list_table_artifact_succeeds(
        self, artifact, client
    ):
        my_table = {"a": [1, 3], "b": [2, 4]}

        artifact_id = await create_table_artifact(
            key=artifact.key,
            table=my_table,
            description=artifact.description,
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        result = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        result_data = json.loads(result.data)
        assert result_data == my_table

    async def test_create_and_read_list_of_dict_table_artifact_succeeds(
        self, artifact, client
    ):
        my_table = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

        artifact_id = await create_table_artifact(
            key=artifact.key,
            table=my_table,
            description=artifact.description,
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        result = pydantic.parse_obj_as(schemas.core.Artifact, response.json())

        result_data = json.loads(result.data)
        assert result_data == my_table

    async def test_create_and_read_list_of_list_table_artifact_succeeds(
        self, artifact, client
    ):
        my_table = [[1, 2], [None, 4]]

        artifact_id = await create_table_artifact(
            key=artifact.key,
            table=my_table,
            description=artifact.description,
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        result = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        result_data = json.loads(result.data)
        assert result_data == my_table

    async def test_create_table_artifact_in_task_succeeds(self, client):
        @task
        def my_special_task():
            my_table = {"a": [1, 3], "b": [2, 4]}
            task_run_id = get_run_context().task_run.id
            artifact_id = create_table_artifact(
                key="task-link-artifact-3",
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

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_table_artifact = pydantic.parse_obj_as(
            schemas.core.Artifact, response.json()
        )

        assert my_table_artifact.flow_run_id == flow_run_id
        assert my_table_artifact.task_run_id == task_run_id
        result_data = json.loads(my_table_artifact.data)
        assert result_data == {"a": [1, 3], "b": [2, 4]}

    async def test_create_table_artifact_in_flow_succeeds(self, client):
        @flow
        def my_flow():
            my_table = {"a": [1, 3], "b": [2, 4]}
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_table_artifact(
                key="task-link-artifact-4",
                table=my_table,
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_table_artifact = pydantic.parse_obj_as(
            schemas.core.Artifact, response.json()
        )

        assert my_table_artifact.flow_run_id == flow_run_id
        assert my_table_artifact.task_run_id is None
        result_data = json.loads(my_table_artifact.data)
        assert result_data == {"a": [1, 3], "b": [2, 4]}

    async def test_create_table_artifact_in_subflow_succeeds(self, client):
        @flow
        def my_subflow():
            my_table = {"a": [1, 3], "b": [2, 4]}
            flow_run_id = get_run_context().flow_run.id
            artifact_id = create_table_artifact(
                key="task-link-artifact-3",
                table=my_table,
                description="my-artifact-description",
            )
            return artifact_id, flow_run_id

        @flow
        def my_flow():
            artifact_id, flow_run_id = my_subflow()

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_table_artifact = pydantic.parse_obj_as(
            schemas.core.Artifact, response.json()
        )

        assert my_table_artifact.flow_run_id == flow_run_id
        result_data = json.loads(my_table_artifact.data)
        assert result_data == {"a": [1, 3], "b": [2, 4]}
        assert my_table_artifact.task_run_id is None

    async def test_create_table_artifact_using_map_succeeds(self):
        """
        Test that we can create a table artifact using map.
        An ode to prefect issue
        """

        @task
        def add_ten(x):
            my_table = {"a": [1, 3], "b": [2, 4]}
            create_table_artifact(
                # TODO: uncomment this out once unique constraint is dropped on artifact key
                # key="task-link-artifact-3",
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

    async def test_create_dict_table_artifact_with_none_succeeds(self):
        my_table = {"a": [1, 3], "b": [2, None]}

        await create_table_artifact(
            key="swiss-table",
            table=my_table,
            description="my-artifact-description",
        )

    async def test_create_dict_table_artifact_with_nan_succeeds(self, client):
        my_table = {"a": [1, 3], "b": [2, float("nan")]}

        artifact_id = await create_table_artifact(
            key="swiss-table",
            table=my_table,
            description="my-artifact-description",
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        my_artifact = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        my_data = json.loads(my_artifact.data)
        assert my_data == {"a": [1, 3], "b": [2, None]}

    async def test_create_list_table_artifact_with_none_succeeds(self):
        my_table = [
            {"a": 1, "b": 2},
            {"a": 3, "b": None},
        ]

        await create_table_artifact(
            key="swiss-table",
            table=my_table,
            description="my-artifact-description",
        )

    async def test_create_list_table_artifact_with_nan_succeeds(self, client):
        my_table = [
            {"a": 1, "b": 2},
            {"a": 3, "b": float("nan")},
        ]

        artifact_id = await create_table_artifact(
            key="swiss-table",
            table=my_table,
            description="my-artifact-description",
        )

        response = await client.get(f"/artifacts/{artifact_id}")
        my_artifact = pydantic.parse_obj_as(schemas.core.Artifact, response.json())
        my_data = json.loads(my_artifact.data)
        assert my_data == [
            {"a": 1, "b": 2},
            {"a": 3, "b": None},
        ]
