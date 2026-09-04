# Deployment concurrency TLA+ model

This bounded safety model asks whether deployment-concurrency cleanup can
revoke a renewed lease or decrement capacity owned by another run. It also
specifies the intended claim-authority boundary described in
[`plans/deployment-concurrency-lease-claims.md`](../../../plans/deployment-concurrency-lease-claims.md).

TLA+ specifies a protocol, not its Python implementation. Every relevant
counterexample here has a deterministic pytest counterpart at the production
service or orchestration boundary.

## Scope

The model has two lease-aware runs, two unique lease IDs, one static
non-decaying limit of capacity one, bounded lease revisions, nondeterministic
expiry, terminal release, and queued expiry release.

`claim`, `leaseOwner`, and the lease-lifecycle fields mean different things by
configuration:

- In `DeploymentConcurrency.cfg`, `CounterexampleStaleReap.cfg`, and
  `CounterexampleFallbackRelease.cfg`, `claim`, `leaseOwner`, `leaseState`, and
  `epoch` model the proposed durable SQL claim and its authoritative deadline.
  A claim identity is the only authority allowed to decrement its allocation.
- In the read-present release-order counterexample, they are ghost state that
  makes visible which logical reservation the current aggregate-only release
  sequence consumed; `leaseState` is the current external lease record.

The target claim path does not write or read the external memory, filesystem,
or Redis lease store, so the model does not include it. Those stores remain
legacy-only during migration and cannot enable a target action here.

## Configurations

- `DeploymentConcurrency.cfg` is the target protocol. Expiry release checks
  the authoritative current deadline, missing external records never trigger
  aggregate fallback, and a decrement requires a live claim. It must pass.
- `CounterexampleStaleReap.cfg` deliberately disables the target protocol's
  current-deadline guard, representing queued repossessor work that does not
  atomically revalidate expiry. It must violate `RenewWinsAgainstStaleScan`.
- `CounterexampleFallbackRelease.cfg` deliberately disables the target
  protocol's live-claim requirement, representing missing-lease cleanup that
  decrements a deployment aggregate. It must violate `NoForeignRelease` after
  another run acquires the freed capacity.
- `CounterexampleReadPresentRelease.cfg` represents terminal cleanup that
  reads a lease, loses the release race, then applies its stale aggregate
  decrement after another run acquires. It must violate `NoForeignRelease`.

The counterexample configurations are successful checks when TLC reports the
named invariant violation. They must not be run as ordinary expected-green
jobs without a wrapper that verifies the expected invariant.

## Run locally

TLA+ tools v1.7.4 is the pinned model-checker version. The tool JAR is not
committed. Download it from the official release and verify SHA-256
`936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`.

From the repository root:

```bash
java -XX:+UseParallelGC -jar .planning/tla-tools/tla2tools.jar \
  -workers 1 \
  -metadir .planning/tlc/deployment-concurrency/target \
  -config formal/tla/deployment-concurrency/DeploymentConcurrency.cfg \
  formal/tla/deployment-concurrency/DeploymentConcurrency.tla
```

`java` must resolve to JDK 11 or newer. `JAVA_HOME/bin/java` works when the JDK
is not on `PATH`; the local Homebrew experiment used
`/opt/homebrew/opt/openjdk@21/bin/java`. Use a distinct metadata directory for
every configuration.

The advisory GitHub Actions workflow at
`.github/workflows/tla-plus.yaml` runs the target and verifies each expected
counterexample when this model or the workflow changes. It downloads the same
pinned JAR and verifies its checksum rather than committing the tool.

## Expected results

Observed on 2026-09-03 with OpenJDK 21.0.12.1 and TLC 2.19:

- target: 2,087 distinct states, depth 15, no invariant violation, under one
  second;
- stale reaper: `RenewWinsAgainstStaleScan` violation at depth 6;
- missing fallback: `NoForeignRelease` violation at depth 7;
- read-present race: `NoForeignRelease` violation at depth 17.

The target result is exhaustive only for these finite bounds.

## Properties

- `TypeOK`: every variable remains in its declared finite domain.
- `CounterBounds`: the aggregate stays between zero and the limit.
- `ClaimCapacitySafety`: live logical claims do not exceed capacity.
- `OwnershipConsistent`: every live claim names its owning run and state
  reference.
- `AccountingConsistent`: outside no hidden state, `dbSlots` equals live
  claims.
- `NoForeignRelease`: release for one lease cannot consume another lease's
  capacity.
- `RenewWinsAgainstStaleScan`: a renewal that leaves the authoritative claim
  unexpired at expiry release's linearization point fences queued stale work.

## Code and regression mapping

| Model boundary | Production boundary | Regression |
| --- | --- | --- |
| acquire and commit | `SecureFlowConcurrencySlots` | future claim-module contract |
| renew | `ValidateDeploymentConcurrencyAtRunning` and renewal API | stale-reaper pytest |
| scan and expiry release | `services/repossessor.py` | stale-reaper pytest |
| terminal release | `_release_concurrency_lease` and `ReleaseFlowConcurrencySlots` | two release-race pytests |
| claim decrement | proposed concurrency-claim module | all three pytests |

The regressions are strict `xfail` tests while production lacks claim
authority. Implementing the design must remove those marks and make the same
assertions pass; replacing them with lower-level tests is not sufficient.

## Interpretation limits

This model checks safety, not liveness. It excludes rate limits, legacy
clients and stores, lease-ID reuse, holder indexing, SQL outages, and arbitrary
cardinalities. It also bounds logical claims, not the brief physical overlap
possible while a process reacts to lease loss.

Acquire, renew, and release are modeled as SQL-authoritative transitions. The
model does not yet cover acquisition-response delivery or replay; the design's
caller-supplied lease ID and request fingerprint require separate contract
tests before implementation. Adding an external claim projection would require
a new outbox/generation design and model review. Eventual reclamation requires
explicit fairness and eventual availability assumptions before it can be added
as a temporal property.

Owner: Prefect server orchestration maintainers.

Review this model whenever deployment or global concurrency changes admission,
renewal, expiry scanning, terminal release, lease persistence, or aggregate
accounting.
