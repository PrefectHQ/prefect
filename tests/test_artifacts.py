import asyncio
import json
from typing import cast
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from prefect import flow, task
from prefect.artifacts import (
    Artifact,
    acreate_link_artifact,
    acreate_progress_artifact,
    acreate_table_artifact,
    aupdate_progress_artifact,
    create_image_artifact,
    create_link_artifact,
    create_markdown_artifact,
    create_progress_artifact,
    create_table_artifact,
    update_progress_artifact,
)
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import Artifact as ArtifactResponse
from prefect.context import FlowRunContext, TaskRunContext, get_run_context
from prefect.server import schemas
from prefect.server.schemas.actions import ArtifactCreate


class TestCreateArtifacts:
    @pytest.fixture
    def artifact(self):
        yield ArtifactCreate(
            key="voltaic",
            data=1,
            description="# This is a markdown description title",
        )

    async def test_create_and_read_link_artifact_with_linktext_succeeds(
        self, artifact: ArtifactCreate, client: httpx.AsyncClient
    ):
        my_link = "prefect.io"
        link_text = "Prefect"

        @flow
        async def my_flow():
            return await acreate_link_artifact(
                key=artifact.key,
                link=my_link,
                link_text=link_text,
                description=artifact.description,
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 200
        result = schemas.core.Artifact.model_validate(response.json())
        assert result.data == f"[{link_text}]({my_link})"

    async def test_create_link_artifact_in_task_succeeds(
        self, client: httpx.AsyncClient
    ):
        @task
        def my_special_task():
            run_context = get_run_context()
            assert isinstance(run_context, TaskRunContext)
            task_run_id = run_context.task_run.id
            artifact_id = create_link_artifact(
                key="task-link-artifact-3",
                link="google.com",
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id
            artifact_id, task_run_id = my_special_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_link_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id == task_run_id

    async def test_create_link_artifact_in_flow_succeeds(
        self, client: httpx.AsyncClient
    ):
        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id = create_link_artifact(
                key="task-link-artifact-4",
                link="google.com",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_link_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id is None

    async def test_create_link_artifact_in_subflow_succeeds(
        self, client: httpx.AsyncClient
    ):
        @flow
        def my_subflow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id
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
        assert response.status_code == 200
        my_link_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_link_artifact.flow_run_id == flow_run_id
        assert my_link_artifact.task_run_id is None

    async def test_create_link_artifact_using_map_succeeds(self):
        """
        Test that we can create a markdown artifact using map.
        """

        # An ode to prefect issue #5309.
        @task
        def add_ten(x: int) -> int:
            create_link_artifact(
                # TODO: uncomment this out once unique constraint is dropped on artifact key
                # key="new-markdown-artifact",
                link="s3://my-bucket/my-file",
                description="my-artifact-description",
            )
            return x + 10

        @flow
        def simple_map(nums: list[int]):
            big_nums = add_ten.map(nums)
            return [big_num.result() for big_num in big_nums]

        my_big_nums = simple_map([1, 2, 3])
        assert my_big_nums == [11, 12, 13]

    async def test_create_markdown_artifact_in_task_succeeds(
        self, client: httpx.AsyncClient
    ):
        @task
        def my_special_task():
            run_context = get_run_context()
            assert isinstance(run_context, TaskRunContext)
            task_run_id = run_context.task_run.id
            artifact_id = create_markdown_artifact(
                key="task-link-artifact-3",
                markdown="my markdown",
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id
            artifact_id, task_run_id = my_special_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_markdown_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id == task_run_id

    async def test_create_markdown_artifact_in_flow_succeeds(
        self, client: httpx.AsyncClient
    ):
        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id = create_markdown_artifact(
                key="task-link-artifact-4",
                markdown="my markdown",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_markdown_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id is None

    async def test_create_markdown_artifact_in_subflow_succeeds(
        self, client: httpx.AsyncClient
    ):
        @flow
        def my_subflow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id
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
        assert response.status_code == 200
        my_markdown_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_markdown_artifact.flow_run_id == flow_run_id
        assert my_markdown_artifact.task_run_id is None

    async def test_create_markdown_artifact_using_map_succeeds(self):
        """
        Test that we can create a markdown artifact using map.
        """

        @task
        def add_ten(x: int) -> int:
            create_markdown_artifact(
                key="new-markdown-artifact",
                markdown="my markdown",
                description="my-artifact-description",
            )
            return x + 10

        @flow
        def simple_map(nums: list[int]) -> list[int]:
            big_nums = add_ten.map(nums)
            return [big_num.result() for big_num in big_nums]

        my_big_nums = simple_map([1, 2, 3])
        assert my_big_nums == [11, 12, 13]

    async def test_create_and_read_dict_of_list_table_artifact_succeeds(
        self, artifact: ArtifactCreate, client: httpx.AsyncClient
    ):
        my_table = {"a": [1, 3], "b": [2, 4]}

        @flow
        async def my_flow():
            return await acreate_table_artifact(
                key=artifact.key,
                table=my_table,
                description=artifact.description,
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 200
        result = schemas.core.Artifact.model_validate(response.json())
        assert isinstance(result.data, str)
        result_data = json.loads(result.data)
        assert result_data == my_table

    async def test_create_and_read_list_of_dict_table_artifact_succeeds(
        self, artifact: ArtifactCreate, client: httpx.AsyncClient
    ):
        my_table = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

        @flow
        async def my_flow():
            return await acreate_table_artifact(
                key=artifact.key,
                table=my_table,
                description=artifact.description,
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 200
        result = schemas.core.Artifact.model_validate(response.json())

        assert isinstance(result.data, str)
        result_data = json.loads(result.data)
        assert result_data == my_table

    async def test_create_and_read_list_of_list_table_artifact_succeeds(
        self, artifact: ArtifactCreate, client: httpx.AsyncClient
    ):
        my_table = [[1, 2], [None, 4]]

        @flow
        async def my_flow():
            return await acreate_table_artifact(
                key=artifact.key,
                table=my_table,
                description=artifact.description,
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 200
        result = schemas.core.Artifact.model_validate(response.json())
        assert isinstance(result.data, str)
        result_data = json.loads(result.data)
        assert result_data == my_table

    async def test_create_table_artifact_in_task_succeeds(
        self, client: httpx.AsyncClient
    ):
        @task
        def my_special_task():
            my_table = {"a": [1, 3], "b": [2, 4]}
            run_context = get_run_context()
            assert isinstance(run_context, TaskRunContext)
            task_run_id = run_context.task_run.id
            artifact_id = create_table_artifact(
                key="task-link-artifact-3",
                table=my_table,
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id
            artifact_id, task_run_id = my_special_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        my_table_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_table_artifact.flow_run_id == flow_run_id
        assert my_table_artifact.task_run_id == task_run_id
        assert isinstance(my_table_artifact.data, str)
        result_data = json.loads(my_table_artifact.data)
        assert result_data == {"a": [1, 3], "b": [2, 4]}

    async def test_create_table_artifact_in_flow_succeeds(
        self, client: httpx.AsyncClient
    ):
        @flow
        def my_flow():
            my_table = {"a": [1, 3], "b": [2, 4]}
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id = create_table_artifact(
                key="task-link-artifact-4",
                table=my_table,
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_table_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_table_artifact.flow_run_id == flow_run_id
        assert my_table_artifact.task_run_id is None
        assert isinstance(my_table_artifact.data, str)
        result_data = json.loads(my_table_artifact.data)
        assert result_data == {"a": [1, 3], "b": [2, 4]}

    async def test_create_table_artifact_in_subflow_succeeds(
        self, client: httpx.AsyncClient
    ):
        @flow
        def my_subflow():
            my_table = {"a": [1, 3], "b": [2, 4]}
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id
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
        assert response.status_code == 200
        my_table_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_table_artifact.flow_run_id == flow_run_id
        assert isinstance(my_table_artifact.data, str)
        result_data = json.loads(my_table_artifact.data)
        assert result_data == {"a": [1, 3], "b": [2, 4]}
        assert my_table_artifact.task_run_id is None

    async def test_create_table_artifact_using_map_succeeds(self):
        """
        Test that we can create a table artifact using map.
        An ode to prefect issue
        """

        @task
        def add_ten(x: int) -> int:
            my_table = {"a": [1, 3], "b": [2, 4]}
            create_table_artifact(
                # TODO: uncomment this out once unique constraint is dropped on artifact key
                # key="task-link-artifact-3",
                table=my_table,
                description="my-artifact-description",
            )
            return x + 10

        @flow
        def simple_map(nums: list[int]):
            big_nums = add_ten.map(nums)
            return [big_num.result() for big_num in big_nums]

        my_big_nums = simple_map([1, 2, 3])
        assert my_big_nums == [11, 12, 13]

    async def test_create_dict_table_artifact_with_none_succeeds(self):
        my_table = {"a": [1, 3], "b": [2, None]}

        @flow
        def my_flow():
            return create_table_artifact(
                key="swiss-table",
                table=my_table,
                description="my-artifact-description",
            )

        my_flow()

    async def test_create_dict_table_artifact_with_nan_succeeds(
        self, client: httpx.AsyncClient
    ):
        my_table = {"a": [1, 3], "b": [2, float("nan")]}

        @flow
        async def my_flow():
            return await acreate_table_artifact(
                key="swiss-table",
                table=my_table,
                description="my-artifact-description",
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 200
        my_artifact = schemas.core.Artifact.model_validate(response.json())
        assert isinstance(my_artifact.data, str)
        my_data = json.loads(my_artifact.data)
        assert my_data == {"a": [1, 3], "b": [2, None]}

    async def test_create_list_table_artifact_with_none_succeeds(self):
        my_table = [
            {"a": 1, "b": 2},
            {"a": 3, "b": None},
        ]

        @flow
        async def my_flow():
            await acreate_table_artifact(
                key="swiss-table",
                table=my_table,
                description="my-artifact-description",
            )

        await my_flow()

    async def test_create_list_table_artifact_with_nan_succeeds(
        self, client: httpx.AsyncClient
    ):
        my_table = [
            {"a": 1, "b": 2},
            {"a": 3, "b": float("nan")},
        ]

        @flow
        async def my_flow():
            return await acreate_table_artifact(
                key="swiss-table",
                table=my_table,
                description="my-artifact-description",
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 200
        my_artifact = schemas.core.Artifact.model_validate(response.json())
        assert isinstance(my_artifact.data, str)
        my_data = json.loads(my_artifact.data)
        assert my_data == [
            {"a": 1, "b": 2},
            {"a": 3, "b": None},
        ]

    async def test_create_progress_artifact_without_key(
        self, client: httpx.AsyncClient
    ):
        progress = 0.0

        @flow
        async def my_flow():
            return await acreate_progress_artifact(
                progress, description="my-description"
            )

        artifact_id = await my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 200
        my_artifact = schemas.core.Artifact.model_validate(response.json())
        assert my_artifact.data == progress
        assert my_artifact.type == "progress"
        assert my_artifact.description == "my-description"

    async def test_create_progress_artifact_with_key(self, client: httpx.AsyncClient):
        progress = 0.0

        @flow
        def my_flow():
            return create_progress_artifact(
                progress, key="progress-artifact", description="my-description"
            )

        artifact_id = my_flow()
        response = await client.get(f"/artifacts/{artifact_id}")
        assert response.status_code == 200
        my_artifact = schemas.core.Artifact.model_validate(response.json())
        assert my_artifact.data == progress
        assert my_artifact.type == "progress"
        assert my_artifact.key == "progress-artifact"
        assert my_artifact.description == "my-description"

    async def test_create_progress_artifact_in_task_succeeds(
        self, client: httpx.AsyncClient
    ):
        @task
        def my_task():
            run_context = get_run_context()
            assert isinstance(run_context, TaskRunContext)
            assert run_context.task_run is not None
            task_run_id = run_context.task_run.id
            artifact_id = create_progress_artifact(
                key="task-link-artifact-3",
                progress=0.0,
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id
            artifact_id, task_run_id = my_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id == task_run_id
        assert my_progress_artifact.data == 0.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"

    async def test_create_progess_artifact_in_flow_succeeds(
        self, client: httpx.AsyncClient
    ):
        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id = create_progress_artifact(
                key="task-link-artifact-4",
                progress=0.0,
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id is None
        assert my_progress_artifact.data == 0.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"

    async def test_create_image_artifact_in_task_succeeds(
        self, client: httpx.AsyncClient
    ):
        @task
        def my_task():
            run_context = get_run_context()
            assert isinstance(run_context, TaskRunContext)
            assert run_context.task_run is not None
            task_run_id = run_context.task_run.id
            artifact_id = create_image_artifact(
                image_url="https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
                key="task-link-artifact-3",
                description="my-artifact-description",
            )
            return artifact_id, task_run_id

        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id
            artifact_id, task_run_id = my_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_image_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_image_artifact.flow_run_id == flow_run_id
        assert my_image_artifact.task_run_id == task_run_id
        assert (
            my_image_artifact.data
            == "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
        )
        assert my_image_artifact.type == "image"
        assert my_image_artifact.description == "my-artifact-description"

    async def test_create_image_artifact_in_flow_succeeds(
        self, client: httpx.AsyncClient
    ):
        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id = create_image_artifact(
                image_url="https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
                key="task-link-artifact-4",
                description="my-artifact-description",
            )

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
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
            create_link_artifact("https://www.google.com", "Google", _sync=True)  # pyright: ignore[reportCallIssue]

        with pytest.warns(FutureWarning):
            await acreate_link_artifact("https://www.google.com", "Google")


class TestUpdateArtifacts:
    async def test_update_progress_artifact_updates_progress_async(
        self, client: httpx.AsyncClient
    ):
        progress = 0.0

        @flow
        async def my_flow():
            artifact_id = await acreate_progress_artifact(progress)
            assert isinstance(artifact_id, UUID)

            response = await client.get(f"/artifacts/{artifact_id}")
            my_artifact = schemas.core.Artifact.model_validate(response.json())
            assert my_artifact.data == progress
            assert my_artifact.type == "progress"

            new_progress = 50.0
            await aupdate_progress_artifact(artifact_id, new_progress)
            response = await client.get(f"/artifacts/{artifact_id}")
            assert response.status_code == 200
            my_artifact = schemas.core.Artifact.model_validate(response.json())
            assert my_artifact.data == new_progress

        await my_flow()

    def test_update_progress_artifact_updates_progress_sync(
        self, sync_client: TestClient
    ):
        progress = 0.0

        @flow
        def my_flow():
            artifact_id = create_progress_artifact(progress)
            assert isinstance(artifact_id, UUID)

            response = sync_client.get(f"/artifacts/{artifact_id}")
            my_artifact = schemas.core.Artifact.model_validate(response.json())
            assert my_artifact.data == progress
            assert my_artifact.type == "progress"

            new_progress = 50.0
            update_progress_artifact(artifact_id, new_progress)
            response = sync_client.get(f"/artifacts/{artifact_id}")
            assert response.status_code == 200
            my_artifact = schemas.core.Artifact.model_validate(response.json())
            assert my_artifact.data == new_progress

        my_flow()

    async def test_update_progress_artifact_in_task(self, client: httpx.AsyncClient):
        @task
        def my_task():
            run_context = get_run_context()
            assert isinstance(run_context, TaskRunContext)
            assert run_context.task_run is not None
            task_run_id = run_context.task_run.id

            artifact_id = create_progress_artifact(
                key="task-link-artifact-3",
                progress=0.0,
                description="my-artifact-description",
            )
            assert isinstance(artifact_id, UUID)
            update_progress_artifact(artifact_id, 50.0)
            return artifact_id, task_run_id

        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id, task_run_id = my_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id == task_run_id
        assert my_progress_artifact.data == 50.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"

    async def test_update_progress_artifact_in_async_task(
        self, client: httpx.AsyncClient
    ):
        @task
        async def my_task():
            run_context = get_run_context()
            assert isinstance(run_context, TaskRunContext)
            assert run_context.task_run is not None
            task_run_id = run_context.task_run.id

            artifact_id_coro = create_progress_artifact(
                key="task-link-artifact-3",
                progress=0.0,
                description="my-artifact-description",
            )
            assert asyncio.iscoroutine(artifact_id_coro)
            artifact_id = await artifact_id_coro
            assert isinstance(artifact_id, UUID)
            update_coro = update_progress_artifact(artifact_id, 50.0)
            assert asyncio.iscoroutine(update_coro)
            await update_coro
            return artifact_id, task_run_id

        @flow
        async def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id, task_run_id = await my_task()

            return artifact_id, flow_run_id, task_run_id

        my_artifact_id, flow_run_id, task_run_id = await my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id == task_run_id
        assert my_progress_artifact.data == 50.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"

    async def test_update_progress_artifact_in_flow(self, client: httpx.AsyncClient):
        @flow
        def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id = create_progress_artifact(
                key="task-link-artifact-4",
                progress=0.0,
                description="my-artifact-description",
            )
            assert isinstance(artifact_id, UUID)
            update_progress_artifact(artifact_id, 50.0)

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id is None
        assert my_progress_artifact.data == 50.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"

    async def test_update_progress_artifact_in_async_flow(
        self, client: httpx.AsyncClient
    ):
        @flow
        async def my_flow():
            run_context = get_run_context()
            assert isinstance(run_context, FlowRunContext)
            assert run_context.flow_run is not None
            flow_run_id = run_context.flow_run.id

            artifact_id_coro = create_progress_artifact(
                key="task-link-artifact-4",
                progress=0.0,
                description="my-artifact-description",
            )
            assert asyncio.iscoroutine(artifact_id_coro)
            artifact_id = await artifact_id_coro
            assert isinstance(artifact_id, UUID)
            update_coro = update_progress_artifact(artifact_id, 50.0)
            assert asyncio.iscoroutine(update_coro)
            await update_coro

            return artifact_id, flow_run_id

        my_artifact_id, flow_run_id = await my_flow()

        response = await client.get(f"/artifacts/{my_artifact_id}")
        assert response.status_code == 200
        my_progress_artifact = schemas.core.Artifact.model_validate(response.json())

        assert my_progress_artifact.flow_run_id == flow_run_id
        assert my_progress_artifact.task_run_id is None
        assert my_progress_artifact.data == 50.0
        assert my_progress_artifact.type == "progress"
        assert my_progress_artifact.description == "my-artifact-description"


class TestArtifact:
    async def test_artifact_format(self):
        """Test creating an artifact and formatting its data"""
        data = {"key": "value"}
        artifact = Artifact(
            type="test", key="test-artifact", description="Test artifact", data=data
        )

        formatted_data = await artifact.aformat()
        assert formatted_data == '{"key": "value"}'

        sync_formatted = cast(str, artifact.format(_sync=True))  # pyright: ignore[reportCallIssue]
        assert sync_formatted == '{"key": "value"}'

    async def test_artifact_create_methods(self, prefect_client: PrefectClient):
        """Test both sync and async create methods"""
        data = {"test": "data"}
        artifact = Artifact(
            type="test", key="test-artifact", description="Test artifact", data=data
        )

        # Test async create
        @flow
        async def my_async_flow():
            return await artifact.acreate(prefect_client)

        response = await my_async_flow()
        assert response.key == "test-artifact"
        assert response.type == "test"
        assert response.description == "Test artifact"

        # Test sync create
        @flow
        def my_sync_flow():
            return artifact.create()

        response = my_sync_flow()
        assert isinstance(response, ArtifactResponse)
        assert response.key == "test-artifact"
        assert response.type == "test"
        assert response.description == "Test artifact"

    async def test_artifact_get_async(self, prefect_client: PrefectClient):
        """Test both sync and async get methods"""
        # Create an artifact first
        artifact = Artifact(
            type="test", key="get-test", description="Test get", data={"test": "get"}
        )

        @flow
        async def my_flow():
            return await artifact.acreate(prefect_client)

        await my_flow()

        # Test async get
        retrieved = await Artifact.aget("get-test", prefect_client)
        assert retrieved is not None
        assert retrieved.key == "get-test"
        assert retrieved.type == "test"

    def test_artifact_get_sync(self, prefect_client: PrefectClient):
        # Create an artifact first
        artifact = Artifact(
            type="test", key="get-test", description="Test get", data={"test": "get"}
        )

        @flow
        def my_flow():
            artifact.create()

        my_flow()

        # Test sync get
        retrieved = Artifact.get("get-test")
        assert isinstance(retrieved, ArtifactResponse)
        assert retrieved.key == "get-test"
        assert retrieved.type == "test"

    def test_artifact_get_or_create_sync(self):
        # Test sync get_or_create

        @flow
        def my_flow():
            return Artifact.get_or_create(
                key="get-or-create-test-sync",
                type="test",
                description="Test sync get or create",
                data={"test": "sync"},
            )

        get_or_create_result = my_flow()
        assert isinstance(get_or_create_result, tuple)
        artifact, created = get_or_create_result
        assert created is True
        assert artifact.key == "get-or-create-test-sync"

        get_or_create_result = my_flow()
        assert isinstance(get_or_create_result, tuple)
        artifact, created = get_or_create_result
        assert created is False
        assert artifact.key == "get-or-create-test-sync"

    async def test_artifact_get_or_create_async(self):
        @flow
        async def my_flow():
            return await Artifact.aget_or_create(
                key="get-or-create-test",
                type="test",
                description="Test get or create",
                data={"test": "get-or-create"},
            )

        artifact, created = await my_flow()
        assert created is True
        assert artifact.key == "get-or-create-test"

        # Test getting existing - should not create new
        artifact, created = await my_flow()
        assert created is False
        assert artifact.key == "get-or-create-test"

    async def test_artifact_creation_outside_run_context_warns(self):
        """Test that creating artifacts outside run context raises warning"""
        artifact = Artifact(
            type="test",
            key="warning-test",
            description="Test warning",
            data={"test": "warning"},
        )

        with pytest.warns(FutureWarning):
            await artifact.acreate()

        with pytest.warns(FutureWarning):
            artifact.create(_sync=True)  # pyright: ignore[reportCallIssue]

    def test_get_nonexistent_artifact_sync(self):
        """Test getting an artifact that doesn't exist returns None"""
        retrieved = Artifact.get("nonexistent-key")
        assert retrieved is None

    async def test_get_nonexistent_artifact_async(self, prefect_client: PrefectClient):
        """Test getting an artifact that doesn't exist returns None"""
        retrieved = await Artifact.aget("nonexistent-key", prefect_client)
        assert retrieved is None
