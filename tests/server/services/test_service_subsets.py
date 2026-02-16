from prefect.server.events.services.actions import Actions
from prefect.server.events.services.event_logger import EventLogger
from prefect.server.events.services.event_persister import EventPersister
from prefect.server.events.services.triggers import ReactiveTriggers
from prefect.server.events.stream import Distributor
from prefect.server.logs.stream import LogDistributor
from prefect.server.services.base import RunInEphemeralServers, RunInWebservers, Service
from prefect.server.services.task_run_recorder import TaskRunRecorder


def test_the_all_service_subset():
    """The following services should be enabled on background servers or full-featured
    API servers"""
    assert set(Service.all_services()) == {
        # Orchestration services
        TaskRunRecorder,
        # Events services
        Actions,
        Distributor,
        EventLogger,
        EventPersister,
        ReactiveTriggers,
        # Logs services
        LogDistributor,
    }


def test_run_in_ephemeral_servers():
    """The following services should be enabled on ephemeral servers"""
    assert set(RunInEphemeralServers.all_services()) == {
        # Orchestration services
        TaskRunRecorder,
        # Events services
        Actions,
        Distributor,
        EventLogger,
        EventPersister,
        ReactiveTriggers,
        # Logs services
        LogDistributor,
    }


def test_run_in_webservers():
    """The following services should be enabled on webservers"""
    assert set(RunInWebservers.all_services()) == {
        # Events services
        Distributor,
        # Logs services
        LogDistributor,
    }
