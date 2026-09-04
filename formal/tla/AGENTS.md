# TLA+ Protocol Models

TLA+ is executable design evidence, not proof that Prefect's implementation
conforms to a model.

## Selection

Add or expand a model only when:

- correctness depends on concurrency, retries, duplication, reordering,
  crashes, time, or authority split across durable systems;
- the model answers one named question with explicit safety or liveness
  properties that ordinary tests cannot establish cheaply;
- every action maps to a production interface or a named environment action;
- a domain maintainer owns the model and its mapped tests; and
- the result can change a design, reject an unsafe alternative, or preserve a
  concrete regression.

Do not model whole subsystems, ordinary CRUD, implementation syntax, or a
known defect already covered completely by cheaper tests.

## Development

- Keep one protocol per directory. Label every configuration as current,
  target, or an intentional unsafe mutation.
- Model current behavior before a proposed repair. A target configuration is a
  proposal until mapped production tests pass.
- Keep independently durable stores, queues, transactions, and clocks distinct
  unless production gives them one atomic authority.
- Give each critical invariant an unsafe configuration that violates that
  exact invariant, and choose finite bounds that admit the contested trace.
- State fairness and availability assumptions. Never infer liveness from a
  safety-only run.

## Model-to-code Mapping

Each model README must record its question, owner, bounds, assumptions,
exclusions, configuration status, invariants, commands, expected results, and
review triggers. Map every state variable and action to observable production
state, a production interface, or an environment action.

Every production writer of modeled state must map to an action or be explicitly
outside the modeled authority. Prefer one narrow owning module whose interface
matches the model actions; prevent other writers from bypassing it.

Translate relevant counterexamples into deterministic behavior-level pytest
regressions using explicit barriers rather than sleeps. Before calling a target
implemented, add contract tests at the owning interface and run database
serialization or locking cases against PostgreSQL. Use a test-only refinement
mapping when concrete state must be compared with abstract model state.

Do not generate the model from production code or share implementation
predicates with the test oracle. Independence is what lets the model expose a
design error.

## CI and Maintenance

- Pin the JDK and TLA+ tools and verify downloaded artifacts by checksum.
- Require target configurations to pass and wrappers to verify each unsafe
  configuration's exact exit status and violated invariant.
- Describe checks as model checks, never implementation verification. Mapped
  code changes must also run their contract and behavior tests.
- Keep checks advisory until the domain owner accepts the scope, invariants,
  runtime, and diagnostics.
- Do not commit tool JARs or TLC metadata.
- Remove a model and its dedicated CI when its protocol is abandoned, no owner
  remains, the production mapping cannot be maintained, or a stronger artifact
  replaces it. Preserve useful production regressions.
