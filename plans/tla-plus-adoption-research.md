# TLA+ Adoption Research

## Recommendation

Use **TLA+**, Leslie Lamport's formal specification language, for one bounded
pilot: Prefect's **deployment-concurrency lease protocol**. This is unrelated
to test-impact analysis or `pytest-tia`.

TLA+ describes a system as states and allowed state transitions, then TLC
checks properties across the reachable behaviors. It is intended for designs
above the code level, especially concurrent and distributed systems
([Lamport, *A High-Level View of TLA+*][high-level]). It does not verify that
Python faithfully implements the model.

The pilot should answer one concrete question:

> Across admission, state persistence, renewal, retry, release, expiry,
> repossession, duplication, and process failure, can Prefect over-admit work,
> release another run's capacity, or strand capacity permanently?

Do not model the whole orchestration engine or make TLA+ a repository-wide
requirement yet.

The repository review candidate answers a narrower safety slice: three
renewal/release interleavings and the proposed SQL claim authority. It does not
yet model transport reply loss, arbitrary process failure, legacy-store
migration, or eventual reclamation. Those remain explicit adoption work rather
than conclusions of the current green TLC run.

## Why This Protocol

Deployment-concurrency authority is split across three durable surfaces:

1. The database aggregate `active_slots` atomically decides admission
   ([model][slot-model]).
2. Separate lease storage records expiry, resource IDs, slot count, and holder
   identity ([lease contract][lease-storage]).
3. Flow state stores `deployment_concurrency_lease_id`, which the engine renews
   and orchestration later releases ([state schema][state-schema]).

The repossessor observes expired lease IDs, queues work, then separately reads
the lease, decrements the database, and revokes the lease
([repossessor][repossessor]). Terminal release follows another read, decrement,
and revoke sequence ([core policy][core-policy]). There is no transaction across
the database, lease store, flow state, engine, and queued repossessor.

That is a compact distributed protocol with meaningful crash and interleaving
boundaries. TLA+ can exhaust those boundaries with a tiny state space, while
pytest should retain concrete regression tests for relevant counterexamples.

## Pilot Model Envelope

### Bounds

The full pilot should grow toward:

- `Runs = {r1, r2}`;
- one deployment and one non-decaying limit;
- capacity one, with capacity two as a second TLC configuration;
- two or three reusable lease IDs;
- lease-aware clients only;
- a bounded logical clock;
- one repossessor with zero to two queued jobs per lease;
- failure or response loss between every database, lease-store, and state
  persistence step.

Small finite instances are intentional: TLC exhausts a finite model of the
specification rather than simulating production load
([Lamport, *TLA+ Models vs. TLC Models*][tlc-models]).

### State

Suggested variables:

- `runState[r]` — scheduled, acquiring, pending, submitting, running,
  awaiting-retry, cancelling, or terminal;
- `stateLease[r]` — lease ID or none;
- `leaseStatus[l]` — absent, active, expired, or revoked;
- `leaseOwner[l]`, `leaseDeadline[l]`;
- `dbSlots` and a ghost `slotClaim[r]` expressing logical ownership;
- `operationPhase[r]` for partially completed acquire/release operations;
- `reapJobs[l]`, `processAlive[r]`, and bounded `now`.

Keep database accounting, lease storage, flow state, and queued work distinct.
Do not encode SQL, Redis commands, HTTP, Python functions, threads, or exact
wall-clock durations unless they change the protocol.

### Actions

Name actions after observable Prefect boundaries so TLC traces remain useful:

| Model action | Production boundary |
|---|---|
| `ReserveSlot` | Atomic conditional database increment |
| `CreateLease` | External lease-store write |
| `CommitPending` / `RollbackPending` | Persist or abandon the state transition |
| `PreserveLeaseRef` | Carry the lease reference across states and retries |
| `Tick` | Advance bounded logical time |
| `RenewLease` | Engine/API renewal |
| `ScanExpired` | Snapshot expired IDs and enqueue repossessor work |
| `ReapRead` / `ReapDecrement` / `ReapRevoke` | Split queued repossession at await boundaries |
| `ValidatePendingToRunning` | Renew or reacquire before execution |
| `ReleaseRead` / `ReleaseDecrement` / `ReleaseRevoke` | Split terminal cleanup |
| `CrashOrLoseReply` | Fail between cross-store steps or retry an unknown result |

### Properties

Check `TypeOK` and these safety properties first:

- `CapacitySafety`: logical owners never exceed the deployment limit.
- `CounterBounds`: `0 <= dbSlots <= Limit`.
- `NoUnbackedRunning`: a lease-aware running flow owns and references a live
  claim.
