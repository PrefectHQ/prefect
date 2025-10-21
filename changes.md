# Flow and Task Run State Change Logging Implementation

## Overview
This implementation adds comprehensive debug logging for all flow run and task run state changes across the entire Prefect orchestration stack. The logging provides detailed visibility into state transitions for debugging purposes.

## Changes Made

### 1. Flow Engine Level (`src/prefect/flow_engine.py`)

#### FlowRunEngine.set_state() (Sync)
- Added debug logging before state transition attempts
- Added debug logging after state transition results
- Logs include flow run ID, state types, force flag, state names, and messages

#### AsyncFlowRunEngine.set_state() (Async)  
- Same logging enhancements as sync version
- Maintains async compatibility

### 2. Task Engine Level (`src/prefect/task_engine.py`)

#### SyncTaskRunEngine.set_state() (Sync)
- Added debug logging before task state transition attempts
- Added debug logging after task state transition results
- Logs include task run ID, state types, force flag, task name, state names, and messages

#### AsyncTaskRunEngine.set_state() (Async)
- Same logging enhancements as sync version
- Maintains async compatibility

### 3. Server Orchestration Level (`src/prefect/server/orchestration/instrumentation_policies.py`)

#### New FlowRunStateTransitionLogger Class
- Created comprehensive orchestration policy for logging flow state transitions
- Implements `before_transition()` and `after_transition()` hooks
- Logs flow run details, state information, and orchestration context
- Captures orchestration status and error details

#### New TaskRunStateTransitionLogger Class  
- Created comprehensive orchestration policy for logging task state transitions
- Implements `before_transition()` and `after_transition()` hooks
- Logs task run details, state information, and orchestration context
- Captures orchestration status and error details

### 4. Orchestration Policy Registration (`src/prefect/server/orchestration/core_policy.py`)

#### Flow Policy Integration
- Added import for `FlowRunStateTransitionLogger`
- Registered logger in `CoreFlowPolicy.priority()`
- Added to `MinimalFlowPolicy.priority()`
- Added to `MarkLateRunsPolicy.priority()`
- Positioned before `InstrumentFlowRunStateTransitions` for proper sequencing

#### Task Policy Integration
- Added import for `TaskRunStateTransitionLogger`
- Registered logger in `CoreTaskPolicy.priority()`
- Added to `ClientSideTaskOrchestrationPolicy.priority()`
- Added to `BackgroundTaskPolicy.priority()`
- Added to `MinimalTaskPolicy.priority()`

### 5. Server Model Level

#### Enhanced set_flow_run_state() (`src/prefect/server/models/flow_runs.py`)
- Added comprehensive logging at orchestration entry and exit points
- Logs flow run details, state transitions, and orchestration parameters
- Captures initial, proposed, and final state information
- Logs orchestration errors and completion status

#### Enhanced set_task_run_state() (`src/prefect/server/models/task_runs.py`)
- Added comprehensive logging at orchestration entry and exit points
- Logs task run details, state transitions, and orchestration parameters
- Captures initial, proposed, and final state information
- Logs orchestration errors and completion status

### 6. API Level

#### Enhanced set_flow_run_state Endpoint (`src/prefect/server/api/flow_runs.py`)
- Added API request logging with flow run ID and state details
- Added API response logging with orchestration results
- Provides visibility into HTTP API layer state changes

#### Enhanced set_task_run_state Endpoint (`src/prefect/server/api/task_runs.py`)
- Added API request logging with task run ID and state details
- Added API response logging with orchestration results
- Provides visibility into HTTP API layer state changes

## Log Output Format

The logging provides structured debug output with consistent prefixes:

### Flow Engine Logs
```
Flow run {id} attempting state transition: {from} -> {to} (force={bool})
Flow run {id} state transition result: {from} -> {to} (state_name='{name}', message='{msg}')
```

### Task Engine Logs
```
Task run {id} attempting state transition: {from} -> {to} (force={bool}, task_name='{name}')
Task run {id} state transition result: {from} -> {to} (state_name='{name}', message='{msg}', task_name='{name}')
```

