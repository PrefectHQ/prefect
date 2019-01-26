---
title: 'PIN-2: Proper Implementation of Result Handlers and State Metadata'
sidebarDepth: 0
---

# PIN-2: Proper Implementation of Result Handlers and State Metadata

Date: 2019-01-25

Author: Chris White

## Status

Proposed

## Context

One of the strengths of using Prefect is security: we can robustly execute user pipelines, allow data to flow between tasks, and pick up from failures using retries, _all without our backend ever having access to user data_.  At a high level, this is implemented via an intermediary which is currently called a "Result Handler"; the result handler is a lightweight class that can be attached to Flows and implements a basic interface which stores and retrieves data from arbitrary locations (for example, a customer's Google Cloud Infrastructure).  In this way, our backend can store only URIs that result handlers use to retrieve the real underlying data for use in the pipeline.  Because Flows run on user-controlled infrastructure too, all of this stays "in house" for a user of Prefect.

However, result handlers are currently utilized inside state serializers only; this means that _every piece of data_ that flows through the system is handled and stored somewhere, which is excessive.  Moreover, individual tasks might want their results handled differently.  Furthermore, the name "Result Handler" is a misnomer, as we also need to handle cached inputs, cached parameters, etc.

## Decision

We should implement result handlers (with a new name) by making the following changes:
- all Prefect State objects will gain a new attribute, called `metadata`, which will be a dictionary whose keys correspond to other attributes of the State (e.g., `cached_inputs`, `result`, etc.) This dictionary will store the following information about the State's data: whether each piece of data is still in raw format, or whether it is a URI pointing to raw data in storage, and what result handler has been (or _should be_) used when handling this data
- State serializers will use this metadata dictionary in making decisions about what to ship to the backend; in particular, _no raw data_ should be serialized into the State object.  Additionally, State serializers will no longer perform the handling - they will simply decide what is safe to put in the DB, and ignore all else. (Note that, because Failed states include informative messages about their exceptions, we don't really lose anything by not storing those exceptions)
- Task Runner caching pipeline steps should be updated to include result handling logic; for example, the only time a _result_ should be handled is if the user requests it via the `cache_for` kwarg on the Task.  Similarly, for input storage the Task Runner can inspect the upstream state's metadata attribute to handle each and every input in a custom way
- Task Runner input handling pipeline steps will become responsible for unpackaging any URIs using the associated result handlers (this will prevent too much data from being loaded at the beginning of a Flow run)

Note that this allows for all kinds of interesting features: for example, we can implement a simple `JSONHandler` for storing tiny bits of data (strings, numbers) _directly in the DB_.  This will both allow for the convenience of storing such things to users, while also providing plenty of surface area for warning them that this means the Prefect backend will actually have their data.  In this case, the "URI" of a processed piece of data is simply its JSON representation.

Additionally, note that this means that if handling of data fails for any reason, it will be treated as a Task failure.

## Consequences

