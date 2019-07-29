---
sidebarDepth: 0
---

# Contents

**Prefect Improvement Notices** are used to propose, discuss, accept, and memorialize any major architectural decisions for Prefect Core.

## [PIN-1: Introduce Prefect Improvement Notices](PIN-1-Introduce-PINs.md)

Introducing PINs for recording Prefect decisions.

**Status:** Approved

## [PIN-2: Implementation of Result Handlers and State Metadata](PIN-2-Result-Handlers.md)

Adding metadata to `States` in order to track task results and serialization methods.

**Status:** Approved

## [PIN-3: Agent-Environment Model for Flow Execution](PIN-3-Agent-Environment.md)

A description of a more complex and executable `Environment` object.

**Status:** Approved

## [PIN-4: Result Objects for Tracking and Serializing Task Outputs](PIN-4-Result-Objects.md)

A new `Result` object that clarifies the logic introduced by [PIN-2](PIN-2-Result-Handlers.md).

**Status:** Approved

## [PIN-5: Ability to Combine Tasks](PIN-5-Combining-Tasks.md)

A proposal for automatically combining tasks to ensure data locality; ultimately declined as a general approach.

**Status:** Declined

## [PIN-6: Remove Constant Tasks](PIN-6-Remove-Constant-Tasks.md)

A proposal for removing auto-converting non-task objects into `Constant` Tasks; ultimately declined as the benefits outweigh the costs.

**Status:** Declined

## [PIN-7: Storage and Execution](PIN-7-Storage-Execution.md)

A proposal for refactoring environments into `Storage` classes and execution `Environment` classes with specific, loosely coupled interfaces.

**Status:** Approved

## [PIN-8: Event-Driven / Listener Flows](PIN-8-Listener-Flows.md)

A proposal for event-driven or long-running flows that run in response to events that arrive in an irregular stream.

**Status:** Proposed

## [PIN-9: Prefect CLI](PIN-9-CLI.md)

A proposal for a flexible and live-updating Prefect Cloud command line client.

**Status:** Approved

## [PIN-10: Flexible Schedules](PIN-10-Schedules.md)

A proposal for a new way of building schedules that captures a wider variety of use cases.

**Status:** Proposed

## [PIN-11: Single-Task Loops](PIN-11-Task-Loops.md)

A proposal for a way to loop over single tasks with arbitrary control logic and all Prefect semantics intact

**Status:** Proposed
