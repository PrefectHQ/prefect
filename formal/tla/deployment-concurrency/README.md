# Deployment concurrency TLA+ model

This bounded safety model asks whether cleanup can revoke a renewed lease or
decrement another run's capacity. Its unimplemented target makes a durable SQL
claim the sole decrement authority, updates claim and accounting atomically,
and rechecks the current deadline before expiry release. TLC checks that
protocol, including duplicate reaper delivery and PENDING reacquisition, not
the Python implementation.

Owner: Prefect server orchestration maintainers.

## Model and checks

Bounds: two runs, two unique lease IDs, two reaper work items per lease,
capacity one, bounded lease revisions, and nondeterministic expiry, PENDING
reacquisition, terminal release, flow-run deletion, and queued expiry release.
The target result is exhaustive only within these bounds. No configuration
models the whole current protocol; the unsafe configurations isolate known
failures.

| Configuration | Status | Expected TLC result |
| --- | --- | --- |
| `DeploymentConcurrency.cfg` | target claim protocol | passes; 55,915 states, depth 19 |
| `CounterexampleStaleReap.cfg` | unsafe: no deadline recheck | exit 12; `RenewWinsAgainstStaleScan`, depth 10 |
| `CounterexampleFallbackRelease.cfg` | unsafe: no live-claim guard | exit 12; `NoForeignRelease`, depth 17 |
| `CounterexampleReadPresentRelease.cfg` | unsafe: stale read-present release | exit 12; `NoForeignRelease`, depth 17 |
| `CounterexampleFlowRunDeletion.cfg` | unsafe: deletion leaves its lease live | exit 12; `NoForeignRelease`, depth 14 |
| `CounterexampleDuplicateReap.cfg` | unsafe: duplicate reaper decrement | exit 12; `NoForeignRelease`, depth 18 |

These TLA+ tools v1.7.4 baselines record the explored graphs; the counterexample
traces witness the unsafe paths. CI verifies each expected exit and invariant.

Properties: `TypeOK`, `CounterBounds`, `ClaimCapacitySafety`,
`OwnershipConsistent`, and `AccountingConsistent` constrain state and
accounting; `NoForeignRelease` prevents cross-lease decrement; and
`RenewWinsAgainstStaleScan` fences stale work after a renewal.

This model excludes liveness, rate limits, legacy clients and stores, lease-ID
reuse, holder indexing, SQL outages, arbitrary cardinalities, more than two
reaper jobs per lease, physical overlap during lease-loss reaction, response
replay, and request identity. The target does not access an external lease
store: projections, migration, and eventual reclamation need separate models
or tests, and cannot authorize claim actions.

`Limit` maps to `ConcurrencyLimitV2.limit`, is selected before `Init`, and stays
fixed for one modeled behavior. The target assumes a dedicated, unshared limit
whose occupied slots all have modeled claims. It excludes limit-definition
changes, `global_concurrency_limit_id` reassignment, and public v2 API writes to
that limit's `active_slots` through direct updates or leased and unleased
increments and decrements. Production does not enforce this isolation:
deployments can share a global limit, and public v2 callers can mutate it.

Implementing the target therefore requires routing every slot writer for a
claim-managed limit through the same claim authority, or isolating deployment
accounting from shared global-limit accounting. Dynamic limit changes need a
separate model; lowering a live limit may leave occupancy above the new limit
until holders release.

## Run locally

Use JDK 21 locally; CI uses Temurin 21. Download the TLA+ tools release and
SHA-256 checksum pinned in `.github/workflows/tla-plus.yaml` to
`.planning/tla-tools/tla2tools.jar`. Use `$JAVA_HOME/bin/java` if `java` is
not on `PATH`, then run from the repository root:

```bash
java -XX:+UseParallelGC -jar .planning/tla-tools/tla2tools.jar \
  -workers 1 \
  -metadir .planning/tlc/deployment-concurrency/target \
  -config formal/tla/deployment-concurrency/DeploymentConcurrency.cfg \
  formal/tla/deployment-concurrency/DeploymentConcurrency.tla
```

Use a distinct `-metadir` per configuration. CI wraps the unsafe configurations
as expected failures. Its path-filtered workflow cannot become required until
it reports on every required pull-request event.

## Code mapping and drift control

Production paths below are relative to `src/prefect/server/`; lease operations
use `concurrency/lease_storage/ConcurrencyLeaseStorage`.

