import asyncio

import pendulum
import sqlalchemy as sa

import prefect
from prefect.orion import models
from prefect.orion.services.loop_service import LoopService
from prefect.utilities.collections import batched_iterable

settings = prefect.settings.orion.services


class Scheduler(LoopService):
    loop_seconds: float = settings.scheduler_loop_seconds
    deployment_batch_size: int = settings.scheduler_deployment_batch_size
    max_runs: int = settings.scheduler_max_runs
    max_future_seconds: float = settings.scheduler_max_future_seconds

    async def run_once(self):
        now = pendulum.now("UTC")
        total_inserted_runs = 0

        async with self.session_factory() as session:
            with session.begin():
                last_id = None
                while True:
                    query = (
                        sa.select(models.orm.Deployment)
                        .where(
                            models.orm.Deployment.is_schedule_active.is_(True),
                            models.orm.Deployment.schedule.is_not(None),
                        )
                        .order_by(models.orm.Deployment.id)
                        .limit(self.deployment_batch_size)
                    )

                    # use cursor based pagination
                    if last_id:
                        query = query.where(models.orm.Deployment.id > last_id)

                    result = await session.execute(query)
                    deployments = result.scalars().unique().all()

                    # collect runs across all deployments
                    all_runs = []
                    for deployment in deployments:
                        runs = await models.deployments._generate_scheduled_flow_runs(
                            session=session,
                            deployment_id=deployment.id,
                            start_time=now,
                            end_time=now.add(seconds=self.max_future_seconds),
                            max_runs=self.max_runs,
                        )
                        all_runs.extend(runs)

                    # bulk insert the runs, 500 at a time
                    for batch in batched_iterable(all_runs, 500):
                        inserted_runs = (
                            await models.deployments._insert_scheduled_flow_runs(
                                session=session, runs=batch
                            )
                        )
                        await session.commit()
                        total_inserted_runs += len(inserted_runs)

                    # if no deployments were found, exit the loop
                    if len(deployments) < self.deployment_batch_size:
                        break
                    else:
                        # record the last deployment ID
                        last_id = deployments[-1].id

            self.logger.info(f"Scheduled {total_inserted_runs} runs.")


if __name__ == "__main__":
    asyncio.run(Scheduler().start())
