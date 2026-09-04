---------------------- MODULE DeploymentConcurrency ----------------------
EXTENDS Naturals, FiniteSets, TLC

(***************************************************************************)
(* A bounded safety model of Prefect's deployment-concurrency lease        *)
(* protocol. In ClaimAuthoritySpec, claim, leaseOwner, leaseState, and      *)
(* epoch model the proposed durable SQL claim authority. The stale-reaper   *)
(* and fallback configurations deliberately disable target guards. In the  *)
(* read-present release-order spec, claim and leaseOwner are ghost state and *)
(* leaseState is the current external record. The target never mirrors      *)
(* claims into external lease storage.                                      *)
(***************************************************************************)

CONSTANTS
    Runs,
    LeaseIds,
    Limit,
    MaxEpoch,
    NoRun,
    NoLease,
    RecheckExpiryAtRevoke,
    FallbackDecrementsAggregate,
    RequireClaimForDecrement

ASSUME /\ Runs # {}
       /\ LeaseIds # {}
       /\ Limit \in Nat \ {0}
       /\ MaxEpoch \in Nat \ {0}
       /\ NoRun \notin Runs
       /\ NoLease \notin LeaseIds
       /\ RecheckExpiryAtRevoke \in BOOLEAN
       /\ FallbackDecrementsAggregate \in BOOLEAN
       /\ RequireClaimForDecrement \in BOOLEAN

RunStates == {"Scheduled", "Pending", "Running", "Cancelled", "Terminal"}
LeaseStates == {"Unused", "Live", "Expired", "Absent"}
ReapPhases == {"Idle", "Queued", "Read"}
ReleasePhases == {"Idle", "ReadPresent", "ReadMissing"}
TxnKinds == {
    "None",
    "Acquire",
    "Reap",
    "ReapRevoked",
    "ReleasePresent",
    "ReleaseRevoked",
    "ReleaseMissing"
}

VARIABLES
    runState,
    stateLease,
    leaseState,
    leaseOwner,
    epoch,
    claim,
    dbSlots,
    reapPhase,
    scanEpoch,
    releasePhase,
    txnKind,
    txnRun,
    txnLease,
    badForeignDecrement,
    badStaleReap

vars == <<
    runState,
    stateLease,
    leaseState,
    leaseOwner,
    epoch,
    claim,
    dbSlots,
    reapPhase,
    scanEpoch,
    releasePhase,
    txnKind,
    txnRun,
    txnLease,
    badForeignDecrement,
    badStaleReap
>>

Claims == {l \in LeaseIds : claim[l]}
OtherClaim(l) == \E other \in LeaseIds \ {l} : claim[other]
Decrement(n) == IF n = 0 THEN 0 ELSE n - 1

Init ==
    /\ runState = [r \in Runs |-> "Scheduled"]
    /\ stateLease = [r \in Runs |-> NoLease]
    /\ leaseState = [l \in LeaseIds |-> "Unused"]
    /\ leaseOwner = [l \in LeaseIds |-> NoRun]
    /\ epoch = [l \in LeaseIds |-> 0]
    /\ claim = [l \in LeaseIds |-> FALSE]
    /\ dbSlots = 0
    /\ reapPhase = [l \in LeaseIds |-> "Idle"]
    /\ scanEpoch = [l \in LeaseIds |-> 0]
    /\ releasePhase = [r \in Runs |-> "Idle"]
    /\ txnKind = "None"
    /\ txnRun = NoRun
    /\ txnLease = NoLease
    /\ badForeignDecrement = FALSE
    /\ badStaleReap = FALSE

BeginAcquire(r, l) ==
    /\ txnKind = "None"
    /\ runState[r] = "Scheduled"
    /\ leaseState[l] = "Unused"
    /\ dbSlots < Limit
    /\ txnKind' = "Acquire"
    /\ txnRun' = r
    /\ txnLease' = l
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, reapPhase, scanEpoch, releasePhase,
        badForeignDecrement, badStaleReap
        >>

CreateLease ==
    /\ txnKind = "Acquire"
    /\ leaseState[txnLease] = "Unused"
    /\ leaseState' = [leaseState EXCEPT ![txnLease] = "Live"]
    /\ leaseOwner' = [leaseOwner EXCEPT ![txnLease] = txnRun]
    /\ epoch' = [epoch EXCEPT ![txnLease] = 1]
    /\ UNCHANGED <<
        runState, stateLease, claim, dbSlots, reapPhase, scanEpoch,
        releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

CommitAcquire ==
    /\ txnKind = "Acquire"
    /\ leaseState[txnLease] = "Live"
    /\ dbSlots < Limit
    /\ runState' = [runState EXCEPT ![txnRun] = "Pending"]
    /\ stateLease' = [stateLease EXCEPT ![txnRun] = txnLease]
    /\ claim' = [claim EXCEPT ![txnLease] = TRUE]
    /\ dbSlots' = dbSlots + 1
    /\ txnKind' = "None"
    /\ txnRun' = NoRun
    /\ txnLease' = NoLease
    /\ UNCHANGED <<
        leaseState, leaseOwner, epoch, reapPhase, scanEpoch,
        releasePhase, badForeignDecrement, badStaleReap
        >>

CommitRunning(r) ==
    LET l == stateLease[r] IN
    /\ runState[r] = "Pending"
    /\ l # NoLease
    /\ leaseState[l] = "Live"
    /\ claim[l]
    /\ runState' = [runState EXCEPT ![r] = "Running"]
    /\ UNCHANGED <<
        stateLease, leaseState, leaseOwner, epoch, claim, dbSlots,
        reapPhase, scanEpoch, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

Expire(l) ==
    /\ leaseState[l] = "Live"
    /\ leaseState' = [leaseState EXCEPT ![l] = "Expired"]
    /\ UNCHANGED <<
        runState, stateLease, leaseOwner, epoch, claim, dbSlots,
        reapPhase, scanEpoch, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

Renew(r) ==
    LET l == stateLease[r] IN
    /\ runState[r] \in {"Pending", "Running"}
    /\ l # NoLease
    /\ leaseState[l] \in {"Live", "Expired"}
    /\ epoch[l] < MaxEpoch
    /\ leaseState' = [leaseState EXCEPT ![l] = "Live"]
    /\ epoch' = [epoch EXCEPT ![l] = @ + 1]
    /\ UNCHANGED <<
        runState, stateLease, leaseOwner, claim, dbSlots,
        reapPhase, scanEpoch, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

ScanExpired(l) ==
    /\ leaseState[l] = "Expired"
    /\ reapPhase[l] = "Idle"
    /\ reapPhase' = [reapPhase EXCEPT ![l] = "Queued"]
    /\ scanEpoch' = [scanEpoch EXCEPT ![l] = epoch[l]]
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

ReapRead(l) ==
    /\ reapPhase[l] = "Queued"
    /\ leaseState[l] # "Absent"
    /\ reapPhase' = [reapPhase EXCEPT ![l] = "Read"]
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, scanEpoch, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

BeginReap(l) ==
    /\ reapPhase[l] = "Read"
    /\ txnKind = "None"
    /\ txnKind' = "Reap"
    /\ txnRun' = NoRun
    /\ txnLease' = l
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, reapPhase, scanEpoch, releasePhase,
        badForeignDecrement, badStaleReap
        >>

ReapObservationIsCurrent(l) ==
    /\ leaseState[l] = "Expired"
    /\ epoch[l] = scanEpoch[l]

ReapRevoke ==
    LET l == txnLease IN
    /\ txnKind = "Reap"
    /\ (~RecheckExpiryAtRevoke \/ ReapObservationIsCurrent(l))
    /\ badStaleReap' =
        (badStaleReap \/ ~ReapObservationIsCurrent(l))
    /\ leaseState' = [leaseState EXCEPT ![l] = "Absent"]
    /\ txnKind' = "ReapRevoked"
    /\ UNCHANGED <<
        runState, stateLease, leaseOwner, epoch, claim, dbSlots,
        reapPhase, scanEpoch, releasePhase, txnRun, txnLease,
        badForeignDecrement
        >>

CancelStaleReap ==
    LET l == txnLease IN
    /\ txnKind = "Reap"
    /\ RecheckExpiryAtRevoke
    /\ ~ReapObservationIsCurrent(l)
    /\ reapPhase' = [reapPhase EXCEPT ![l] = "Idle"]
    /\ txnKind' = "None"
    /\ txnRun' = NoRun
    /\ txnLease' = NoLease
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, scanEpoch, releasePhase,
        badForeignDecrement, badStaleReap
        >>

CommitReap ==
    LET l == txnLease IN
    /\ txnKind = "ReapRevoked"
    /\ dbSlots' =
        IF claim[l]
        THEN Decrement(dbSlots)
        ELSE IF RequireClaimForDecrement
             THEN dbSlots
             ELSE Decrement(dbSlots)
    /\ claim' = [claim EXCEPT ![l] = FALSE]
    /\ badForeignDecrement' =
        (badForeignDecrement \/
         (~claim[l] /\ ~RequireClaimForDecrement /\ OtherClaim(l)))
    /\ reapPhase' = [reapPhase EXCEPT ![l] = "Idle"]
    /\ txnKind' = "None"
    /\ txnRun' = NoRun
    /\ txnLease' = NoLease
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch,
        scanEpoch, releasePhase, badStaleReap
        >>

CancelAfterLostLease(r) ==
    LET l == stateLease[r] IN
    /\ runState[r] = "Pending"
    /\ l # NoLease
    /\ leaseState[l] = "Absent"
    /\ runState' = [runState EXCEPT ![r] = "Cancelled"]
    /\ UNCHANGED <<
        stateLease, leaseState, leaseOwner, epoch, claim, dbSlots,
        reapPhase, scanEpoch, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

TerminalReadPresent(r) ==
    LET l == stateLease[r] IN
    /\ runState[r] \in {"Pending", "Running", "Cancelled"}
    /\ releasePhase[r] = "Idle"
    /\ l # NoLease
    /\ leaseState[l] # "Absent"
    /\ releasePhase' = [releasePhase EXCEPT ![r] = "ReadPresent"]
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, reapPhase, scanEpoch, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

TerminalReadMissing(r) ==
    LET l == stateLease[r] IN
    /\ runState[r] = "Cancelled"
    /\ releasePhase[r] = "Idle"
    /\ l # NoLease
    /\ leaseState[l] = "Absent"
    /\ releasePhase' = [releasePhase EXCEPT ![r] = "ReadMissing"]
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, reapPhase, scanEpoch, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

BeginReleasePresent(r) ==
    /\ releasePhase[r] = "ReadPresent"
    /\ txnKind = "None"
    /\ txnKind' = "ReleasePresent"
    /\ txnRun' = r
    /\ txnLease' = stateLease[r]
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, reapPhase, scanEpoch, releasePhase,
        badForeignDecrement, badStaleReap
        >>

ReleaseRevoke ==
    /\ txnKind = "ReleasePresent"
    /\ leaseState' = [leaseState EXCEPT ![txnLease] = "Absent"]
    /\ txnKind' = "ReleaseRevoked"
    /\ UNCHANGED <<
        runState, stateLease, leaseOwner, epoch, claim, dbSlots,
        reapPhase, scanEpoch, releasePhase, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

CommitPresentRelease ==
    LET l == txnLease IN
    /\ txnKind = "ReleaseRevoked"
    /\ dbSlots' =
        IF claim[l]
        THEN Decrement(dbSlots)
        ELSE IF RequireClaimForDecrement
             THEN dbSlots
             ELSE Decrement(dbSlots)
    /\ claim' = [claim EXCEPT ![l] = FALSE]
    /\ badForeignDecrement' =
        (badForeignDecrement \/
         (~claim[l] /\ ~RequireClaimForDecrement /\ OtherClaim(l)))
    /\ runState' = [runState EXCEPT ![txnRun] = "Terminal"]
    /\ releasePhase' = [releasePhase EXCEPT ![txnRun] = "Idle"]
    /\ txnKind' = "None"
    /\ txnRun' = NoRun
    /\ txnLease' = NoLease
    /\ UNCHANGED <<
        stateLease, leaseState, leaseOwner, epoch,
        reapPhase, scanEpoch, badStaleReap
        >>

BeginFallbackRelease(r) ==
    /\ FallbackDecrementsAggregate
    /\ releasePhase[r] = "ReadMissing"
    /\ txnKind = "None"
    /\ txnKind' = "ReleaseMissing"
    /\ txnRun' = r
    /\ txnLease' = stateLease[r]
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim,
        dbSlots, reapPhase, scanEpoch, releasePhase,
        badForeignDecrement, badStaleReap
        >>

SkipFallbackRelease(r) ==
    /\ ~FallbackDecrementsAggregate
    /\ releasePhase[r] = "ReadMissing"
    /\ runState' = [runState EXCEPT ![r] = "Terminal"]
    /\ releasePhase' = [releasePhase EXCEPT ![r] = "Idle"]
    /\ UNCHANGED <<
        stateLease, leaseState, leaseOwner, epoch, claim, dbSlots,
        reapPhase, scanEpoch, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

CommitFallbackRelease ==
    LET l == txnLease IN
    /\ txnKind = "ReleaseMissing"
    /\ dbSlots' =
        IF claim[l]
        THEN Decrement(dbSlots)
        ELSE IF RequireClaimForDecrement
             THEN dbSlots
             ELSE Decrement(dbSlots)
    /\ claim' = [claim EXCEPT ![l] = FALSE]
    /\ badForeignDecrement' =
        (badForeignDecrement \/
         (~claim[l] /\ ~RequireClaimForDecrement /\ OtherClaim(l)))
    /\ runState' = [runState EXCEPT ![txnRun] = "Terminal"]
    /\ releasePhase' = [releasePhase EXCEPT ![txnRun] = "Idle"]
    /\ txnKind' = "None"
    /\ txnRun' = NoRun
    /\ txnLease' = NoLease
    /\ UNCHANGED <<
        stateLease, leaseState, leaseOwner, epoch,
        reapPhase, scanEpoch, badStaleReap
        >>

(***************************************************************************)
(* Target SQL-claim protocol. Acquisition and release update the claim and  *)
(* aggregate in one action, representing one database transaction. An      *)
(* expiry release checks the authoritative current deadline. A scan is only *)
(* a work hint: after renewal, the queued release cannot win while the claim *)
(* is live, but may reclaim it after a later expiry.                         *)
(***************************************************************************)

ClaimAcquire(r, l) ==
    /\ runState[r] = "Scheduled"
    /\ leaseState[l] = "Unused"
    /\ dbSlots < Limit
    /\ runState' = [runState EXCEPT ![r] = "Pending"]
    /\ stateLease' = [stateLease EXCEPT ![r] = l]
    /\ leaseState' = [leaseState EXCEPT ![l] = "Live"]
    /\ leaseOwner' = [leaseOwner EXCEPT ![l] = r]
    /\ epoch' = [epoch EXCEPT ![l] = 1]
    /\ claim' = [claim EXCEPT ![l] = TRUE]
    /\ dbSlots' = dbSlots + 1
    /\ UNCHANGED <<
        reapPhase, scanEpoch, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

ClaimExpiryRelease(l) ==
    /\ reapPhase[l] = "Queued"
    /\ (~RequireClaimForDecrement \/ claim[l])
    /\ (~RecheckExpiryAtRevoke \/ leaseState[l] = "Expired")
    /\ badStaleReap' = (badStaleReap \/ leaseState[l] # "Expired")
    /\ badForeignDecrement' =
        (badForeignDecrement \/ (~claim[l] /\ OtherClaim(l)))
    /\ claim' = [claim EXCEPT ![l] = FALSE]
    /\ dbSlots' = Decrement(dbSlots)
    /\ leaseState' = [leaseState EXCEPT ![l] = "Absent"]
    /\ reapPhase' = [reapPhase EXCEPT ![l] = "Idle"]
    /\ UNCHANGED <<
        runState, stateLease, leaseOwner, epoch, scanEpoch, releasePhase,
        txnKind, txnRun, txnLease
        >>

DiscardStaleExpiry(l) ==
    /\ reapPhase[l] = "Queued"
    /\ \/ ~claim[l]
       \/ leaseState[l] # "Expired"
    /\ reapPhase' = [reapPhase EXCEPT ![l] = "Idle"]
    /\ UNCHANGED <<
        runState, stateLease, leaseState, leaseOwner, epoch, claim, dbSlots,
        scanEpoch, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

ClaimTerminalRelease(r) ==
    LET l == stateLease[r] IN
    /\ runState[r] \in {"Pending", "Running", "Cancelled"}
    /\ l # NoLease
    /\ (~RequireClaimForDecrement \/ claim[l])
    /\ badForeignDecrement' =
        (badForeignDecrement \/ (~claim[l] /\ OtherClaim(l)))
    /\ runState' = [runState EXCEPT ![r] = "Terminal"]
    /\ leaseState' = [leaseState EXCEPT ![l] = "Absent"]
    /\ claim' = [claim EXCEPT ![l] = FALSE]
    /\ dbSlots' = Decrement(dbSlots)
    /\ UNCHANGED <<
        stateLease, leaseOwner, epoch, reapPhase, scanEpoch, releasePhase,
        txnKind, txnRun, txnLease, badStaleReap
        >>

ClaimTerminalNoop(r) ==
    LET l == stateLease[r] IN
    /\ runState[r] \in {"Pending", "Running", "Cancelled"}
    /\ l # NoLease
    /\ ~claim[l]
    /\ runState' = [runState EXCEPT ![r] = "Terminal"]
    /\ UNCHANGED <<
        stateLease, leaseState, leaseOwner, epoch, claim, dbSlots,
        reapPhase, scanEpoch, releasePhase, txnKind, txnRun, txnLease,
        badForeignDecrement, badStaleReap
        >>

AcquireActions ==
    \/ \E r \in Runs, l \in LeaseIds : BeginAcquire(r, l)
    \/ CreateLease
    \/ CommitAcquire

ReapActions ==
    \/ \E l \in LeaseIds : Expire(l)
    \/ \E l \in LeaseIds : ScanExpired(l)
    \/ \E l \in LeaseIds : ReapRead(l)
    \/ \E l \in LeaseIds : BeginReap(l)
    \/ ReapRevoke
    \/ CancelStaleReap
    \/ CommitReap

FallbackActions ==
    \/ \E r \in Runs : CancelAfterLostLease(r)
    \/ \E r \in Runs : TerminalReadMissing(r)
    \/ \E r \in Runs : BeginFallbackRelease(r)
    \/ \E r \in Runs : SkipFallbackRelease(r)
    \/ CommitFallbackRelease

PresentReleaseActions ==
    \/ \E r \in Runs : TerminalReadPresent(r)
    \/ \E r \in Runs : BeginReleasePresent(r)
    \/ ReleaseRevoke
    \/ CommitPresentRelease

StaleReapNext ==
    \/ AcquireActions
    \/ \E r \in Runs : Renew(r)
    \/ ReapActions

FallbackNext ==
    \/ AcquireActions
    \/ ReapActions
    \/ FallbackActions

ReadPresentNext ==
    \/ AcquireActions
    \/ ReapActions
    \/ PresentReleaseActions

ClaimAuthorityNext ==
    \/ \E r \in Runs, l \in LeaseIds : ClaimAcquire(r, l)
    \/ \E r \in Runs : CommitRunning(r)
    \/ \E r \in Runs : Renew(r)
    \/ \E l \in LeaseIds : Expire(l)
    \/ \E l \in LeaseIds : ScanExpired(l)
    \/ \E l \in LeaseIds : ClaimExpiryRelease(l)
    \/ \E l \in LeaseIds : DiscardStaleExpiry(l)
    \/ \E r \in Runs : CancelAfterLostLease(r)
    \/ \E r \in Runs : ClaimTerminalRelease(r)
    \/ \E r \in Runs : ClaimTerminalNoop(r)

StaleReapSpec == Init /\ [][StaleReapNext]_vars
FallbackSpec == Init /\ [][FallbackNext]_vars
ReadPresentSpec == Init /\ [][ReadPresentNext]_vars
ClaimAuthoritySpec == Init /\ [][ClaimAuthorityNext]_vars

TypeOK ==
    /\ runState \in [Runs -> RunStates]
    /\ stateLease \in [Runs -> LeaseIds \cup {NoLease}]
    /\ leaseState \in [LeaseIds -> LeaseStates]
    /\ leaseOwner \in [LeaseIds -> Runs \cup {NoRun}]
    /\ epoch \in [LeaseIds -> 0..MaxEpoch]
    /\ claim \in [LeaseIds -> BOOLEAN]
    /\ dbSlots \in 0..Limit
    /\ reapPhase \in [LeaseIds -> ReapPhases]
    /\ scanEpoch \in [LeaseIds -> 0..MaxEpoch]
    /\ releasePhase \in [Runs -> ReleasePhases]
    /\ txnKind \in TxnKinds
    /\ txnRun \in Runs \cup {NoRun}
    /\ txnLease \in LeaseIds \cup {NoLease}
    /\ badForeignDecrement \in BOOLEAN
    /\ badStaleReap \in BOOLEAN

CounterBounds == dbSlots \in 0..Limit
ClaimCapacitySafety == Cardinality(Claims) <= Limit
OwnershipConsistent ==
    \A l \in LeaseIds :
        claim[l] =>
            /\ leaseOwner[l] \in Runs
            /\ stateLease[leaseOwner[l]] = l
NoForeignRelease == ~badForeignDecrement
RenewWinsAgainstStaleScan == ~badStaleReap
AccountingConsistent == dbSlots = Cardinality(Claims)

=============================================================================