| Split-path counterexample actions | Production boundary |
| --- | --- |
| `BeginAcquire`, `CreateLease`, `CommitAcquire` | `core_policy.py::SecureFlowConcurrencySlots`; `models/concurrency_limits_v2.py::bulk_increment_active_slots`; lease storage `create_lease` |
| `Renew`, `Expire`, `ScanExpired`, `ReapRead`, `BeginReap`, `ReapRevoke`, `CommitReap` | `api/concurrency_limits_v2.py::renew_concurrency_lease`; `core_policy.py::ValidateDeploymentConcurrencyAtRunning`; lease deadlines and `renew_lease`/`read_expired_lease_ids`; `services/repossessor.py::{monitor_expired_leases, revoke_expired_lease}`; `models/concurrency_limits_v2.py::bulk_decrement_active_slots` |
| `CancelAfterLostLease`, `TerminalRead*`, `Begin*Release`, `ReleaseRevoke`, `Commit*Release` | `core_policy.py::{ValidateDeploymentConcurrencyAtRunning, _release_concurrency_lease, ReleaseFlowConcurrencySlots}`; lease storage `read_lease`/`revoke_lease`; `models/concurrency_limits_v2.py::bulk_decrement_active_slots` |
| `DeleteFlowRun` | `models/flow_runs.py::{cleanup_flow_run_concurrency_slots, delete_flow_run, delete_flow_runs}`; `models/concurrency_limits_v2.py::bulk_decrement_active_slots` |

The generic concurrency-limit helper mappings cover only calls from the listed
deployment protocol paths; public v2 slot API calls are excluded above.

`ClaimAcquire`, `ClaimReacquire`, `ClaimExpiryRelease`, `DiscardStaleExpiry`,
`ClaimTerminalRelease`, and `ClaimTerminalNoop` are an unimplemented
claim-module contract, not aliases for today's split paths. In the target,
`Renew`/`Expire`/`ScanExpired` use its SQL deadline and queued-work hint;
`CommitRunning` and `CancelAfterLostLease` project through
`ValidateDeploymentConcurrencyAtRunning`; `ClaimReacquire` models that rule's
successful PENDING reacquisition branch, covered by
`tests/server/orchestration/test_validate_deployment_concurrency_at_running.py::TestValidateDeploymentConcurrencyAtRunning::test_reacquires_slot_after_lease_expiry`.
`CancelStaleReap` and
`SkipFallbackRelease` are the proposed safe branches. `ClaimTerminalRelease`
also covers atomic claim release during flow-run deletion; `Terminal` abstracts
removal from protocol participation.

The two flow-run-state writes in an in-process `Running` -> `AwaitingRetry` ->
`Running` cycle refine to the stuttering alternative in
`[ClaimAuthorityNext]_vars`: concrete `AwaitingRetry` maps to abstract
`Running`. `RetryFailedFlows`, `ReleaseFlowConcurrencySlots`'s retry branch,
and `PreserveDeploymentConcurrencyLeaseId` leave the lease identity and occupied
slot unchanged, while the flow engine keeps lease renewal active during the
wait. Existing `Renew`, `Expire`, queued-release, and terminal actions retain
their guards and can interleave with that wait. The lease-preservation mapping
is covered by
`tests/server/orchestration/test_core_policy.py::TestFlowConcurrencyLimits::test_in_process_retry_transition_does_not_release_concurrency_slots`.

`runState` is the concurrency-relevant phase rather than a one-to-one flow-run
state projection; `stateLease` and `dbSlots` correspond to
`deployment_concurrency_lease_id` and `ConcurrencyLimitV2.active_slots`. The
claim and lease ownership/lifecycle fields are proposed SQL state in the target;
split-path models use ghost slot attribution around an external lease record.
Reaper phases and scan epochs track two independent work items per lease;
transaction and `bad*` fields expose in-flight or counterexample state.

| Counterexample | Production-boundary regression |
| --- | --- |
| stale expiry scan | `tests/server/services/test_repossessor.py::TestRevokeExpiredLease::test_does_not_revoke_lease_renewed_after_expiry_scan` |
| missing-lease fallback | `tests/server/orchestration/test_validate_deployment_concurrency_at_running.py::TestValidateDeploymentConcurrencyAtRunning::test_full_policy_missing_lease_release_preserves_replacement_slot` |
| read-present release | `tests/server/orchestration/test_validate_deployment_concurrency_at_running.py::TestValidateDeploymentConcurrencyAtRunning::test_terminal_release_racing_reaper_preserves_replacement_slot` |
| flow-run deletion | `tests/server/orchestration/test_validate_deployment_concurrency_at_running.py::TestValidateDeploymentConcurrencyAtRunning::test_flow_run_deletion_reaper_preserves_replacement_slot` |
| duplicate reapers | `tests/server/services/test_repossessor.py::TestRevokeExpiredLease::test_duplicate_reapers_preserve_replacement_capacity` |

These regressions are strict `xfail` tests while claim authority is absent.
Implementing the target requires removing those marks and passing the same
boundary assertions; lower-level replacements are insufficient.

Review the model when deployment or global concurrency changes admission,
renewal, expiry scanning, terminal release, flow-run deletion, lease
persistence, queue delivery, PENDING reacquisition, or accounting.
