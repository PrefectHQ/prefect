# Executors

The `Executor` class allows arbitrary functions to be run in various execution environments.

Executors have three main methods:
    - `start()`: a contextmanager that performs any setup and teardown
    - `submit()`: submits a function and its arguments for execution, and returns a future
    - `wait()`: accepts a collection of futures and returns their results

Executors may be synchronous or asynchronous. Synchronous executors (which block until submitted functions have been executed) do not need to implement a `wait()` method, as the results of `submit()` are already useable. Asynchronous executors must implement both `wait()` (to resolve futures returned by `submit()`) and also a form of dependency detection so that `submit()` can intelligently wait for any futures passed as arguments to subsequent function submissions.
