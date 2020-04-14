# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio

import pendulum
import prefect
from prefect.engine.state import Failed
from prefect.utilities.graphql import EnumValue

import prefect_server
from prefect_server import api
from prefect_server.database import models
from prefect_server.services.loop_service import LoopService


class ZombieKiller(LoopService):
    """
    The ZombieKiller is a service that monitors existing task runs for "zombies".

    Zombies are tasks that should be checkpointing with the Orchestration
    layer, but due to some issue (typically but not exclusively network issues), they
    are unable to. They're called zombies because they could still be running just fine,
    but since they're unable to communicate with the Orchestration layer, we have
    to assume they're dead in order to keep flows running smoothly.

    Zombies are considered as:
        - A running task run
        - the flow associated with the task run does has heartbeats enabled
        - the task run hasn't checked in in 2 minutes.

    The Zombie Killer loads up to 100 task runs, matching these conditions, prioritizing tasks
    by start time. These task runs are marked are then moved from their current state
    to a Failed state with a message noting that it was killed by the ZombieKiller.
    """

    zombie_killer_config_key = "services.zombie_killer.zombie_killer_loop_seconds"
    # Scheduled to run relatively frequently. Set to longer if this is putting too
    # much stress on your database.
    loop_seconds_default = 120

    async def kill_zombies(self, n_zombies: int = 100) -> int:
        """
        Main function of the Zombie Killer, responsible for locating the 
        correct task runs to kill. Task runs are eligible to be killed if they
        meet all criteria as a "Zombie".

        Args:
            - n_zombies (int): Maximum number of task runs to kill

        Returns:
            - int: Number of task runs actually killed
        """
        kill_threshold = pendulum.now("UTC") - pendulum.duration(minutes=2)

        zombie_task_runs = await models.TaskRun.where(
            {
                # Task run is currently running
                "state": {"_eq": "Running"},
                "_and": [
                    {
                        "_or": [
                            # hasn't had a heartbeat since the threshold
                            {"heartbeat": {"_lte": kill_threshold.isoformat()}},
                            # Hasn't had a heartbeat since task run creation, in which
                            # case we can safely default back to `updated`. If we use
                            # created, we can possibly end up in a loop of a task surviving
                            # and never heartbeating, and every time it would get rescheduled,
                            # the zombie killer would kill it immediately.
                            {
                                "_and": [
                                    {"heartbeat": {"_is_null": True}},
                                    {"updated": {"_lte": kill_threshold.isoformat()}},
                                ]
                            },
                        ],
                    },
                    {  # For backwards compatability, we check whether the
                        # both the old and new heartbeat keys are indicating that
                        # this is a task run that should be heartbeating
                        "_or": [
                            {
                                "flow_run": {
                                    "flow": {
                                        "settings": {
                                            "_contains": {"heartbeat_enabled": True}
                                        }
                                    }
                                }
                            },
                            {
                                "flow_run": {
                                    "flow": {
                                        "settings": {
                                            "_contains": {"disable_heartbeat": False}
                                        }
                                    }
                                }
                            },
                        ],
                    },
                ],
            },
        ).get(
            selection_set={"id"},
            order_by=[{"heartbeat": EnumValue("asc_nulls_first")}],
            limit=n_zombies,
        )

        task_runs_killed = await asyncio.gather(
            *[
                api.states.set_task_run_state(
                    zombie.id, Failed("Task killed by Zombie Killer.")
                )
                for zombie in zombie_task_runs
            ]
        )
        num_runs_killed = len(task_runs_killed)
        self.logger.info(f"{num_runs_killed} task runs killed by Zombie Killer.")
        return num_runs_killed

    async def run_once(self) -> None:
        """
        Runs the Zombie Killer one time.

        As long as any zombies are found, the Zombie Killer attempts to go
        back in for another round. If no zombies are found, we consider this
        "run" of the Zombie Killer complete and we move on.
        """

        zombies_killed = True

        while zombies_killed:
            zombies_killed = await self.kill_zombies()
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(ZombieKiller().run())
