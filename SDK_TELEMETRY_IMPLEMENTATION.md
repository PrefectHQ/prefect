# SDK Telemetry Implementation Summary

## Overview

This branch adds **opt-in** SDK usage telemetry to Prefect to understand feature adoption without compromising user privacy. This is a new system, separate from existing server telemetry and OpenTelemetry tracing.

**GitHub Issue**: #18702

## What We Built

### 1. Settings Infrastructure
**File**: `src/prefect/settings/models/telemetry.py`

- `PREFECT_TELEMETRY_ENABLED` (default: `false`) - Opt-in by default
- `PREFECT_TELEMETRY_ENDPOINT` - Where to send telemetry
- `PREFECT_TELEMETRY_BATCH_SIZE` - Event batching configuration
- `PREFECT_TELEMETRY_BATCH_INTERVAL_SECONDS` - Send frequency

### 2. State Management
**File**: `src/prefect/telemetry/state.py`

Persistent state stored in `~/.prefect/telemetry_state.toml`:
- Tracks whether user has been prompted
- Stores anonymous session ID
- Records decision dates
- Respects `PREFECT_HOME` environment variable

### 3. Usage Collector
**File**: `src/prefect/telemetry/sdk_usage.py`

Collects anonymous metrics:
- Feature usage (retries, caching, persist_result, etc.)
- Decorator counts (flows, tasks)
- Environment info (Python version, OS)
- Block types (just types, not values)
- Exception types (just names, not messages)

### 4. Instrumentation Points
**Files modified**:
- `src/prefect/flows.py` - Added telemetry to `Flow.__init__`
- `src/prefect/tasks.py` - Added telemetry to `Task.__init__`

Example instrumentation:
```python
# In Flow.__init__
try:
    from prefect.telemetry.sdk_usage import record_decorator
    record_decorator(
        "flow",
        retries=retries is not None,
        persist_result=persist_result is not None,
        timeout=timeout_seconds is not None,
        # ... other feature flags
    )
except Exception:
    pass  # Never let telemetry break user code
```

## What Gets Collected

Example telemetry payload:
```json
{
  "session_id": "anonymous-uuid",
  "sdk_version": "3.0.0",
  "python_version": "3.11.0",
  "os": "darwin",
  "architecture": "arm64",
  "usage": {
    "features": ["flow_retries", "task_caching", "flow_persist_result"],
    "decorators": {"flow": 2, "task": 5},
    "block_types": ["s3", "github"],
    "exception_types": ["ValueError"],
    "event_count": 7
  }
}
```

## Privacy Guarantees

**Never Collected**:
- ❌ Flow/task names or descriptions
- ❌ Parameter values or results
- ❌ User code or business logic
- ❌ File paths or directory structures
- ❌ IP addresses or hostnames
- ❌ User/organization identifiers

**Only Collected**:
- ✅ Feature flags (boolean: is feature X used?)
- ✅ Counts (how many flows/tasks defined?)
- ✅ Environment metadata
- ✅ Anonymous session UUID

## Testing

To test the telemetry collection:

```python
# Enable telemetry
import os
os.environ["PREFECT_TELEMETRY_ENABLED"] = "true"

from prefect import flow, task
from prefect.telemetry.sdk_usage import get_sdk_collector

@flow(retries=2, persist_result=True)
def my_flow():
    pass

@task(cache_key_fn=lambda: "key")
def my_task():
    pass

# Preview what would be collected
collector = get_sdk_collector()
print(collector.preview())
```

## Still TODO

1. **CLI Commands** - `prefect telemetry enable/disable/status/preview`
2. **Opt-in Prompt** - One-time prompt when users run flows
3. **HTTP Sending** - Actually send to endpoint (currently just collects)
4. **More Collection Points** - Block usage, deployments, serve()
5. **Tests** - Comprehensive test suite

## Design Decisions

1. **Separate from existing telemetry** - This is SDK-focused, not server or tracing
2. **State in PREFECT_HOME** - Persistent across sessions, respects user's home
3. **Singleton collector** - Global instance to aggregate across entire session
4. **Silent failures** - Telemetry never breaks user code
5. **Feature flags, not values** - We know "retries is used", not "retries=3"

## Files Changed

```
src/prefect/
├── settings/
│   └── models/
│       ├── root.py (added telemetry to Settings)
│       └── telemetry.py (new - settings model)
├── telemetry/
│   ├── state.py (new - state management)
│   └── sdk_usage.py (new - usage collector)
├── flows.py (instrumented Flow.__init__)
└── tasks.py (instrumented Task.__init__)
```

## Next Steps

This foundation is ready for:
1. Adding CLI commands for user control
2. Implementing the opt-in prompt
3. Connecting to the actual endpoint
4. Expanding collection points
5. Community feedback via RFC