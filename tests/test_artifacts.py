import json
from typing import List

import pytest

from prefect import flow, task
from prefect.artifacts import (
    create_image_artifact,
    create_link_artifact,
    create_markdown_artifact,
    create_progress_artifact,
    create_table_artifact,
    update_progress_artifact,
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

    async def test_create_and_read_link_artifact_with_linktext_succeeds(
        self, artifact, client
    ):
        my_link = "prefect.io"
        link_text = "Prefect"

        @flow
        async def my_flow():
            return await create_link_artifact(
                key=artifact.key,
                link=my_link,
                link_text=link_text,
                description=artifact.description,
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        result = schemas.core.Artifact.model_validate(response.json())
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
        my_link_artifact = schemas.core.Artifact.model_validate(response.json())

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
        my_link_artifact = schemas.core.Artifact.model_validate(response.json())

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
        my_link_artifact = schemas.core.Artifact.model_validate(response.json())

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
        my_markdown_artifact = schemas.core.Artifact.model_validate(response.json())

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
        my_markdown_artifact = schemas.core.Artifact.model_validate(response.json())

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
        my_markdown_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id is None

    async def test_create_markdown_artifact_using_map_succeeds(self):
        """
        Test that we can create a markdown artifact using map.
        """

        @task
        def add_ten(x):
            create_markdown_artifact(
                key="new-markdown-artifact",
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

        @flow
        async def my_flow():
            return await create_table_artifact(
                key=artifact.key,
                table=my_table,
                description=artifact.description,
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        result = schemas.core.Artifact.model_validate(response.json())
        result_data = json.loads(result.data)
        assert result_data == my_table

    async def test_create_and_read_list_of_dict_table_artifact_succeeds(
        self, artifact, client
    ):
        my_table = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

        @flow
        async def my_flow():
            return await create_table_artifact(
                key=artifact.key,
                table=my_table,
                description=artifact.description,
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        result = schemas.core.Artifact.model_validate(response.json())

        result_data = json.loads(result.data)
        assert result_data == my_table

    async def test_create_and_read_list_of_list_table_artifact_succeeds(
        self, artifact, client
    ):
        my_table = [[1, 2], [None, 4]]

        @flow
        async def my_flow():
            return await create_table_artifact(
                key=artifact.key,
                table=my_table,
                description=artifact.description,
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        result = schemas.core.Artifact.model_validate(response.json())
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
        my_table_artifact = schemas.core.Artifact.model_validate(response.json())

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
        my_table_artifact = schemas.core.Artifact.model_validate(response.json())

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
        my_table_artifact = schemas.core.Artifact.model_validate(response.json())

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

        @flow
        async def my_flow():
            return await create_table_artifact(
                key="swiss-table",
                table=my_table,
                description="my-artifact-description",
            )

        await my_flow()

    async def test_create_dict_table_artifact_with_nan_succeeds(self, client):
        my_table = {"a": [1, 3], "b": [2, float("nan")]}

        @flow
        async def my_flow():
            return await create_table_artifact(
                key="swiss-table",
                table=my_table,
                description="my-artifact-description",
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        my_artifact = schemas.core.Artifact.model_validate(response.json())
        my_data = json.loads(my_artifact.data)
        assert my_data == {"a": [1, 3], "b": [2, None]}

    async def test_create_list_table_artifact_with_none_succeeds(self):
        my_table = [
            {"a": 1, "b": 2},
            {"a": 3, "b": None},
        ]

        @flow
        async def my_flow():
            await create_table_artifact(
                key="swiss-table",
                table=my_table,
                description="my-artifact-description",
            )

        await my_flow()

    async def test_create_list_table_artifact_with_nan_succeeds(self, client):
        my_table = [
            {"a": 1, "b": 2},
            {"a": 3, "b": float("nan")},
        ]

        @flow
        async def my_flow():
            return await create_table_artifact(
                key="swiss-table",
                table=my_table,
                description="my-artifact-description",
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        my_artifact = schemas.core.Artifact.model_validate(response.json())
        my_data = json.loads(my_artifact.data)
        assert my_data == [
            {"a": 1, "b": 2},
            {"a": 3, "b": None},
        ]

    async def test_create_progress_artifact_without_key(self, client):
        progress = 0.0

        @flow
        async def my_flow():
            return await create_progress_artifact(
                progress, description="my-description"
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        my_artifact = schemas.core.Artifact.model_validate(response.json())
        assert my_artifact.data == progress
        assert my_artifact.type == "progress"
        assert my_artifact.description == "my-description"

    async def test_create_progress_artifact_with_key(self, client):
        progress = 0.0

        @flow
        async def my_flow():
            return await create_progress_artifact(
                progress, key="progress-artifact", description="my-description"
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        my_artifact = schemas.core.Artifact.model_validate(response.json())
        assert my_artifact.data == progress
        assert my_artifact.type == "progress"
        assert my_artifact.key == "progress-artifact"
        assert my_artifact.description == "my-description"

    async def test_create_progress_artifact_in_task_succeeds(self, client):
        @task
        def my_task():
            task_run_id = get_run_context().task_run.id
            artifact_id = create_progress_artifact(
                key="task-link-artifact-3",
                progress=0.0,
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id, task_run_id = my_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id == task_run_id
        assert my_progress_artifact.data == 0.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"

    async def test_create_progess_artifact_in_flow_succeeds(self, client):
        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_progress_artifact(
                key="task-link-artifact-4",
                progress=0.0,
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id is None
        assert my_progress_artifact.data == 0.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"

    async def test_create_image_artifact_in_task_succeeds(self, client):
        @task
        def my_task():
            task_run_id = get_run_context().task_run.id
            artifact_id = create_image_artifact(
                image_url="https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
                key="task-link-artifact-3",
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id, task_run_id = my_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_image_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_image_artifact.flow_run_id == flow_run_id
        assert my_image_artifact.task_run_id == task_run_id
        assert (
            my_image_artifact.data
            == "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
        )
        assert my_image_artifact.type == "image"
        assert my_image_artifact.description == "my-artifact-description"

    async def test_create_image_artifact_in_flow_succeeds(self, client):
        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_image_artifact(
                image_url="https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
                key="task-link-artifact-4",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_image_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_image_artifact.flow_run_id == flow_run_id
        assert my_image_artifact.task_run_id is None
        assert (
            my_image_artifact.data
            == "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
        )
        assert my_image_artifact.type == "image"
        assert my_image_artifact.description == "my-artifact-description"

    async def test_creating_artifact_outside_of_flow_run_context_warns(self):
        with pytest.warns(FutureWarning):
            await create_link_artifact("https://www.google.com", "Google")


class TestUpdateArtifacts:
    async def test_update_progress_artifact_updates_progress(self, client):
        progress = 0.0

        @flow
        async def my_flow():
            artifact_id = await create_progress_artifact(progress)

            response = await client.get(f"/artifacts/{artifact_id}")
            my_artifact = schemas.core.Artifact.model_validate(response.json())
            assert my_artifact.data == progress
            assert my_artifact.type == "progress"

            new_progress = 50.0
            await update_progress_artifact(artifact_id, new_progress)
            response = await client.get(f"/artifacts/{artifact_id}")
            my_artifact = schemas.core.Artifact.model_validate(response.json())
            assert my_artifact.data == new_progress

        await my_flow()

    async def test_update_progress_artifact_in_task(self, client):
        @task
        def my_task():
            task_run_id = get_run_context().task_run.id
            artifact_id = create_progress_artifact(
                key="task-link-artifact-3",
                progress=0.0,
                description="my-artifact-description",
            )
            update_progress_artifact(artifact_id, 50.0)
            return artifact_id, task_run_id

        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id
            artifact_id, task_run_id = my_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id == task_run_id
        assert my_progress_artifact.data == 50.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"

    async def test_update_progress_artifact_in_flow(self, client):
        @flow
        def my_flow():
            flow_run_id = get_run_context().flow_run.id

            artifact_id = create_progress_artifact(
                key="task-link-artifact-4",
                progress=0.0,
                description="my-artifact-description",
            )
            update_progress_artifact(artifact_id, 50.0)

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id is None
        assert my_progress_artifact.data == 50.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"
