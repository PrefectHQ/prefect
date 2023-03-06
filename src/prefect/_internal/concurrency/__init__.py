"""
This module implements management of concurrency with a focus on seamless handling of
both asynchronous and synchronous calls.

Much of the complexity managed here arises from ensuring that a thread of execution is
not blocked.

The primary interfaces exist at `concurrency.api.from_sync` and `concurrency.api.from_async`
for use from synchronous and asynchronous contexts respectively.
"""
