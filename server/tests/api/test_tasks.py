# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import prefect
import prefect_server
from prefect_server.database import models


class TestCreateTask:
    async def test_task_auto_generated_default_to_false(self, task_id):
        task_id = await models.Task.where(id=task_id).first({"id", "auto_generated"})
        assert task_id.auto_generated == False
