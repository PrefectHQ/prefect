import importlib
import os
import random
import signal
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from unittest.mock import MagicMock, create_autospec
from uuid import UUID, uuid4

import pytest
from prefect_aws.microvm import supervisor
from prefect_aws.microvm.payload import RunHookPayload

import prefect._flow_run_suspension
import prefect._internal.observers
import prefect.flow_engine
from prefect import Flow, flow
from prefect._flow_run_suspension import (
    PrestartedFlowRunSuspensionObserver,
    adopt_prestarted_flow_run_suspension_observer,
    prestart_flow_run_suspension_observer,
)
from prefect._internal.control_listener import configure_from_env
from prefect._internal.metrics import RunMetrics
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import FlowRun, State
from prefect.engine import _drive_run_flow_result, handle_engine_signals
from prefect.flow_engine import (
    _run_flow_from_runtime_entrypoint,
    load_flow,
    load_flow_run,
    run_flow,
)
from prefect.states import (
    Cancelled,
    Completed,
    Crashed,
    Failed,
    Pending,
    Running,
    StateType,
)

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="The MicroVM entrypoint forks."),
    pytest.mark.filterwarnings(
        "ignore:This process .* is multi-threaded:DeprecationWarning"
    ),
    pytest.mark.usefixtures("api_from_environment"),
]

CreateFlowRun = Callable[[State], FlowRun]


def make_payload(flow_run_id: UUID, **overrides: object) -> RunHookPayload:
    fields: dict[str, object] = {"v": 1, "flow_run_id": flow_run_id}
    fields.update(overrides)
    return RunHookPayload.model_validate(fields)


def read_state(flow_run_id: UUID) -> State:
    with get_client(sync_client=True) as client:
        state = client.read_flow_run(flow_run_id).state
    assert state is not None
    return state


def child_exits_with(code: object) -> Callable[[RunHookPayload], None]:
    def run_in_child(payload: RunHookPayload) -> None:
        if code:
            raise SystemExit(code)

    return run_in_child


def child_raises(payload: RunHookPayload) -> None:
    raise RuntimeError("flow code failed")


def child_is_killed(payload: RunHookPayload) -> None:
    os.kill(os.getpid(), signal.SIGKILL)


def test_report_crash_moves_a_running_flow_run_to_crashed(
    flow_run_in: CreateFlowRun,
):
    flow_run = flow_run_in(Running())

    supervisor.report_crash(flow_run.id, "exited with code 3")

    state = read_state(flow_run.id)
    assert state.type == StateType.CRASHED
    assert state.message == "Flow run process exited with code 3."


@pytest.mark.parametrize(
    "final_state",
    [Completed(), Cancelled(), Failed(), Crashed(message="crashed earlier")],
    ids=["completed", "cancelled", "failed", "crashed"],
)
def test_report_crash_leaves_a_final_flow_run_in_its_state(
    flow_run_in: CreateFlowRun, final_state: State
):
    flow_run = flow_run_in(final_state)
    assert flow_run.state is not None

    supervisor.report_crash(flow_run.id, "exited with code 1")

    state = read_state(flow_run.id)
    assert state.type == final_state.type
    assert state.id == flow_run.state.id


def test_child_exit_0_leaves_the_flow_run_alone(
    monkeypatch: pytest.MonkeyPatch, flow_run_in: CreateFlowRun
):
    flow_run = flow_run_in(Running())
    monkeypatch.setattr(supervisor, "execute_flow_run", child_exits_with(0))

    assert supervisor.supervise_flow_run(make_payload(flow_run.id)) == 0

    assert read_state(flow_run.id).type == StateType.RUNNING


@pytest.mark.parametrize(
    "run_in_child, message",
    [
        (child_exits_with(3), "Flow run process exited with code 3."),
        (child_raises, "Flow run process exited with code 1."),
        (child_is_killed, "Flow run process was killed by signal 9."),
        (child_exits_with(256), "Flow run process exited with code 1."),
        (child_exits_with(-1), "Flow run process exited with code 1."),
        (child_exits_with("not an int"), "Flow run process exited with code 1."),
    ],
    ids=["exit-3", "exception", "sigkill", "exit-256", "exit-negative", "exit-str"],
)
def test_failed_child_moves_the_flow_run_to_crashed(
    monkeypatch: pytest.MonkeyPatch,
    flow_run_in: CreateFlowRun,
    run_in_child: Callable[[RunHookPayload], None],
    message: str,
):
    flow_run = flow_run_in(Running())
    monkeypatch.setattr(supervisor, "execute_flow_run", run_in_child)

    assert supervisor.supervise_flow_run(make_payload(flow_run.id)) == 1

    state = read_state(flow_run.id)
    assert state.type == StateType.CRASHED
    assert state.message == message


