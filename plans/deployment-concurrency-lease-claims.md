# Concurrency Lease Claim Authority

Status: proposed design; not implemented.

## Decision

Make a durable SQL claim the sole authority for concurrency-slot ownership.
Expose one deep server module with four operations:

```python
async def acquire(
    session: AsyncSession,
    *,
    lease_id: UUID,
    resources: Sequence[LeaseResource],
    ttl: timedelta,
    holder: ConcurrencyLeaseHolder | None = None,
) -> (
    LeaseGrant
    | AcquisitionDenied
    | LeaseLost
    | LeaseConflict
): ...

async def renew(
    session: AsyncSession,
    *,
    lease_id: UUID,
    ttl: timedelta,
) -> Renewed | LeaseLost | NonRenewable: ...

async def make_terminal_only(
    session: AsyncSession,
    *,
    lease_id: UUID,
    flow_run_id: UUID,
) -> TerminalOnly | LeaseLost | HolderMismatch: ...

async def release(
    session: AsyncSession,
    *,
    lease_id: UUID,
    cause: Literal["terminal", "expired", "orphaned"],
) -> (
    Released
    | AlreadyReleased
    | NotExpired
    | HolderStillActive
    | LeaseLost
    | UnknownLease
): ...
```

The caller supplies one stable UUID `lease_id` for each logical acquisition
attempt and reuses it after an unknown response. A replay with the same
canonical request returns the original live grant without incrementing again;
a denied attempt returns the original `AcquisitionDenied`; a released claim
returns `LeaseLost`; reuse for different resources, slots, or holder returns
`LeaseConflict`. A replay returns the original outcome and deadline and never
reapplies its `ttl`; changing the deadline is `renew`'s responsibility. After a
caller observes `AcquisitionDenied`, a later logical attempt uses a new ID.

Release callers provide only that lease identity, never fallback limit IDs or
slot counts. The module derives release accounting from the claim it owns.

For deployment admission, use the request's stable state `transition_id` as
the lease ID; claim mode rejects a transition without one. The generic leased
increment endpoint likewise accepts a caller-supplied ID. This keeps retry
identity outside the module instead of silently generating a new key after an
unknown response.

Claim-backed deployment leases are not mirrored to the configured memory,
filesystem, or Redis lease store. Claim-aware renewal, repossession, release,
and operational lookup read SQL. Existing stores remain the authority only for
limits still in `legacy` or `draining` mode.

## Why

The current protocol splits authority between the SQL `active_slots`
aggregate, external lease storage, flow-state lease references, and queued
repossessor work. Three deterministic regressions demonstrate the consequence:

1. queued reaper work can revoke a lease renewed after the expiry scan;
2. missing-lease fallback can decrement capacity now owned by a replacement
   lease;
3. terminal release and the reaper can both read one lease and both decrement
   it.

An atomic lease-store pop closes those three safety traces only while every
step succeeds. If the process or SQL transaction fails after the pop, the
ownership record needed for retry is gone. It is therefore a useful adapter
primitive, but not a sufficient claim or idempotency boundary.

## Invariants

- A lease ID names one immutable allocation set.
- Retrying acquisition with one lease ID cannot create a second allocation.
- Reusing a lease ID for a different request cannot change the original claim.
- Live-claim creation and `active_slots` increment commit in one SQL
  transaction.
- Exactly one `active -> released` transition may decrement an allocation.
- Claim release and `active_slots` decrement commit in one SQL transaction.
- An expiry release succeeds only when the current SQL deadline is non-null
  and expired.
- Renewal and release serialize on the same claim row; renewal cannot
  resurrect a released claim.
- Renewal cannot turn a terminal-only claim back into an expiring claim.
- Unknown, denied, stale, and already-released lease IDs never change
  accounting.
- A multi-limit acquisition and release are all-or-none.

These are safety invariants. Eventual reclamation additionally requires fair
retries and eventual SQL availability.

## Storage

