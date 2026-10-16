"""
Keep observer notifications flowing while the events stream comes and goes.

`ObservationDelivery` owns the transport lifecycle shared by the flow run
observers: it consumes the events stream while it is healthy, polls the current
state while it is not, and periodically tries to restore the stream. Observers
supply what to do with an event, how to check the current state, and how to
report that neither mechanism is working; interpreting flow run state remains
their responsibility.

Lifecycle state machine (`_DeliveryState` selects the active phase in `_run`;
`start`, `stop`, and `_supervise` own startup and terminal transitions):

    STARTING ---- setup succeeds -----------------------> STREAMING
        |                                                   |
        +--- setup fails ---> POLLING <--- consumer ends ----+
                                 |
                              retry due
                                 v
                            CONNECTING
                                 |
                           setup succeeds
                                 v
                            RECONCILING --- check succeeds -> STREAMING

Additional transitions and guards:

* CONNECTING -> POLLING when setup fails and the poller is still running.
* RECONCILING -> RECONCILING when a state check fails: retain the consumer,
  wait with jittered backoff, then retry the check.
* RECONCILING -> POLLING when the consumer ends and the poller is still running.
* POLLING or CONNECTING -> FAILED when polling ends without an established
  consumer. A completed successful setup wins over simultaneous poll failure.
* RECONCILING -> FAILED only when its consumer ends and polling has also ended.
* Any active phase -> STOPPING -> STOPPED on deliberate shutdown or cancelled
  entry. Cancel and await owned work, then close the connection.
* FAILED releases owned work before reporting unavailability once. STOPPED
  does not report unavailability or schedule further work.

Phase ownership and invariants:

* STARTING owns bounded setup; initial success needs no recovery reconciliation.
* POLLING owns the fallback poller and reconnect delay; CONNECTING keeps that
  same poller while owning a bounded setup attempt.
* RECONCILING owns a live consumer and a state check or retry delay. The poller
  may still be running or may have exhausted its policy; a live consumer keeps
  delivery available in either case.
* RECONCILING -> STREAMING requires a successful current-state check and a
  running consumer, followed by cancelling and awaiting any live poller.
* STREAMING owns only the consumer. A quiet stream has no idle deadline.
* STOPPED and FAILED own no running tasks or open connection.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable, Coroutine
from enum import Enum, auto
from typing import Any, TypeVar

from prefect.events import Event
from prefect.events.clients import PrefectEventSubscriber
from prefect.utilities.services import critical_service_loop

T = TypeVar("T")

# Bound on opening the socket plus the application handshake (ping, auth, filter)
SETUP_TIMEOUT_SECONDS = 10.0
RECONNECT_BASE_DELAY_SECONDS = 1.0
RECONNECT_MAX_DELAY_SECONDS = 300.0
# A stream that stays up this long resets reconnect backoff; shorter-lived
# streams (e.g. a handshake followed by an immediate close) keep backing off.
STABLE_CONNECTION_SECONDS = 60.0


async def _sleep(delay: float) -> None:
    await asyncio.sleep(delay)


def reconnect_delay(attempt: int) -> float:
    """Jittered exponential backoff for reconnect attempt number `attempt`."""
    ceiling = min(
        RECONNECT_MAX_DELAY_SECONDS,
        RECONNECT_BASE_DELAY_SECONDS * 2 ** min(attempt, 32),
    )
    return random.uniform(ceiling / 2, ceiling)


class _DeliveryState(Enum):
    STOPPED = auto()
    STARTING = auto()
    STREAMING = auto()
    POLLING = auto()
    CONNECTING = auto()
    RECONCILING = auto()
    STOPPING = auto()
    FAILED = auto()


class ObservationDelivery:
    """
    Deliver observations from the events stream, falling back to polling.

    Polling continues while a reconnect attempt is pending. Once a new stream is
    established and a current-state check succeeds, polling stops. If polling
    exhausts its retry policy while no stream is established, `on_unavailable`
    is called once and delivery stops.
    """

    def __init__(
        self,
        *,
        name: str,
        logger: logging.Logger,
        subscriber_factory: Callable[[], PrefectEventSubscriber],
        on_event: Callable[[Event], None],
        check_current_state: Callable[[], Coroutine[Any, Any, None]],
        on_unavailable: Callable[[BaseException], None],
        polling_interval: float,
    ) -> None:
        self._name = name
        self._logger = logger
        self._subscriber_factory = subscriber_factory
        self._subscriber: PrefectEventSubscriber | None = None
        self._on_event = on_event
        self._check_current_state = check_current_state
        self._on_unavailable = on_unavailable
        self._polling_interval = polling_interval
        self._state = _DeliveryState.STOPPED
        self._connected = False
        self._tasks: set[asyncio.Task[Any]] = set()
        self._supervisor: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Attempt the initial connection and begin streaming or polling."""
        assert self._state is _DeliveryState.STOPPED
        self._state = _DeliveryState.STARTING
        consumer: asyncio.Task[None] | None = None
        error = await self._connect()
        if error is None:
            consumer = self._spawn(self._consume())
            self._state = _DeliveryState.STREAMING
        else:
            self._state = _DeliveryState.POLLING
            self._logger.warning(
                "%s failed to connect to the events stream. Falling back to"
                " polling until it reconnects. Reason: %s",
                self._name,
                error,
            )
        self._supervisor = asyncio.create_task(self._supervise(consumer))

    async def stop(self) -> None:
        """Stop delivery, awaiting owned work and closing the connection."""
        self._state = _DeliveryState.STOPPING
        if self._supervisor is not None:
            self._supervisor.cancel()
            await asyncio.wait([self._supervisor])
        await self._shutdown_owned_work()
        self._state = _DeliveryState.STOPPED

    def _spawn(self, coroutine: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _shutdown_owned_work(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks)
        await self._disconnect()

    async def _supervise(self, consumer: asyncio.Task[None] | None) -> None:
        try:
            error = await self._run(consumer)
        except Exception as exc:
            self._logger.exception("%s event delivery failed unexpectedly.", self._name)
            error = exc
        finally:
            await self._shutdown_owned_work()
        self._state = _DeliveryState.FAILED
        self._on_unavailable(error)

    async def _run(self, consumer: asyncio.Task[None] | None) -> BaseException:
        """Advance delivery states until neither transport is working."""
        loop = asyncio.get_running_loop()
        failed_attempts = 0
        failed_checks = 0
        poller: asyncio.Task[None] | None = None
        while True:
            match self._state:
                case _DeliveryState.STREAMING:
                    assert consumer is not None
                    connected_at = loop.time()
                    await asyncio.wait([consumer])
                    self._log_stream_end(consumer)
                    await self._disconnect()
                    if loop.time() - connected_at >= STABLE_CONNECTION_SECONDS:
                        failed_attempts = 0
                    consumer = None
                    self._state = _DeliveryState.POLLING

                case _DeliveryState.POLLING:
                    if poller is None:
                        poller = self._spawn(
                            critical_service_loop(
                                workload=self._check_current_state,
                                interval=self._polling_interval,
                                jitter_range=0.3,
                            )
                        )
                    delay = self._spawn(_sleep(reconnect_delay(failed_attempts)))
                    failed_attempts += 1
                    await asyncio.wait(
                        [delay, poller], return_when=asyncio.FIRST_COMPLETED
                    )
                    if poller.done():
                        return _polling_error(poller)
                    self._state = _DeliveryState.CONNECTING

                case _DeliveryState.CONNECTING:
                    assert poller is not None
                    setup = self._spawn(self._connect())
                    await asyncio.wait(
                        [setup, poller], return_when=asyncio.FIRST_COMPLETED
                    )
                    if not setup.done():
                        # A pending connection is not working monitoring.
                        setup.cancel()
                        await asyncio.wait([setup])
                        return _polling_error(poller)
                    if (error := setup.result()) is not None:
                        self._logger.debug(
                            "%s failed to reconnect to the events stream: %r",
                            self._name,
                            error,
                        )
                        if poller.done():
                            return _polling_error(poller)
                        self._state = _DeliveryState.POLLING
                    else:
                        consumer = self._spawn(self._consume())
                        failed_checks = 0
                        self._state = _DeliveryState.RECONCILING

                case _DeliveryState.RECONCILING:
                    assert consumer is not None and poller is not None
                    reconcile = self._spawn(self._check_current_state())
                    await asyncio.wait(
                        [consumer, reconcile], return_when=asyncio.FIRST_COMPLETED
                    )
                    if not consumer.done():
                        if (error := reconcile.exception()) is None:
                            if poller.done():
                                _polling_error(poller)
                            else:
                                poller.cancel()
                                await asyncio.wait([poller])
                            self._logger.info(
                                "%s reconnected to the events stream and stopped"
                                " polling.",
                                self._name,
                            )
                            poller = None
                            self._state = _DeliveryState.STREAMING
                            continue

                        # Keep the functioning stream while HTTP checks recover.
                        self._logger.debug(
                            "%s reconnected to the events stream, but could not"
                            " check the current state: %r",
                            self._name,
                            error,
                        )
                        retry = self._spawn(_sleep(reconnect_delay(failed_checks)))
                        failed_checks += 1
                        await asyncio.wait(
                            [consumer, retry], return_when=asyncio.FIRST_COMPLETED
                        )
                        if not consumer.done():
                            continue
                        retry.cancel()
                        await asyncio.wait([retry])

                    reconcile.cancel()
                    await asyncio.wait([reconcile])
                    self._logger.debug(
                        "%s reconnected to the events stream, but it ended before"
                        " polling stopped: %s",
                        self._name,
                        consumer.exception() or "the stream closed",
                    )
                    await self._disconnect()
                    consumer = None
                    if poller.done():
                        return _polling_error(poller)
                    self._state = _DeliveryState.POLLING

                case _:
                    raise RuntimeError(f"Unexpected delivery state: {self._state}")

    async def _connect(self) -> Exception | None:
        """Open the stream within the setup deadline, returning any failure."""
        try:
            if self._subscriber is None:
                self._subscriber = self._subscriber_factory()
            async with asyncio.timeout(SETUP_TIMEOUT_SECONDS):
                await self._subscriber.__aenter__()
                self._connected = True
        except Exception as exc:
            await self._disconnect()
            return exc
        return None

    async def _disconnect(self) -> None:
        if not self._connected or self._subscriber is None:
            return
        try:
            await self._subscriber.__aexit__(None, None, None)
        except Exception:
            self._logger.debug(
                "%s failed to close the events stream.", self._name, exc_info=True
            )
        # Left set if closing is cancelled so that final cleanup retries it
        self._connected = False

    async def _consume(self) -> None:
        assert self._subscriber is not None
        async for event in self._subscriber:
            self._on_event(event)

    def _log_stream_end(self, consumer: asyncio.Task[None]) -> None:
        if error := consumer.exception():
            self._logger.warning(
                "The %s websocket failed with an exception. Switching to polling"
                " mode until it reconnects.",
                self._name,
                exc_info=error,
            )
        else:
            self._logger.warning(
                "The %s websocket closed. Switching to polling mode until it"
                " reconnects.",
                self._name,
            )


def _polling_error(poller: asyncio.Task[None]) -> BaseException:
    return poller.exception() or RuntimeError("Polling stopped unexpectedly.")