def test_failed_crash_report_still_exits_1(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(supervisor, "execute_flow_run", child_exits_with(1))

    assert supervisor.supervise_flow_run(make_payload(uuid4())) == 1


def test_sigterm_to_the_parent_is_forwarded_to_the_child(
    monkeypatch: pytest.MonkeyPatch, flow_run_in: CreateFlowRun
):
    flow_run = flow_run_in(Running())
    signals_received_by_the_test: list[int] = []

    def test_sigterm_handler(signum: int, frame: FrameType | None) -> None:
        signals_received_by_the_test.append(signum)

    child_ready_read, child_ready_write = os.pipe()

    def wait_for_sigterm(payload: RunHookPayload) -> None:
        os.write(child_ready_write, b"x")
        time.sleep(60)

    def send_sigterm_once_the_supervisor_handles_it() -> None:
        os.read(child_ready_read, 1)
        deadline = time.monotonic() + 10
        while (
            signal.getsignal(signal.SIGTERM) is test_sigterm_handler
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        os.kill(os.getpid(), signal.SIGTERM)

    monkeypatch.setattr(supervisor, "execute_flow_run", wait_for_sigterm)
    previous_handler = signal.signal(signal.SIGTERM, test_sigterm_handler)
    try:
        sender = threading.Thread(target=send_sigterm_once_the_supervisor_handles_it)
        sender.start()
        exit_code = supervisor.supervise_flow_run(make_payload(flow_run.id))
        sender.join()
        handler_after_supervising = signal.getsignal(signal.SIGTERM)
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        os.close(child_ready_read)
        os.close(child_ready_write)

    assert exit_code == 1
    assert signals_received_by_the_test == []
    assert handler_after_supervising is test_sigterm_handler
    assert read_state(flow_run.id).message == (
        "Flow run process was killed by signal 15."
    )


def test_sigterm_sent_just_after_the_fork_is_forwarded_to_the_child(
    monkeypatch: pytest.MonkeyPatch, flow_run_in: CreateFlowRun
):
    flow_run = flow_run_in(Running())
    signals_received_by_the_test: list[int] = []

    def test_sigterm_handler(signum: int, frame: FrameType | None) -> None:
        signals_received_by_the_test.append(signum)

    real_fork = os.fork

    def fork_then_sigterm_the_parent() -> int:
        child_pid = real_fork()
        if child_pid != 0:
            # Sent to this thread, as SIGTERM reaches a single-threaded PID 1,
            # before the supervisor has installed its forwarding handler.
            signal.pthread_kill(threading.main_thread().ident, signal.SIGTERM)
        return child_pid

    def wait_for_sigterm(payload: RunHookPayload) -> None:
        time.sleep(30)

    monkeypatch.setattr(supervisor.os, "fork", fork_then_sigterm_the_parent)
    monkeypatch.setattr(supervisor, "execute_flow_run", wait_for_sigterm)
    previous_handler = signal.signal(signal.SIGTERM, test_sigterm_handler)
    try:
        exit_code = supervisor.supervise_flow_run(make_payload(flow_run.id))
    finally:
        signal.signal(signal.SIGTERM, previous_handler)

    assert exit_code == 1
    assert signals_received_by_the_test == []
    assert read_state(flow_run.id).message == (
        "Flow run process was killed by signal 15."
    )


def sigterm_is_blocked() -> bool:
    return signal.SIGTERM in signal.pthread_sigmask(signal.SIG_BLOCK, [])


@pytest.mark.usefixtures("restore_signal_mask")
def test_child_gets_default_sigterm_unblocked_and_parent_mask_is_restored(
    monkeypatch: pytest.MonkeyPatch,
):
    assert not sigterm_is_blocked()
    report_read, report_write = os.pipe()

    def report_sigterm_state(payload: RunHookPayload) -> None:
        is_default = signal.getsignal(signal.SIGTERM) == signal.SIG_DFL
        os.write(report_write, f"{is_default} {sigterm_is_blocked()}".encode())

    def test_sigterm_handler(signum: int, frame: FrameType | None) -> None:
        pass

    monkeypatch.setattr(supervisor, "execute_flow_run", report_sigterm_state)
    previous_handler = signal.signal(signal.SIGTERM, test_sigterm_handler)
    try:
        exit_code = supervisor.supervise_flow_run(make_payload(uuid4()))
        parent_blocks_sigterm_after_supervising = sigterm_is_blocked()
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        os.close(report_write)
    child_report = os.read(report_read, 64)
    os.close(report_read)

    assert exit_code == 0
    assert child_report == b"True False"
    assert not parent_blocks_sigterm_after_supervising


def test_child_reseeds_random(monkeypatch: pytest.MonkeyPatch):
    # CPython reseeds `random` in every forked child; this guards against an
    # interpreter, or a child started some other way, that does not.
    report_read, report_write = os.pipe()

    def report_random(payload: RunHookPayload) -> None:
        os.write(report_write, repr(random.random()).encode())

    monkeypatch.setattr(supervisor, "execute_flow_run", report_random)
    state_before_test = random.getstate()
    random.seed(1234)
    try:
        exit_code = supervisor.supervise_flow_run(make_payload(uuid4()))
        parent_next_random = random.random()
    finally:
        random.setstate(state_before_test)
        os.close(report_write)
    child_random = float(os.read(report_read, 64))
    os.close(report_read)

    assert exit_code == 0
    assert child_random != parent_next_random


@pytest.mark.usefixtures("restore_signal_mask")
def test_fork_failure_propagates_and_unblocks_sigterm(monkeypatch: pytest.MonkeyPatch):
    assert not sigterm_is_blocked()

    def fail_to_fork() -> int:
        raise OSError("fork failed")

    monkeypatch.setattr(supervisor.os, "fork", fail_to_fork)

    with pytest.raises(OSError, match="fork failed"):
        supervisor.supervise_flow_run(make_payload(uuid4()))

    assert not sigterm_is_blocked()


def test_child_makes_itself_the_preferred_oom_victim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    oom_score_adj = tmp_path / "oom_score_adj"
    monkeypatch.setattr(supervisor, "OOM_SCORE_ADJ_PATH", oom_score_adj)
    monkeypatch.setattr(supervisor, "execute_flow_run", child_exits_with(0))

    assert supervisor.supervise_flow_run(make_payload(uuid4())) == 0

    assert oom_score_adj.read_text() == "1000"


def test_supervisor_reaps_other_exited_children(monkeypatch: pytest.MonkeyPatch):
    exited_sibling_pid = os.fork()
    if exited_sibling_pid == 0:
        os._exit(0)

    def outlive_the_sibling(payload: RunHookPayload) -> None:
        time.sleep(0.5)

    monkeypatch.setattr(supervisor, "execute_flow_run", outlive_the_sibling)

    assert supervisor.supervise_flow_run(make_payload(uuid4())) == 0

    with pytest.raises(ChildProcessError):
        os.waitpid(exited_sibling_pid, os.WNOHANG)


def test_entrypoint_payload_runs_the_runtime_entrypoint_in_working_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.chdir(Path.cwd())
    run_from_entrypoint = create_autospec(_run_flow_from_runtime_entrypoint)
    monkeypatch.setattr(
        supervisor, "_run_flow_from_runtime_entrypoint", run_from_entrypoint
    )
    seen_cwd: list[Path] = []
    run_from_entrypoint.side_effect = lambda *args: seen_cwd.append(Path.cwd())
    flow_run_id = uuid4()

    supervisor.execute_flow_run(
        make_payload(
            flow_run_id, entrypoint="flows/etl.py:etl", working_dir=str(tmp_path)
        )
    )

    run_from_entrypoint.assert_called_once_with(flow_run_id, "flows/etl.py:etl")
    assert seen_cwd == [tmp_path.resolve()]


def test_null_entrypoint_loads_the_flow_from_the_flow_run(
    monkeypatch: pytest.MonkeyPatch, flow_run_in: CreateFlowRun
):
    flow_run = flow_run_in(Running())
    flow = MagicMock(name="flow")
    load_run = create_autospec(load_flow_run, return_value=flow_run)
    load = create_autospec(load_flow, return_value=flow)
    run = create_autospec(run_flow, return_value="run result")
    drive = create_autospec(_drive_run_flow_result)
    run_from_entrypoint = create_autospec(_run_flow_from_runtime_entrypoint)
    configure = create_autospec(configure_from_env)
    signals = create_autospec(handle_engine_signals)
    metrics = create_autospec(RunMetrics)
    monkeypatch.setattr(supervisor, "configure_from_env", configure)
    monkeypatch.setattr(supervisor, "handle_engine_signals", signals)
    monkeypatch.setattr(supervisor, "RunMetrics", metrics)
    monkeypatch.setattr(supervisor, "load_flow_run", load_run)
    monkeypatch.setattr(supervisor, "load_flow", load)
    monkeypatch.setattr(supervisor, "run_flow", run)
    monkeypatch.setattr(supervisor, "_drive_run_flow_result", drive)
    monkeypatch.setattr(
        supervisor, "_run_flow_from_runtime_entrypoint", run_from_entrypoint
    )

    supervisor.execute_flow_run(make_payload(flow_run.id, entrypoint=None))

    load_run.assert_called_once_with(flow_run_id=flow_run.id)
    load.assert_called_once_with(flow_run)
    assert run.call_args.args == (flow,)
    assert run.call_args.kwargs["flow_run"] is flow_run
    drive.assert_called_once_with(flow, "run result")
    run_from_entrypoint.assert_not_called()
    configure.assert_called_once_with()
    signals.assert_called_once_with(flow_run.id)
    signals.return_value.__enter__.assert_called_once()
    metrics.assert_called_once_with(flow_run, flow)
    metrics.return_value.__enter__.assert_called_once()


@pytest.fixture
def watched_flow_run_ids(monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    """
    Replace the `FlowRunSuspendingObserver` that suspension observer threads use,
    so that none connects to the API, and return the IDs of the flow runs they
    watch.
    """
    watched: list[UUID] = []

    class FakeFlowRunSuspendingObserver:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeFlowRunSuspendingObserver":
            return self

        async def __aexit__(self, *exc_info: object) -> None:
            pass

        async def watch_flow_run_id(self, flow_run_id: UUID) -> None:
            watched.append(flow_run_id)

    monkeypatch.setattr(
        prefect._internal.observers,
        "FlowRunSuspendingObserver",
        FakeFlowRunSuspendingObserver,
    )
    return watched


@pytest.fixture
def engine_observers_started(monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    """
    Return the IDs of the flow runs for which the flow run engine starts its own
    suspension observer instead of adopting a prestarted one.
    """
    started: list[UUID] = []

    @contextmanager
    def record_observe_flow_run_suspension(
        flow_run_id: UUID, suspension_request: object
    ) -> Iterator[None]:
        started.append(flow_run_id)
        yield

    monkeypatch.setattr(
        prefect.flow_engine,
        "observe_flow_run_suspension",
        record_observe_flow_run_suspension,
    )
    return started


def flow_that_records_it_ran(ran: list[bool]) -> Flow[[], None]:
    @flow(name="microvm-supervisor-loaded-flow")
    def loaded_flow() -> None:
        ran.append(True)

    return loaded_flow


def deployment_flow_run(loaded_flow: Flow[[], None]) -> FlowRun:
    with get_client(sync_client=True) as client:
        flow_id = client.create_flow(loaded_flow)
        deployment_id = client.create_deployment(
            flow_id=flow_id, name=f"microvm-supervisor-{uuid4()}"
        )
        return client.create_flow_run_from_deployment(deployment_id)


def patch_flow_loading(
    monkeypatch: pytest.MonkeyPatch,
    loaded_flow: Flow[[], None],
    adopted_while_loading_flow_run: list[PrestartedFlowRunSuspensionObserver | None],
    adopted_while_loading_flow: list[PrestartedFlowRunSuspensionObserver | None],
) -> None:
    """
    Make the no-entrypoint path load `loaded_flow`, and record the prestarted
    observer while the flow run and the flow load.
    """
    monkeypatch.setattr(
        supervisor, "configure_from_env", create_autospec(configure_from_env)
    )

    def load_flow_run_recording(flow_run_id: UUID) -> FlowRun:
        flow_run = load_flow_run(flow_run_id=flow_run_id)
        adopted_while_loading_flow_run.append(
            adopt_prestarted_flow_run_suspension_observer(flow_run_id)
        )
        return flow_run

    def load_flow_recording(flow_run: FlowRun) -> Flow[[], None]:
        adopted_while_loading_flow.append(
            adopt_prestarted_flow_run_suspension_observer(flow_run.id)
        )
        return loaded_flow

    monkeypatch.setattr(supervisor, "load_flow_run", load_flow_run_recording)
    monkeypatch.setattr(supervisor, "load_flow", load_flow_recording)


def test_null_entrypoint_deployment_run_adopts_the_prestarted_observer(
    monkeypatch: pytest.MonkeyPatch,
    watched_flow_run_ids: list[UUID],
    engine_observers_started: list[UUID],
):
    ran: list[bool] = []
    loaded_flow = flow_that_records_it_ran(ran)
    flow_run = deployment_flow_run(loaded_flow)
    assert flow_run.deployment_id is not None
    adopted_while_loading_flow_run: list[
        PrestartedFlowRunSuspensionObserver | None
    ] = []
    adopted_while_loading_flow: list[PrestartedFlowRunSuspensionObserver | None] = []
    patch_flow_loading(
        monkeypatch,
        loaded_flow,
        adopted_while_loading_flow_run,
        adopted_while_loading_flow,
    )

    supervisor.execute_flow_run(make_payload(flow_run.id, entrypoint=None))

    assert ran == [True]
    assert read_state(flow_run.id).type == StateType.COMPLETED
    assert len(adopted_while_loading_flow_run) == 1
    assert adopted_while_loading_flow_run[0] is not None
    assert adopted_while_loading_flow == adopted_while_loading_flow_run
    assert engine_observers_started == []
    assert watched_flow_run_ids == [flow_run.id]
    assert adopt_prestarted_flow_run_suspension_observer(flow_run.id) is None


def test_null_entrypoint_run_without_deployment_stops_the_prestarted_observer(
    monkeypatch: pytest.MonkeyPatch,
    flow_run_in: CreateFlowRun,
    watched_flow_run_ids: list[UUID],
    engine_observers_started: list[UUID],
):
    flow_run = flow_run_in(Pending())
    assert flow_run.deployment_id is None
    ran: list[bool] = []
    loaded_flow = flow_that_records_it_ran(ran)
    adopted_while_loading_flow_run: list[
        PrestartedFlowRunSuspensionObserver | None
    ] = []
    adopted_while_loading_flow: list[PrestartedFlowRunSuspensionObserver | None] = []
    patch_flow_loading(
        monkeypatch,
        loaded_flow,
        adopted_while_loading_flow_run,
        adopted_while_loading_flow,
    )

    supervisor.execute_flow_run(make_payload(flow_run.id, entrypoint=None))

    assert ran == [True]
    assert read_state(flow_run.id).type == StateType.COMPLETED
    assert len(adopted_while_loading_flow_run) == 1
    assert adopted_while_loading_flow_run[0] is not None
    assert adopted_while_loading_flow == [None]
    assert engine_observers_started == []


def test_null_entrypoint_deployment_run_with_a_prefect_without_prestarted_observers(
    monkeypatch: pytest.MonkeyPatch,
    watched_flow_run_ids: list[UUID],
    engine_observers_started: list[UUID],
):
    ran: list[bool] = []
    loaded_flow = flow_that_records_it_ran(ran)
    flow_run = deployment_flow_run(loaded_flow)
    assert flow_run.deployment_id is not None
    adopted_while_loading_flow_run: list[
        PrestartedFlowRunSuspensionObserver | None
    ] = []
    adopted_while_loading_flow: list[PrestartedFlowRunSuspensionObserver | None] = []
    try:
        with monkeypatch.context() as older_prefect:
            older_prefect.delattr(
                prefect._flow_run_suspension, "prestart_flow_run_suspension_observer"
            )
            importlib.reload(supervisor)
            assert (
                supervisor.prestart_flow_run_suspension_observer
                is not prestart_flow_run_suspension_observer
            )
            patch_flow_loading(
                older_prefect,
                loaded_flow,
                adopted_while_loading_flow_run,
                adopted_while_loading_flow,
            )

            supervisor.execute_flow_run(make_payload(flow_run.id, entrypoint=None))
    finally:
        importlib.reload(supervisor)

    assert ran == [True]
    assert read_state(flow_run.id).type == StateType.COMPLETED
    assert adopted_while_loading_flow_run == [None]
    assert engine_observers_started == [flow_run.id]
    assert watched_flow_run_ids == []
    assert (
        supervisor.prestart_flow_run_suspension_observer
        is prestart_flow_run_suspension_observer
    )
