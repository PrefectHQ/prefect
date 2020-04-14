# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


from unittest.mock import MagicMock

import pendulum
import prefect
import pytest
from prefect.engine.state import Failed, Mapped, Pending, Success

from prefect_server import api
from prefect_server.database import models as m
from prefect_server.services.zombie_killer import ZombieKiller


@pytest.fixture(autouse=True)
async def update_flow_settings(flow_id):
    """
    Sets the default heartbeat settings
    for the flow to `heartbeat_disabled=False`.
    """
    await m.Flow.where({"id": {"_eq": flow_id}}).update(
        set={"settings": {"disable_heartbeat": False}}
    )


async def update_heartbeat(task_run_id, heartbeat: pendulum.datetime) -> None:
    """
    Small convenience function to avoid having to address the model
    every time we need to manually manipulate a heartbeat... which is a lot.
    """

    await m.TaskRun.where({"id": {"_eq": task_run_id}}).update(
        set={"heartbeat": heartbeat}
    )


async def test_killer_ignores_healthy_runs(task_run_id_2):
    """Tests the killer doesn't harm healthy runs."""
    # Maybe it's a little late on the current heartbeat, but that's
    # no reason to kill off a perfectly good task, right?
    await update_heartbeat(
        task_run_id_2, pendulum.now("UTC") - pendulum.duration(seconds=15)
    )

    assert await ZombieKiller().kill_zombies() == 0


@pytest.mark.parametrize("state", [Success(), Pending(), Mapped(), Failed()])
async def test_killer_ignores_all_states_but_running(task_run_id_2, state):
    """
    Tests to make sure the killer won't kill any task runs
    except for those in `Running` states.
    """
    await api.states.set_task_run_state(task_run_id=task_run_id_2, state=state)
    # Old enough that _should_ trigger the zombie killer *if*
    # it were in a running state.
    await update_heartbeat(
        task_run_id_2, pendulum.now("UTC") - pendulum.duration(minutes=10)
    )
    assert await ZombieKiller().kill_zombies() == 0


@pytest.mark.parametrize(
    "settings", [{"heartbeat_disabled": True}, {"enable_heartbeat": False}]
)
async def test_respects_disabled_heartbeats(flow_id, task_run_id_2, settings):
    """
    Tests than an otherwise eligible zombie won't be killed
    if the flow's settings prevent it.
    """
    await m.Flow.where(id=flow_id).update(set={"settings": settings})
    # Would normally trigger the Zombie Killer
    await update_heartbeat(
        task_run_id_2, pendulum.now("UTC") - pendulum.duration(minutes=10)
    )

    assert await ZombieKiller().kill_zombies() == 0


async def test_kills_straightforward_case(task_run_id_2):
    """Tests the most straightforward zombie can be killed."""

    await update_heartbeat(
        task_run_id_2, pendulum.now("utc") - pendulum.duration(minutes=5)
    )
    assert await ZombieKiller().kill_zombies() == 1


async def test_kills_when_no_heartbeat(task_run_id_2, monkeypatch):
    """
    This test should ensure that the fallback plan of looking
    at the `updated` timestamp is used when a task has never
    successfully done a heartbeat.
    """
    await update_heartbeat(task_run_id_2, None)
    # So we can't actually update the `updated` timestamp
    # since its a trigger in the database, so what we're gonna
    # do is mock the kill threshold's sense of "now", to appear
    # as though we're 5 minutes in the future instead.

    mock_now = MagicMock(
        return_value=pendulum.now("UTC") + pendulum.duration(minutes=5)
    )

    monkeypatch.setattr(
        "prefect_server.services.zombie_killer.zombie_killer.pendulum.now", mock_now,
    )

    assert await ZombieKiller().kill_zombies() == 1


@pytest.mark.parametrize("state", [Success(), Pending(), Mapped(), Failed()])
async def test_doesnt_kill_based_on_updated_if_not_running(
    task_run_id_2, state, monkeypatch
):
    """
    This test should ensure that the fallback plan of looking
    at the `updated` timestamp is used when a task has never
    successfully done a heartbeat.
    """
    await api.states.set_task_run_state(task_run_id=task_run_id_2, state=state)
    await update_heartbeat(task_run_id_2, None)
    # So we can't actually update the `updated` timestamp
    # since its a trigger in the database, so what we're gonna
    # do is mock the kill threshold's sense of "now", to appear
    # as though we're 5 minutes in the future instead.

    mock_now = MagicMock(
        return_value=pendulum.now("UTC") + pendulum.duration(minutes=5)
    )

    monkeypatch.setattr(
        "prefect_server.services.zombie_killer.zombie_killer.pendulum.now", mock_now,
    )

    assert await ZombieKiller().kill_zombies() == 0


async def test_killed_zombies_set_to_failed(task_run_id_2):
    """
    Tests that once found, any zombie runs get set to Failed state.
    """

    await update_heartbeat(
        task_run_id_2, pendulum.now("utc") - pendulum.duration(minutes=5)
    )
    assert await ZombieKiller().kill_zombies() == 1

    instance = await m.TaskRun.where({"id": {"_eq": task_run_id_2}}).get(
        {"id", "state"}
    )
    assert instance[0].id == task_run_id_2
    assert instance[0].state == "Failed"