- `ExactlyOnceRelease`: one claim can affect accounting at most once.
- `NoForeignRelease`: cleanup for run A cannot reduce run B's claim.
- `StableAccounting`: outside named in-flight phases, the database count equals
  outstanding logical claims.
- `LeaseRefContinuity`: pending, submitting, running, and in-process retry keep
  the reference until explicit release.
- `RenewWinsAgainstStaleScan`: queued expiry work cannot revoke a lease renewed
  before revocation's linearization point.
- `TerminalNoClaim`: a terminal run eventually has no reference, lease, or
  slot claim.

Add liveness only after safety is stable. Any eventual reclamation property
must state weak-fairness and eventual database/storage availability
assumptions; otherwise the model promises more than the service can guarantee.
Lamport distinguishes safety from liveness and explains why fairness must be
explicit ([high-level view][high-level]).

## Traces to Challenge First

Static inspection suggests these model traces. They are **hypotheses to check**,
not runtime-confirmed defects:

1. `ScanExpired(A); Renew(A); Reap(A)`: queued expiry work reads the renewed
   lease without visibly rechecking expiry before decrement/revoke
   ([repossessor][repossessor]).
2. `Reap(A); Acquire(B); ValidateAndCancel(A); ReleaseFallback(A)`: after B
   takes the freed capacity, fallback release for A may act on the aggregate
   limit rather than A's absent lease ([core policy][core-policy]).
3. `ReleaseRead(A); ReapRead(A); ReleaseDecrement(A); ReapDecrement(A)`: two
   cleanup paths observe the same lease before either revokes it.
4. `ReserveSlot; CreateLeaseFailure`: the generic lease endpoint commits its
   database increment before external lease creation
   ([API][lease-api]).
5. `ReserveSlot; CreateLease; RollbackPending`: orchestration creates an
   external lease inside a database-backed state transition that can still
   fail or roll back.

Translate any relevant counterexample into a focused pytest regression using
deterministic barriers, not sleeps. Existing lease-validation coverage exercises
important pieces but does not establish every full-policy interleaving
([tests][validation-tests]).

Before trusting a green model, deliberately remove a critical guard and show
that TLC finds the expected counterexample. The official examples project asks
for short-running models and, where possible, an interesting failing model
([examples guidance][examples-guidance]).

## Repository Rollout

### Phase 0: ignored local experiment

The repository already ignores `.planning/`. Use it to prove the model is
worth maintaining without creating a committed toolchain:

```text
.planning/
├── tla-tools/tla2tools.jar
├── tla/deployment-concurrency/
│   ├── DeploymentConcurrency.tla
│   └── DeploymentConcurrency.cfg
└── tlc/deployment-concurrency/
```

For the local experiment, OpenJDK 21.0.12.1 is installed through Homebrew at
`/opt/homebrew/opt/openjdk@21/bin/java`. It is intentionally not linked into
the system Java wrappers or added to the user's shell profile. The official
tools require Java 11 or newer and run from the release JAR
([official CLI instructions][use]).

Pin stable TLA+ tools `v1.7.4` rather than the moving `v1.8.0` prerelease:

```bash
mkdir -p .planning/tla-tools .planning/tlc/deployment-concurrency
curl --fail --location --silent --show-error \
  https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar \
  --output .planning/tla-tools/tla2tools.jar
echo "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88  .planning/tla-tools/tla2tools.jar" \
  | shasum -a 256 -c -
java -XX:+UseParallelGC \
  -jar .planning/tla-tools/tla2tools.jar \
  -workers 1 \
  -metadir .planning/tlc/deployment-concurrency \
  -config formal/tla/deployment-concurrency/DeploymentConcurrency.cfg \
  formal/tla/deployment-concurrency/DeploymentConcurrency.tla
```

The SHA-256 above was recomputed from the official release asset on
2026-09-03. The optional VS Code extension provides editing, TLC execution, and
trace visualization on top of the official tools
([extension][vscode-extension]). Do not standardize on the unmaintained Eclipse
Toolbox ([tools repository][tools-repository]).

The ignored Phase 0 experiment completed on 2026-09-03. Its guarded prototype
passed 21,663 distinct states in under one second. After refinement, the
SQL-claim target passed 2,087 distinct states at depth 15 in under one second.
Three negative configurations representing two disabled authority guards and
the current read-before-release ordering produced the intended
counterexamples: delayed repossessor work revoked a renewed lease,
missing-lease aggregate fallback consumed a replacement holder's accounting,
and terminal release raced the reaper to decrement one lease twice.

All three traces now have deterministic strict-`xfail` pytest regressions whose
expected failures are limited to dedicated exception types. The missing-lease
and read-present paths exercise the complete `CoreFlowPolicy`; the latter uses
independent database sessions and explicit async barriers rather than sleeps.
The marks make known failures visible without making the test suite red and
turn a future fix into an `XPASS(strict)` failure; setup, timeout, and harness
failures remain ordinary failures.

