from prefect.events.clients import PrefectCloudEventSubscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.task_engine import submit_autonomous_task_to_engine
from prefect.utilities.importtools import import_object


async def poll_for_scheduled_task_runs():
    async for event in PrefectCloudEventSubscriber(
        filter=EventFilter(
            event=EventNameFilter(name=["bespoke_task_run_scheduled_event"])
        )
    ):
        print("Received event: {}".format(event.event))
        task_entrypoint = event.payload.get("task_entrypoint")
        task_parameters = event.payload.get("parameters")

        task_object = import_object(task_entrypoint)

        r = await submit_autonomous_task_to_engine(task_object, task_parameters)

        print(r.result())


if __name__ == "__main__":
    import asyncio

    asyncio.run(poll_for_scheduled_task_runs())
