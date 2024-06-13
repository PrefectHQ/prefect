"""
This module implements management of concurrency with a focus on seamless handling of
both asynchronous and synchronous calls.

Much of the complexity managed here arises from ensuring that a thread of execution is
not blocked.

The main data structure is a `Call` which is created from a function call capturing
local context variables. The call is then submitted to run somewhere via a `Portal`.
The primary portal used is the `WorkerThread`, which executes work on a thread running
concurrently to the one that created the call. A singleton `EventLoopThread` portal
is also used to schedule work on a dedicated event loop.

The result of the call can be retrieved asynchronously using `Call.result()`. Behind
the scenes, a `Future` is used to report the result of the call. Retrieving the result
of a call is a blocking operation.

Sometimes, it is important not to block the current thread while retrieving the result
of a call. For this purpose, there is the `Waiter`. Waiters attach to a call and provide
a `Waiter.wait()` method to wait for the call to complete. Instead of just blocking, the
waiter watches a queue for calls to execute. Waiters implement the portal interface
allowing calls to be submitted to its queue. This pattern is most common when a call
running on a worker thread needs to schedule work back on the main thread.

A possible scenario is as follows:

- The main thread submits a call to a worker thread
- The main thread uses a waiter to wait for the call to finish
- The call does some work on the worker thread
- The call reaches a point where it needs to run a call on the main thread
- The call submits a callback to the waiter and waits for the callback's result
- The waiter on the main thread runs the callback

In most cases, a consumer of these utilities will not need to be aware of these details.
Instead, a simple API is exposed in the  `concurrency.api` module. The API is split into
`api.from_sync` and `api.from_async` for use from synchronous and asynchronous contexts
respectively.
"""

import prefect._internal._logging

logger = prefect._internal._logging.logger.getChild("concurrency")