Add two portable ORM tables plus a `lease_authority` mode on
`concurrency_limit_v2`, with paired SQLite and PostgreSQL migrations.
Existing and newly created limits default to `legacy`.

`concurrency_lease_claim`:

- `id`: caller-generated, externally visible lease UUID and primary key;
- `request_fingerprint`: canonical hash of resources, slots, and holder;
- `status`: denied, live, or released;
- `expires_at`: nullable authoritative deadline; null on a live claim is
  terminal-only;
- `holder`: optional holder metadata;
- fields needed to reconstruct the original `AcquisitionDenied` response;
- `released_at` and `release_reason`;
- `created` and `updated`.

Index live claims with non-null `expires_at`.

`concurrency_lease_claim_resource`:

- `lease_id`, foreign key to the claim;
- `concurrency_limit_id`, foreign key to `concurrency_limit_v2`;
- positive `slots`;
- unique `(lease_id, concurrency_limit_id)`.

The resource table retains generic multi-limit semantics without making
deployment callers understand them. Only live grants have resource rows.
Denied attempts never create them, and release deletes them in the same
transaction after using them for the decrement. Denied and released tombstones
therefore retain no foreign key to a concurrency limit.

## Transaction boundaries

`acquire` first reserves the caller's lease ID inside a savepoint. A concurrent
insert of the same ID serializes on the unique key. After a duplicate becomes
visible, the operation compares its request fingerprint and returns the
original grant, denial, `LeaseLost`, or `LeaseConflict` without touching
accounting. A new request locks requested limits in deterministic UUID order
and validates all capacity. A grant increments all counters, inserts the
resources, and returns the lease ID. Capacity denial changes no accounting but
retains the fingerprint and denial outcome under that lease ID, so a lost
denial response cannot later become a grant; it creates no resource rows. The
claim outcome and, for a grant, resources, counter increments, and flow-state
lease reference commit in one outer transaction before its response is sent.

After the audit window, denied or released claims may drop bulky diagnostic and
holder detail, but the ID, request fingerprint, and fields needed to reconstruct
the original outcome remain as a durable tombstone. The initial design never
deletes that tombstone, so a delayed retry cannot turn an old ID into a new
allocation. This is an explicit storage cost. Bounded pruning requires a
separately reviewed key-epoch protocol; do not add time-based deletion while
callers may replay an ID.

`renew` conditionally updates a live claim's non-null deadline. A denied or
released claim returns `LeaseLost`; a live terminal-only claim returns
`NonRenewable`. An expired live claim may be renewed until an expiry release
wins the claim transition; whichever SQL update linearizes first wins.

`make_terminal_only` locks a live claim, verifies that its holder is the given
flow run, and sets `expires_at` to null. A denied or released claim returns
`LeaseLost`. The old-client `PENDING -> RUNNING` rule invokes it inside the
state-transition transaction. It cannot target a generic or differently held
claim.

`release` conditionally marks one live claim released. A denied claim returns
`LeaseLost`, and a released claim returns `AlreadyReleased`; neither changes
accounting. Only the caller whose live-claim update returns a row decrements the
recorded resources, records occupancy, and deletes those resource rows in the
same transaction. For `cause="expired"`, the update also requires
`expires_at IS NOT NULL AND expires_at <= database_now`.

For `cause="orphaned"`, the module locks the claim and checks its flow-run
holder in the same SQL transaction. It may release only when that run is
terminal or absent; otherwise it returns `HolderStillActive`. The reconciler
does not make this decision outside the module.

The state transition, claim transition, and aggregate accounting use the
caller's transaction. A SQL failure rolls them all back.

## No dual-write projection

Mirroring claims into every configured lease store would require durable
per-adapter generations, delivery cursors, tombstones, and full rebuilds. A
single SQL `projected_revision` cannot represent a restarted process-local
memory store or a configuration switch. No claim-path consumer requires that
second copy once renewal, repossession, release, and lookup use SQL, so this
design does not create it.

