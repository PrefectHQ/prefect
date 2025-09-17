from prefect.server.events.services.actions import Actions
from prefect.server.events.services.event_logger import EventLogger
from prefect.server.events.services.event_persister import EventPersister
from prefect.server.events.services.triggers import ProactiveTriggers, ReactiveTriggers
from prefect.server.events.stream import Distributor
from prefect.server.logs.stream import LogDistributor
from prefect.server.services.base import RunInEphemeralServers, RunInWebservers, Service
from prefect.server.services.cancellation_cleanup import CancellationCleanup
from prefect.server.services.foreman import Foreman
from prefect.server.services.late_runs import MarkLateRuns
from prefect.server.services.pause_expirations import FailExpiredPauses
from prefect.server.services.repossessor import Repossessor
from prefect.server.services.scheduler import RecentDeploymentsScheduler, Scheduler
from prefect.server.services.task_run_recorder import TaskRunRecorder
from prefect.server.services.telemetry import Telemetry


def test_the_all_service_subset():
    """The following services should be enabled on background servers or full-featured
    API servers"""
    assert set(Service.all_services()) == {
        Telemetry,
        # Orchestration services
        CancellationCleanup,
        FailExpiredPauses,
        Foreman,
        MarkLateRuns,
        RecentDeploymentsScheduler,
        Repossessor,
        Scheduler,
        TaskRunRecorder,
        # Events services
        Actions,
        Distributor,
        EventLogger,
        EventPersister,
        ProactiveTriggers,
        ReactiveTriggers,
        # Logs services
        LogDistributor,
    }


def test_run_in_ephemeral_servers():
    """The following services should be enabled on ephemeral servers"""
    assert set(RunInEphemeralServers.all_services()) == {
        Telemetry,
        # Orchestration services
        TaskRunRecorder,
        # Events services
        Actions,
        Distributor,
        EventLogger,
        EventPersister,
        ProactiveTriggers,
        ReactiveTriggers,
        # Logs services
        LogDistributor,
    }


def test_run_in_webservers():
    """The following services should be enabled on webservers"""
    assert set(RunInWebservers.all_services()) == {
        Telemetry,
        # Events services
        Distributor,
        # Logs services
        LogDistributor,
    }
