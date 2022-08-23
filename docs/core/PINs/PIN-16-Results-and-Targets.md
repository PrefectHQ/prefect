---
title: 'PIN-16: Results and Targets'
sidebarDepth: 0
---
# PIN 16: Results and Targets

Date: March 4, 2020

Authors: Chris White & Laura Lorenz

## Status
Accepted
## Context
Currently, Prefect tracks all data explicitly returned by tasks for downstream consumption.  In addition, Prefect allows for caching the success of a task based on a certain condition (specified by a `cache_validator`) over a certain time frame (specified by `cache_for` on the task).  Prefect also currently allows for the data returned by individual tasks to be stored in diverse, configurable locations via the `ResultHandler` interface.  Despite the configurable nature of the result handler and caching APIs, there are still a few use cases that are not sufficiently covered within Prefect's API:
- "Makefile"-like semantics which allow the existence of data in a certain location to prevent the rerun of a task
- Prefect has no way of tracking data produced as side-effects of tasks
- Prefect exposes no first-class hooks for validating data (whether returned from a task or produced by a task during the run)
- Prefect output caches exist only in-memory for Core-only users, so cached computations are not recoverable between Python processes


While most of this can technically still be achieved within Prefect, the popularity of these patterns along with the lack of an obvious "correct" way to achieve them in Prefect leaves room for improving Prefect's API to accommodate such patterns in a first-class way.

## Proposal
The current proposal seeks to address all use cases listed above with a common underlying implementation.  In particular, we will extend the current [`Result` class API](/core/PINs/PIN-04-Result-Objects.html) with the following new methods and settings:
- we will introduce new `Result` types which correspond to different storage backends for data (e.g., `LocalFileResult`, `S3Result`, etc.)
- new `read` / `write` methods which mimic the current [`ResultHandler` implementations](/core/PINs/PIN-02-Result-Handlers.html) and will supercede the need for result handlers altogether
- the initialization of `Result` objects will allow for setting a configurable and templatable location (e.g., a templatable file name), along with a collection of validation functions which will optionally be called on the underlying object
- a new `exists` method for determining whether data exists in a given location
- a new `validate` method which accepts an optional list of validators; both the provided validators along with those set at initialization will then be called on the underlying data to validate it in customizable ways
- `cache_for` and `cache_validators` can be set on the Result, allowing for output cache behaviors to be exposed using this same interface

With this new collection of result "types", we can now introduce the following new features / settings on Tasks and Flows:
- Flows can be provided with a default Result type for its tasks
- individual tasks can optionally override the default Flow type (identical to the current way result handlers work)
- tasks can receive an optional set of validation functions under the `validators` kwarg which will be appended to the validators attached to the task's result type
- when `validate=True` on the `Result` type, the `validate` method described above will be called as an additional pipeline step in the `TaskRunner`; if validation fails, the task run will enter a new `ValidationError` failed state
- a new `target: Result` kwarg on tasks which serves two purposes: a) the output result type can be overriden through this kwarg and b) the new `exists` method will be called as a pre-run pipeline check; if the result exists, it will be `read` and optionally validated, and the task run will then enter a `Cached` state with the data that was read
- if configured, a Result's `cache_for` or `cache_validators` will be run during the pre-run pipeline check on the read Result, and if successful the task run instead enter a `Cached` State with the data that was read

## Consequences
The new API proposed here will allow for makefile like workflows, first-class type validation on _all_ data returned / emitted by tasks (including data produced as a side effect so long as users use the `Result` API), and hopefully make the current `result_handler` interface more intuitive for users.  Because of the large scale of the proposed changes, we will need to consider whether we can implement them in a backwards compatible way (we probably can).
## Actions
We attempt to list a roughly independent set of action items for achieving the above proposal:
- introduce a new `ValidationError` failed state
- merge the interfaces of `Result`s and `ResultHandler`s into a single `Result` interface with multiple types
- decide on how templating of file locations should work (e.g., will we call `.format(**prefect.context)`?)
- introduce three new keywords to `Task.__init__`: `result` (or `result_type`), `validators`, and `target`
- utilize or merge existing output caching logic to operate against Result targets instead of the in-memory cache. `cache_for` will be usable for any Result target type that has an inspectable last modified time
- develop a future PIN that allows for target file locations to be automatically configured by Prefect based on some default templating behavior
