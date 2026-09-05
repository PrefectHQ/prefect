# TLA+ Protocol Models

Add a model only when a bounded concurrency question can change a design or
preserve a regression that cheaper tests cannot establish.

## Model contract

- Label each configuration as current, target, or intentionally unsafe. Model
  or isolate current failure behavior before a repair; a target remains a
  proposal until mapped production tests pass.
- Keep independently durable stores, queues, transactions, and clocks distinct
  unless production makes them atomic. State fairness and availability
  assumptions; never infer liveness from a safety-only run.
- For each design-critical safety claim, include an unsafe configuration that
  violates the exact named invariant, with bounds that admit the contested
  trace and make critical actions reachable.

Each model README records its question, owner, bounds, assumptions and
exclusions, configuration status, invariants, commands and expected results,
action/state-to-production mapping, and review triggers. Every production
writer of modeled state must map to an action or be explicitly out of scope.

Translate relevant counterexamples into deterministic behavior tests using
explicit barriers, not sleeps. A target is implemented only when mapped
contract tests pass; check database locking or serialization against
PostgreSQL. Keep the model and its test oracle independent of production code.

## CI and lifecycle

- Fix the JDK distribution and major version in CI and document the matching
  local major. Pin and checksum the TLA+ tool release. Run targets as
  expected-green and verify each unsafe configuration's exact exit and named
  invariant. Do not commit tool JARs or TLC metadata.
- Keep a new check advisory until its owner accepts the scope, invariants,
  runtime, and diagnostics.
- Remove an unowned, unmappable, or obsolete model and its dedicated CI;
  preserve useful production regressions.
