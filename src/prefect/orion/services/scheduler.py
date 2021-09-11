import pendulum
import asyncio
import sqlalchemy as sa
from prefect.orion.services.loop_service import LoopService
from prefect.orion import models
from prefect.orion.utilities.database import get_session_factory
from prefect.utilities.collections import batched_iterable
import prefect


class Scheduler(LoopService):
    loop_seconds = prefect.settings.orion.services.scheduler_loop_seconds
    deployment_batch_size = (
        prefect.settings.orion.services.scheduler_deployment_batch_size
    )
    max_runs = prefect.settings.orion.services.scheduler_max_runs
    max_timedelta = prefect.settings.orion.services.scheduler_max_timedelta

    async def run_once(self):
        now = pendulum.now("UTC")
        total_inserted_runs = 0
        session_factory = await get_session_factory()

        async with session_factory() as session:
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

                # if no deployments were found, exit the loop
                if not deployments:
                    break

                # record the last deployment ID
                last_id = deployments[-1].id

                # collect runs across all deployments
                all_runs = []
                for deployment in deployments:
                    runs = await models.deployments._generate_scheduled_flow_runs(
                        session=session,
                        deployment_id=deployment.id,
                        start_time=now,
                        end_time=now + self.max_timedelta,
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

            self.logger.info(f"Scheduled {total_inserted_runs} runs.")


if __name__ == "__main__":
    asyncio.run(Scheduler().start())
