---
sidebarDepth: 0
---

# Contents

**Prefect Improvement Notices** are used to propose, discuss, accept, and memorialize any major architectural decisions for Prefect Core.

## [PIN-1: Introduce Prefect Improvement Notices](PIN-01-Introduce-PINs.md)

Introducing PINs for recording Prefect decisions.

**Status:** Approved

## [PIN-2: Implementation of Result Handlers and State Metadata](PIN-02-Result-Handlers.md)

Adding metadata to `States` in order to track task results and serialization methods.

**Status:** Approved

## [PIN-3: Agent-Environment Model for Flow Execution](PIN-03-Agent-Environment.md)

A description of a more complex and executable `Environment` object.

**Status:** Approved

## [PIN-4: Result Objects for Tracking and Serializing Task Outputs](PIN-04-Result-Objects.md)

A new `Result` object that clarifies the logic introduced by [PIN-2](PIN-02-Result-Handlers.md).

**Status:** Approved

## [PIN-5: Ability to Combine Tasks](PIN-05-Combining-Tasks.md)

A proposal for automatically combining tasks to ensure data locality; ultimately declined as a general approach.

**Status:** Declined

## [PIN-6: Remove Constant Tasks](PIN-06-Remove-Constant-Tasks.md)

A proposal for removing auto-converting non-task objects into `Constant` Tasks; ultimately declined as the benefits outweigh the costs.

**Status:** Declined

## [PIN-7: Storage and Execution](PIN-07-Storage-Execution.md)

A proposal for refactoring environments into `Storage` classes and execution `Environment` classes with specific, loosely coupled interfaces.

**Status:** Approved

## [PIN-8: Event-Driven / Listener Flows](PIN-08-Listener-Flows.md)

A proposal for event-driven or long-running flows that run in response to events that arrive in an irregular stream.

**Status:** Proposed

## [PIN-9: Prefect CLI](PIN-09-CLI.md)

A proposal for a flexible and live-updating Prefect Cloud command line client.

**Status:** Approved

## [PIN-10: Flexible Schedules](PIN-10-Schedules.md)

A proposal for a new way of building schedules that captures a wider variety of use cases.

**Status:** Proposed

## [PIN-11: Single-Task Loops](PIN-11-Task-Loops.md)

A proposal for a way to loop over single tasks with arbitrary control logic and all Prefect semantics intact

**Status:** Proposed

## [PIN 12: Environment Callbacks](PIN-12-Environment-Callbacks.md)

A proposal to introduce user-provided callbacks for `Environments` which users can use to specify additional behavior before a Flow is run and after a FlowRun has ended.

**Status:** Accepted

## [PIN 13: Universal Cloud Deploys](PIN-13-Universal-Deploy.md)

A proposal to run Flows from Prefect Cloud with local Python resources and packages.

**Status:** Accepted

## [PIN-14: Event-Driven Flow Execution via Listeners](PIN-14-Listener-Flows-2.md)

A proposal to enable starting a Flow based on events from user provided sources by leveraging the existing Schedule features.

**Status:** Proposed; supersedes [PIN 8](PIN-08-Listener-Flows.html).

## [PIN-15: Skip state as Finished + Control Flow Conditional](PIN-15-Skip-as-Finished-and-Conditionals.md)

A proposal to interpret `Skip` states as `Finished` instead of `Success`ful while also introducing more conditional control flow constructs.

**Status:** Proposed
