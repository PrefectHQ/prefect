import dataclasses
import logging
import queue
import threading
import typing
import uuid
from functools import partial

import anyio

MAIN_THREAD = threading.get_ident()

logging.basicConfig(level="DEBUG")

mt_logger = logging.getLogger("main_thread")
as_logger = logging.getLogger("async_thread")

mt_logger.debug("Logging initialized")


class Runtime:
    _calls = queue.Queue()
    _wakeup = threading.Event()

    def run_async_generator(self, fn, *args, **kwargs):
        with anyio.start_blocking_portal() as portal:
            generator = fn(*args, **kwargs)
            while True:
                try:
                    print("next plz")
                    yielded = portal.call(generator.__anext__)
                    print("yielded", yielded)
                except StopAsyncIteration:
                    print("stop")
                    break
                else:
                    if callable(yielded):
                        result = yielded()
                        print("sending", result)
                        portal.call(generator.asend, result)
                    else:
                        result = yielded

        return result

    def run_with_send_support(self, fn, *args):
        with anyio.start_blocking_portal() as self._portal:
            mt_logger.debug("Scheduling async task %s", fn)
            future = self._portal.start_task_soon(fn, *args)

            def on_completion(*args):
                self._wakeup.set()

            future.add_done_callback(on_completion)

            while not future.done():
                # Watch for some work to do
                mt_logger.debug("Waiting for wakeup event...")
                self._wakeup.wait()
                mt_logger.debug("Wake event set!")

                while True:
                    try:
                        call, callback = self._calls.get_nowait()
                    except queue.Empty:
                        break
                    else:
                        mt_logger.debug("Running sync task %s", call)
                        callback(call())

                self._wakeup.clear()

    async def run_on_main_thread(self, fn, *args):
        as_logger.debug("Scheduling sync task %s", fn)
        event = anyio.Event()
        result = None

        def on_completion(call_result):
            nonlocal result
            result = call_result
            self._portal.call(event.set)

        self._calls.put(((partial(fn, *args)), on_completion))
        self._wakeup.set()
        as_logger.debug("Waiting for completion...")
        await event.wait()

        as_logger.debug("Sync task complete!")

        return result

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass


@dataclasses.dataclass
class Run:
    id: uuid.UUID
    name: str


@dataclasses.dataclass
class Workflow:
    name: str
    fn: typing.Callable

    def __call__(self, **kwds):
        with Runtime() as runtime:
            return runtime.run_with_send_support(run_workflow, runtime, self, kwds)


async def run_workflow(runtime: Runtime, workflow: Workflow, parameters: dict):
    run = await create_run(workflow)
    return await orchestrate_run(runtime, workflow, run, parameters)


async def create_run(workflow: Workflow) -> Run:
    return Run(id=uuid.uuid4(), name=workflow.name)


async def orchestrate_run(
    runtime: Runtime, workflow: Workflow, run: Run, parameters: dict
):
    for i in range(3):
        result = await runtime.run_on_main_thread(workflow.fn, **parameters)


def foo():
    print("Running foo!")
    print("in main thread?", threading.get_ident() == MAIN_THREAD)
    return 1


workflow = Workflow(name="foo", fn=foo)
result = workflow()
print(result)


async def chain_async_generator(gen):
    while True:
        try:
            yielded = await gen.__anext__()
        except StopAsyncIteration:
            print("stop")
            break
        else:
            result = yielded()
            await gen.asend(result)
