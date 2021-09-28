# Flow and Task configuration

## Basic flow configuration

Names, descriptions, versions.

!!! note "Advanced configuration"
    We will see more advanced flow configuration when we discuss deployments.

### Parameter type conversion

This will be particularly important when we use a standalone API to trigger our flow runs.

## Task configuration

Name, descriptions, versions.  But now we get to the feature set of Prefect and why you would use tasks at all - retries, caching.  

!!! warning "The persistence of state"
    Note that up until now we have run all of our workflows interactively; this means that our metadata store that includes things like
    `Cached` states is torn down after we exit our Python session.  To persist sunch information across sessions, we need to standup a persistent database.


Open questions about content order: parallel execution? subflows are maximally useful with a backend. standing up the DB / API / UI?
