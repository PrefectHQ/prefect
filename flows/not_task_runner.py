import anyio

from prefect.events.clients import PrefectCloudEventSubscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.task_engine import submit_autonomous_task_to_engine
from prefect.utilities.importtools import import_object


async def submit_task(task_object, task_parameters):
    return await submit_autonomous_task_to_engine(task_object, task_parameters)


async def poll_for_scheduled_task_runs():
    async with anyio.create_task_group() as tg:
        async for event in PrefectCloudEventSubscriber(
            filter=EventFilter(
                event=EventNameFilter(name=["bespoke_task_run_scheduled_event"])
            )
        ):
            print("Received event: {}".format(event.event))
            task_entrypoint = event.payload.get("task_entrypoint")
            task_parameters = event.payload.get("parameters")

            task_object = import_object(task_entrypoint)

            tg.start_soon(submit_task, task_object, task_parameters)


if __name__ == "__main__":
    anyio.run(poll_for_scheduled_task_runs)