During migration, lease-ID routing checks SQL first. If no claim or retained
claim tombstone exists, the legacy adapter may be consulted only while every
referenced limit is `legacy` or `draining`. A missing legacy record never
authorizes fallback accounting. After a limit reaches `claim`, stale external
records are ignored. Any future requirement for an external claim projection
needs a separate outbox/generation design and model review.

## Caller migration

Roll out the generic schema and module to deployment concurrency first:

1. `SecureFlowConcurrencySlots` obtains one stable UUID per proposed-state
   attempt, calls `acquire`, and stores it in the same state transaction. A
   retried request must reuse that UUID rather than regenerate it.
2. `ValidateDeploymentConcurrencyAtRunning` calls `renew`, then `acquire` with
   a fresh UUID only after `LeaseLost`.
3. The old-client running transition calls `make_terminal_only`. If expiry
   release already won and it returns `LeaseLost`, derive a fresh, retry-stable
   UUIDv5 from the transition ID and the fixed name `terminal-only-reacquire`,
   call `acquire`, and convert that new claim to terminal-only in the same outer
   transaction. Update the proposed state to the new lease ID. If capacity is
   unavailable, reject the transition with a cancelled state; never admit an
   unbacked running flow. `HolderMismatch` is an internal consistency error,
   not a reason to continue.
4. `ReleaseFlowConcurrencySlots` calls `release(cause="terminal")`.
5. The repossessor scans authoritative SQL deadlines and calls
   `release(cause="expired")` with a keyed Docket task.
6. Flow-run deletion uses the same release operation.
7. The renewal API reads and updates SQL claims.
8. Generic `increment-with-lease` and `decrement-with-lease` may move behind
   the same interface for `mode="concurrency"` only after deployment behavior
   and write load are validated. Decaying `mode="rate_limit"` accounting stays
   outside this claim protocol.

A concurrency-limit row cannot mix claim-backed and anonymous accounting. Add
a per-limit authority mode with `legacy`, `draining`, and `claim` states.
`draining` rejects new reservations while allowing existing legacy holders to
renew and release. `claim` transactionally rejects aggregate-only
increment/decrement paths, and rate-limit mode is never eligible. Until every
writer for a limit carries a claim ID, that limit remains outside the target
model's guarantees.

Enforce the mode in the concurrency-limit model layer, not only at HTTP or
orchestration callers. Claim acquisition requires every locked limit to be in
`claim` mode with `slot_decay_per_second = 0`. In `claim` mode:

- only the claim module may increment or decrement `active_slots`;
- direct updates or resets of `active_slots` are rejected;
- changing `slot_decay_per_second` away from zero is rejected;
- lowering `limit` below the currently claimed slots is rejected; and
- deletion is rejected while any live claim references the limit.

The claim module uses identity-bearing internal statements; it does not bypass
these checks through the existing anonymous bulk helpers. Portable check
constraints backstop the mode/decay combination, and foreign keys prevent
unsafe deletion while a live claim has resource rows. The model layer remains
the single boundary for aggregate mutation.

Every legacy admission path locks the limit row and checks this mode before it
increments. The cutover transaction takes the same lock, requires
`lease_authority = "draining"` and `active_slots = 0`, then changes the mode to
`claim`. Observed zero external leases is an operational prerequisite; the
locked zero aggregate plus fenced writers is the atomic accounting gate.

Legacy external-only leases cannot be inferred from `active_slots`; the
aggregate does not identify owners. Deploy the claim code dormant, establish
the required client version floor, move one eligible limit to `draining`, and
wait until both its observed legacy leases and `active_slots` are zero. Then
switch it atomically to `claim` and resume admissions. Never synthesize a claim
or fallback-decrement when a legacy lease is missing.

If a missing legacy record leaves `active_slots` stranded, cutover remains
blocked. An operator may reset it only in `draining` mode, with admissions
fenced and independent evidence that no holder is active; this is an explicit
recovery action, not an automatic fallback.

