# Kubernetes Worker Implementation Changes

## Overview

We are refactoring the Kubernetes worker implementation to move state management responsibilities to a new operator pattern. This document tracks the changes made and the reasoning behind them.

## Changes Made

### 1. Operator Integration

- Added operator start/stop in worker lifecycle methods:
  ```python
  async def __aenter__(self):
      start_operator()
      return await super().__aenter__()

  async def __aexit__(self, *exc_info: Any):
      try:
          await super().__aexit__(*exc_info)
      finally:
          stop_operator()
  ```

### 2. Simplified Worker Responsibilities

The worker's responsibilities have been reduced to:
1. Creating and submitting jobs
2. Monitoring job completion
3. Returning success/failure status

All state management and event handling has been moved to the operator.

### 3. Removed Methods

We removed several methods that were handling responsibilities now managed by the operator:

- `_stream_job_logs` - Log streaming is no longer handled by the worker
- `_get_job_pod` - Pod tracking is now handled by the operator
- `_log_recent_events` - Event debugging is now handled by the operator

### 4. Simplified Job Monitoring

The `_watch_job` method has been simplified to:
- Monitor job completion
- Return status code (0 for success, -1 for failure)
- No longer handles pod status or log streaming

```python
async def _watch_job(self, logger, job_name, configuration, client) -> int:
    """Watch a job until completion."""
    job = await self._get_job(logger, job_name, configuration, client)
    if not job:
        return -1

    async with self._get_batch_client(client) as batch_client:
        try:
            await self._monitor_job_events(...)
            # Get final job status
            job = await batch_client.read_namespaced_job(...)
            return 0 if job.status.succeeded else -1
        except Exception:
            return -1
```

### 5. Event Monitoring

The event monitoring has been simplified to only track completion events:
- `_monitor_job_events` - Only tracks job completion and failure events
- `_job_events` - Simplified to only yield completion-related events

## Current State

The worker now has a cleaner separation of concerns:
- Worker handles job lifecycle (create, monitor, cleanup)
- Operator handles state management and event processing
- No more direct flow run state management in worker
- Removed log streaming to simplify the implementation

## Next Steps

1. Review and test the operator's state management to ensure it correctly handles all job states
2. Consider if any remaining worker methods could be further simplified
3. Add tests to verify the worker and operator integration
4. Document the new operator pattern and its interaction with the worker

## Notes

- The operator is responsible for mapping job events to flow run states
- The worker only needs to monitor job completion and return a status code
- Log streaming may be reimplemented later in a more maintainable way
- All state transitions are now handled by the operator's job handler

## Related Files

- `worker.py` - Main worker implementation
- `operator.py` - New operator implementation handling state management

## Migration Status

- [x] Remove log streaming
- [x] Remove pod status tracking
- [x] Remove event debugging
- [x] Simplify job monitoring
- [x] Move state management to operator
- [ ] Add comprehensive tests
- [ ] Update documentation 