### Server Model Logs
```
SERVER: Flow run {id} (name='{name}') orchestration requested: {from} -> {to} (force={bool}, policy={policy})
SERVER: Flow run {id} orchestration completed: {from} -> {to} (status={status})

SERVER: Task run {id} (name='{name}') orchestration requested: {from} -> {to} (force={bool}, deferred={bool})
SERVER: Task run {id} orchestration completed: {from} -> {to} (status={status})
```

### Orchestration Policy Logs
```
Flow run {id} (name='{name}') state transition requested: {from} -> {to}
Flow run {id} (name='{name}') state transition completed: {from} -> {to}

Task run {id} (name='{name}') state transition requested: {from} -> {to}
Task run {id} (name='{name}') state transition completed: {from} -> {to}
```

### API Logs
```
API: Flow run {id} set_state request: type={type}, name='{name}', force={bool}
API: Flow run {id} set_state response: type={type}, name='{name}', status={status}

API: Task run {id} set_state request: type={type}, name='{name}', force={bool}
API: Task run {id} set_state response: type={type}, name='{name}', status={status}
```

## Enabling Debug Logging

### Method 1: Environment Variable
```bash
export PREFECT_LOGGING_LEVEL=DEBUG
```

### Method 2: Python Configuration
```python
import logging

# Key loggers for flow and task state changes
flow_loggers = [
    'prefect.flow_engine',
    'prefect.server.api.flow_runs',
    'prefect.server.models.flow_runs'
]

task_loggers = [
    'prefect.task_engine',
    'prefect.server.api.task_runs',
    'prefect.server.models.task_runs'
]

orchestration_loggers = [
    'prefect.server.orchestration.instrumentation_policies'
]

all_loggers = flow_loggers + task_loggers + orchestration_loggers

for logger_name in all_loggers:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)
```

### Method 3: Helper Configuration
```python
from debug_logging_config import enable_all_state_debug_logging
enable_all_state_debug_logging()

# Or enable specific components:
from debug_logging_config import enable_flow_state_debug_logging, enable_task_state_debug_logging
enable_flow_state_debug_logging()
enable_task_state_debug_logging()
```

## Supporting Files Created

### Test Files
- `test_flow_state_logging.py` - Comprehensive test suite for verifying flow logging functionality
- `test_task_state_logging.py` - Comprehensive test suite for verifying task logging functionality  
- `verify_logging_changes.py` - Import verification and summary script

### Configuration
- `debug_logging_config.py` - Helper configuration for enabling debug logging for both flows and tasks

## Technical Details

### Logging Hierarchy
1. **API Layer**: HTTP request/response logging
2. **Server Model**: Orchestration entry/exit logging  
3. **Orchestration Policies**: Rule-based state transition logging
4. **Engine Layer**: Client-side state change logging (Flow & Task)

### Error Handling
- Logging failures do not affect flow or task execution
- Graceful handling of missing state information
- Safe string formatting for None values

### Performance Considerations
- Debug logging only active when explicitly enabled
- Minimal overhead when debug logging disabled
- Structured logging format for efficient parsing

## Benefits

1. **Complete Visibility**: End-to-end state transition tracking for both flows and tasks
2. **Multi-Layer Coverage**: Client, server, API, and orchestration layers
3. **Debug-Friendly**: Detailed context for troubleshooting both flow and task issues
4. **Configurable**: Easy to enable/disable as needed
5. **Non-Intrusive**: No impact on existing functionality

## Usage Examples

### Basic Flow and Task Debugging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

@task
def my_task(x):
    return x * 2

@flow
def my_flow():
    result = my_task(5)
    return result

my_flow()  # Will now show all flow and task state transitions
```

### Production Debugging
```python
# Enable only for specific problematic flows/tasks
if flow_name == "problematic_flow":
    logging.getLogger('prefect.flow_engine').setLevel(logging.DEBUG)
    logging.getLogger('prefect.task_engine').setLevel(logging.DEBUG)
```

### Selective Debugging
```python
# Enable only task logging
from debug_logging_config import enable_task_state_debug_logging
enable_task_state_debug_logging()

# Enable only flow logging  
from debug_logging_config import enable_flow_state_debug_logging
enable_flow_state_debug_logging()

# Enable everything
from debug_logging_config import enable_all_state_debug_logging
enable_all_state_debug_logging()
```

This implementation provides comprehensive debugging capabilities for both flow and task state changes while maintaining backward compatibility and performance.