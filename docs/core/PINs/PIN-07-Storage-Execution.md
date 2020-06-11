---
sidebarDepth: 0
---

# PIN-7: Storage and Execution

Date: April 20, 2019

Authors: Josh Meek & Chris White

## Status

Accepted

## Context

Our current environment setup contains multiple classes, some of which can be deployed, others which can't. Moreover, the environment classes tightly couple storage of a flow with execution platform details. This leads to an unsatisfactory interface, and a spreading out of documentation. Additionally, it makes it hard to delineate which environments are appropriate for which use cases and also requires a large number of highly specific classes.

## Proposal

The core of the proposal is to create two separate interfaces: one called `Storage` for storing flows, and one called `Environment` for encoding execution environment logic and setup.  Let's review each of these individually.

### Storage

The proposed Prefect Storage interface encapsulates logic for storing, serializing and even running Flows.  Each storage unit will be able to store _multiple_ flows (possibly with the constraint of name uniqueness within a given unit), and will expose the following methods and attributes:
- a name attribute
- a `flows` attribute that is a dictionary of flow name -> location
- an `add_flow(flow: Flow) -> str` method for adding flows to Storage, and which will return the location of the given flow in the Storage unit
- the `__contains__(self, obj) -> bool` special method for determining whether the Storage contains a given Flow
- one of `get_runner(flow_location: str)` or `get_env_runner(flow_location: str)` for retrieving a way of interfacing with either `flow.run` or a `FlowRunner` for the flow; `get_env_runner` is intended for situations where flow execution can only be interacted with via environment variables
- a `build() -> Storage` method for "building" the storage
- a `serialize() -> dict` method for serializing the relevant information about this Storage for later re-use.

### Execution Environment

The proposed Execution Environment interface encapsulates logic for setting up and executing a flow run on various infrastructure.  The interface for an `Environment` is simple:
- a `setup(storage: Storage) -> None` method for setting up any required infrastructure for the execution environment (e.g., spinning up resources)
- an `execute(storage: Storage, flow_location: str) -> None` method that serves as an entrypoint for individual Flow execution
- a `serialize() -> dict` method for serializing the relevant information about this environment

An environment can require certain types of Storage, but should be able to do all its work via interacting with the Storage interface above.  Note that all of environment, storage and flow_location can be serialized within a given Flow.

## Consequences

All environments will need a total rewrite, new storage classes will need to be introduced, agent interfaces will need to be updated and PIN-3 will be partially voided.  Additionally, the Flow serialization schema will need to be updated to include storage, environment and `flow_location`.