The interface design in `plans/deployment-concurrency-lease-claims.md` makes a
durable SQL claim the release authority and keeps external lease storage on the
legacy path instead of introducing a dual-write projection. This is broader
than adding a local expiry check, but it is the smallest boundary that makes
release idempotent and SQL rollback repairable. The target model specifies
that interface; it is not evidence that production implements it.

### Phase 1: repository review candidate

The model met the local counterexample and runtime criteria, so the executable
review candidate is proposed at:

```text
formal/tla/deployment-concurrency/
├── DeploymentConcurrency.tla
├── DeploymentConcurrency.cfg
├── CounterexampleFallbackRelease.cfg
├── CounterexampleReadPresentRelease.cfg
├── CounterexampleStaleReap.cfg
└── README.md
```

The README defines the question, non-goals, bounds, atomicity and fairness
assumptions, action-to-code mapping, invariants, exact command, expected
results, regression mapping, owner, and review trigger.

The model is not in `tests/`, `pyproject.toml`, `uv.lock`, or the production
Docker image. No pre-commit hook is added; that would impose Java and JAR
acquisition on every contributor.

This is not yet an adopted contract. Owner review remains open, and the
path-filtered workflow below is not a required check until that review occurs.

### Phase 2: advisory CI

The review candidate includes one dedicated, path-filtered workflow:

- Temurin JDK 21;
- pinned `tla2tools.jar` `v1.7.4` with the checksum above;
- TLC metadata under `$RUNNER_TEMP`;
- `contents: read` and a short timeout;
- triggers only for `formal/tla/**` and the workflow itself at first;
- runs the target as expected-green and verifies that each negative
  configuration exits with the expected invariant violation.

Rerunning an unchanged abstract model on every Python change would not prove
implementation conformance. Add mapped implementation paths only after the
team adopts an explicit review rule or a stronger trace/refinement link. Make
the job blocking only after runtime and model ownership are stable. If it later
becomes a globally required check, make the workflow report a successful no-op
for unrelated changes instead of relying on a path filter that can leave a
required check pending.

No wrapper script, `just` target, Apalache, or TLAPS is needed for the first
model. Add shared plumbing only after a second model creates actual reuse.

## Adoption Criteria

The review candidate earns adoption and blocking CI promotion when:

- a deployment-concurrency owner reviews the model boundary and invariants;
- the exhaustive safety model finishes in under ten seconds in CI;
- at least one intentional unsafe mutation produces the expected trace;
- every action maps to code or is explicitly an environment action;
- relevant counterexamples become focused behavior-level Python tests;
- assumptions, ownership, and update triggers are documented;
- maintainers explicitly decide to expand, revise, or remove the experiment.

TLA+ checks the model, not Prefect. A wrong abstraction can pass, finite TLC
instances are not a proof for all cardinalities, and liveness is only as strong
as its fairness assumptions. Those limitations belong in the model README.

## Primary Sources

- Leslie Lamport, [*A High-Level View of TLA+*][high-level]
- Leslie Lamport, [TLA+ learning resources][learning]
- TLA+ Foundation, [tools repository][tools-repository] and [command-line
  instructions][use]
- TLA+ Foundation, [validated examples][examples]
- TLA+ Foundation, [VS Code extension][vscode-extension]

[high-level]: https://lamport.azurewebsites.net/tla/high-level-view.html
[learning]: https://lamport.azurewebsites.net/tla/learning.html
[tlc-models]: https://lamport.azurewebsites.net/tla/model-popup.html
[tools-repository]: https://github.com/tlaplus/tlaplus
[use]: https://github.com/tlaplus/tlaplus/blob/master/USE.md
[examples]: https://github.com/tlaplus/Examples
[examples-guidance]: https://github.com/tlaplus/Examples/blob/master/CONTRIBUTING.md
[vscode-extension]: https://github.com/tlaplus/vscode-tlaplus
[slot-model]: ../src/prefect/server/models/concurrency_limits_v2.py#L253-L327
[lease-storage]: ../src/prefect/server/concurrency/lease_storage/__init__.py#L21-L67
[state-schema]: ../src/prefect/server/schemas/states.py#L81-L103
[repossessor]: ../src/prefect/server/services/repossessor.py#L27-L86
[core-policy]: ../src/prefect/server/orchestration/core_policy.py#L79-L109
[lease-api]: ../src/prefect/server/api/concurrency_limits_v2.py#L337-L388
[validation-tests]: ../tests/server/orchestration/test_validate_deployment_concurrency_at_running.py#L249-L347
