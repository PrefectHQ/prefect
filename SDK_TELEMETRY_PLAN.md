# Prefect SDK Telemetry Plan

## Overview

This document outlines a privacy-first, opt-in telemetry system for the Prefect SDK to better understand user patterns and improve the product without compromising trust.

## Current State

### Existing Telemetry Infrastructure
- **Server-side telemetry**: Already exists at `src/prefect/server/services/telemetry.py`
  - Sends heartbeats to `sens-o-matic.prefect.io` 
  - Controlled by `PREFECT_SERVER_ANALYTICS_ENABLED` setting
  - Collects: platform info, Python version, API version, session ID
  - Runs as a service in the server process
  
- **Run telemetry (OpenTelemetry)**: Integration at `src/prefect/telemetry/run_telemetry.py`
  - Controlled by `PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY`
  - Used for distributed tracing of flow/task runs
  - Creates spans for observability
  - Separate from usage telemetry

- **No SDK usage telemetry**: Currently no collection of SDK usage patterns from clients

## Proposed SDK Telemetry System

### Core Principles

1. **Opt-in by default**: Telemetry is disabled unless explicitly enabled
2. **Transparency**: Clear documentation about what's collected and why
3. **Minimal data**: Only collect what's necessary to improve the product
4. **No PII/sensitive data**: Never collect personal info, credentials, or business data
5. **User control**: Easy to enable/disable at any time
6. **Respect existing users**: Don't surprise existing users with new telemetry

### What to Collect (SDK Usage Metrics)

#### Safe to Collect
- **Feature usage**:
  - Flow/task decorator usage patterns
  - Which decorators/features are used (retries, caching, etc.)
  - Deployment types created
  - Block types used (not values)
  - Task runner types
  
- **Error patterns**:
  - Exception types (not messages/stacktraces with user code)
  - Failed import attempts for integrations
  - Configuration errors
  
- **Performance metrics**:
  - Flow/task execution counts (not names)
  - Approximate run durations (bucketed, not exact)
  - Concurrency patterns
  
- **Environment info**:
  - Prefect version
  - Python version
  - OS type
  - CLI vs programmatic usage
  - Integration packages installed

#### Never Collect
- Flow/task names or descriptions
- Parameter values or results
- User-defined variables or code
- File paths or directory structures
- Network endpoints or credentials
- Business logic or data
- Exact timestamps or durations
- IP addresses or hostnames
- User/organization identifiers (except anonymous session ID)

### Implementation Architecture

```
┌─────────────────┐
│   User Code     │
├─────────────────┤
│  @flow/@task    │
│   decorators    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Telemetry       │
│ Collector       │
│ (if enabled)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Local Buffer    │
│ (in-memory)     │
└────────┬────────┘
         │ Batch & Send
         │ (async, non-blocking)
         ▼
┌─────────────────┐
│ Telemetry API   │
│ (sens-o-matic)  │
└─────────────────┘
```

### Settings & State Structure

```python
# Settings in src/prefect/settings/models/sdk.py (under existing SDK settings)
class SDKSettings(PrefectBaseSettings):
    # ... existing SDK settings ...
    
    telemetry_enabled: bool = Field(
        default=False,
        description="Enable anonymous usage telemetry for SDK improvement"
    )
    
    telemetry_endpoint: str = Field(
        default="https://sens-o-matic.prefect.io/sdk",
        description="Telemetry collection endpoint"
    )
    
    telemetry_batch_size: int = Field(
        default=100,
        description="Number of events to batch before sending"
    )
    
    telemetry_batch_interval_seconds: float = Field(
        default=300.0,  # 5 minutes
        description="Maximum time between telemetry sends"
    )
```

```python
# State file at ~/.prefect/telemetry_state.toml
[telemetry]
prompted = true  # Whether user has been prompted
session_id = "uuid-here"  # Anonymous session ID
prompt_date = "2024-01-01"  # When prompted
decision_date = "2024-01-01"  # When decision was made
```

Environment variables:
- `PREFECT_SDK_TELEMETRY_ENABLED` (default: `false`)
- `PREFECT_SDK_TELEMETRY_ENDPOINT` 
- `PREFECT_SDK_TELEMETRY_BATCH_SIZE`
- `PREFECT_SDK_TELEMETRY_BATCH_INTERVAL_SECONDS`

### CLI Integration

#### Initial Opt-in Flow

