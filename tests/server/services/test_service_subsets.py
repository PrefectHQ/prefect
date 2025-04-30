from prefect.server.events.services.actions import Actions
from prefect.server.events.services.event_logger import EventLogger
from prefect.server.events.services.event_persister import EventPersister
from prefect.server.events.services.triggers import ProactiveTriggers, ReactiveTriggers
from prefect.server.events.stream import Distributor
from prefect.server.services.base import RunInAllServers, Service
from prefect.server.services.cancellation_cleanup import CancellationCleanup
from prefect.server.services.foreman import Foreman
from prefect.server.services.late_runs import MarkLateRuns
from prefect.server.services.pause_expirations import FailExpiredPauses
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
        Scheduler,
        TaskRunRecorder,
        # Events services
        Actions,
        Distributor,
        EventLogger,
        EventPersister,
        ProactiveTriggers,
        ReactiveTriggers,
    }


def test_run_in_all_servers():
    """The following services should be enabled on background servers and web-only
    API servers"""
    assert set(RunInAllServers.all_services()) == {
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
    }