Elapsed TTL alone cannot prove drain because legacy leases can renew
indefinitely. Enabling a limit therefore requires both a versioned writer
cutover and observed zero legacy ownership, achieved by a coordinated client
version floor and, if necessary, a maintenance window. A system that cannot
pause admissions or drain long-running work needs a separately designed
adoption protocol; it may not silently enter a mixed mode. Older clients that
carry no stable transition ID stay on the legacy side of the version floor.
Clients that carry a stable ID but do not renew deployment leases need a
terminal-only SQL claim after cutover: at
`PENDING -> RUNNING`, set `expires_at` to null and retain the claim identity for
terminal release instead of leaving an expiring claim. Full authority begins
only after every writer is claim-aware and the legacy population is verified
empty.

A terminal-only claim trades automatic expiry for safety. Flow-run deletion
releases it in the deletion transaction, and a reconciler may call
`release(cause="orphaned")` only after the authoritative flow run is terminal
or absent. A nonterminal run with no trustworthy liveness signal cannot be
safely reclaimed: deployments that require bounded automatic reclamation must
enforce the lease-aware client version floor instead of using terminal-only
claims.

## Failure behavior

| Failure | Required outcome |
| --- | --- |
| SQL transaction rolls back | state, claim, and counters all remain unchanged |
| Expiry release linearizes while the renewed deadline is future | `NotExpired`; no accounting change |
| Renewal and expiry release contend on the claim | renewal returns `Renewed` or `LeaseLost` according to the winner |
| Terminal and expiry release race | one returns `Released`; the other returns `AlreadyReleased` |
| Unknown lease ID | no decrement |
| Missing legacy record leaves a nonzero aggregate | block cutover; require audited draining-mode recovery |
| Duplicate acquire after response loss | original grant is replayed; no second increment |
| Duplicate acquire after a lost denial response | original denial is replayed, even if capacity is now available |
| Lease ID reused with different request | `LeaseConflict`; no accounting change |
| Renew, convert, or release targets a denied claim | `LeaseLost`; no accounting change |
| Aggregate-only write targets a claim-authoritative limit | rejected |
| Rate-limit request reaches claim module | rejected |
| Direct slot/decay reset targets a claim-authoritative limit | rejected |
| Limit reduction would undercut live claims | rejected |
| Deletion targets a limit with live claims | rejected |
| Terminal-only holder is terminal or deleted | orphan reconciliation releases once |
| Terminal-only holder is nonterminal and liveness is unknown | preserve claim; surface stranded-capacity telemetry |
| Renewal targets a terminal-only claim | `NonRenewable`; deadline stays null |
| Expiry release wins before terminal-only conversion | atomically reacquire and convert, or cancel if denied |

## Verification and rollout gate

The three strict `xfail` regressions map to the repository TLA+ counterexample
configurations. An implementation is not complete until it removes the marks
and makes each assertion pass through the same public service or orchestration
boundary.

Before enabling SQL authority:

- run claim-module contract tests against SQLite and PostgreSQL;
- verify transaction rollback after a winning conditional release;
- verify multi-limit partial denial creates no accounting or resource rows;
- verify duplicate acquisition before and after commit, including a lost reply;
- verify a lost denial response remains denied after capacity becomes available;
- verify a duplicate lease ID with a different fingerprint is rejected;
- verify replay still returns denied and released outcomes after compaction;
- verify renew, terminal conversion, and release cannot mutate a denied claim;
- verify claim-authoritative limits reject anonymous and rate-limit writes;
- verify direct updates, resets, unsafe limit reductions, and deletes are fenced;
- verify terminal-only reconciliation requires terminal or absent flow state;
- race expiry release against old-client terminal-only conversion, covering
  both successful reacquisition and capacity denial;
- run the target TLC configuration and all three expected counterexamples;
- document indefinite ID-tombstone retention plus stranded-capacity observability.