```bash
$ prefect flow serve my_flow.py
╭──────────────────────────────────────────────────────────────╮
│ Help us improve Prefect!                                    │
│                                                              │
│ Would you like to enable anonymous usage telemetry?         │
│ This helps us understand how Prefect is used and improve    │
│ the product. No personal or sensitive data is collected.    │
│                                                              │
│ You can change this anytime with:                          │
│   prefect config set telemetry.enabled=true/false          │
│                                                              │
│ Learn more: https://docs.prefect.io/telemetry              │
╰──────────────────────────────────────────────────────────────╯
Enable telemetry? [y/N]: 
```

This prompt would:
1. Only appear once per environment
2. Store choice in `~/.prefect/profiles.toml`
3. Never interrupt CI/CD (detect non-interactive terminals)
4. Have a timeout (default to No after 10 seconds)

#### Management Commands

```bash
# View current telemetry status
$ prefect telemetry status
Telemetry: Disabled
Session ID: <none>
Last sent: Never

# Enable telemetry
$ prefect telemetry enable
✓ Telemetry enabled. Thank you for helping improve Prefect!

# Disable telemetry  
$ prefect telemetry disable
✓ Telemetry disabled.

# View what would be collected (dry run)
$ prefect telemetry preview
Sample telemetry event:
{
  "event_type": "flow_run",
  "prefect_version": "3.0.0",
  "python_version": "3.11.0",
  "os": "darwin",
  "features_used": ["retries", "caching"],
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Implementation Phases

#### Phase 1: Foundation (Week 1-2)
- [ ] Create telemetry settings model
- [ ] Build event collector base class
- [ ] Implement local buffering/batching
- [ ] Add async HTTP client for sending
- [ ] Create CLI commands for management

#### Phase 2: Basic Collection (Week 3-4)
- [ ] Instrument flow/task decorators
- [ ] Collect feature usage flags
- [ ] Add environment detection
- [ ] Implement opt-in prompt logic
- [ ] Add telemetry preview/dry-run mode

#### Phase 3: Error Tracking (Week 5)
- [ ] Safe exception type collection
- [ ] Import error detection
- [ ] Configuration error patterns
- [ ] Add circuit breaker for failed sends

#### Phase 4: Testing & Documentation (Week 6)
- [ ] Comprehensive test suite
- [ ] Documentation site page
- [ ] Privacy policy update
- [ ] Internal review & security audit

### Privacy & Security Considerations

1. **Data minimization**: Only collect what's needed
2. **Anonymization**: No way to identify individual users
3. **Encryption**: HTTPS only for transmission
4. **Retention**: Define clear data retention policy (e.g., 90 days)
5. **Access control**: Limited access to telemetry data
6. **GDPR/CCPA**: Ensure compliance with privacy regulations
7. **Audit trail**: Log all telemetry configuration changes

### Success Metrics

- Opt-in rate > 30% of active users
- No performance impact (< 1ms overhead per flow run)
- Zero security incidents
- Positive community feedback
- Actionable insights leading to product improvements

### Open Questions

1. Should we differentiate between development and production usage?
2. How to handle air-gapped environments?
3. Should we provide a company-wide opt-out mechanism?
4. What aggregation level for metrics (hourly, daily)?
5. Should we offer a self-hosted telemetry endpoint option?

### Example Telemetry Event

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "660e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-01T12:00:00Z",
  "event_type": "sdk_usage",
  "sdk_version": "3.0.0",
  "python_version": "3.11.0",
  "os": "linux",
  "features": {
    "flow_decorator": true,
    "task_decorator": true,
    "async_tasks": false,
    "retries": true,
    "caching": false,
    "ray_task_runner": false,
    "dask_task_runner": false,
    "deployments": true,
    "blocks_used": ["s3", "github"],
    "serve_used": true
  },
  "metrics": {
    "flows_defined": 5,
    "tasks_defined": 25,
    "approx_runtime_bucket": "1-5min"
  },
  "errors": {
    "import_errors": ["prefect-aws"],
    "exception_types": ["ValueError", "TypeError"]
  }
}
```

## Next Steps

1. Review and gather feedback on this plan
2. Get privacy/legal review
3. Community RFC for transparency
4. Begin phased implementation
5. Soft launch with internal dogfooding
6. Gradual rollout with monitoring

## Alternative Approaches Considered

1. **Opt-out by default**: Rejected due to trust concerns
2. **Server-side only**: Misses client-side usage patterns  
3. **Required telemetry**: Against open-source principles
4. **Third-party analytics**: Privacy and vendor lock-in concerns

## References

- [OpenTelemetry Best Practices](https://opentelemetry.io/docs/reference/specification/telemetry-stability/)
- [Mozilla Telemetry Principles](https://wiki.mozilla.org/Firefox/Data_Collection)
- [VS Code Telemetry](https://code.visualstudio.com/docs/getstarted/telemetry)
- [Homebrew Analytics](https://docs.brew.sh/Analytics)