# PIN 13: Universal Cloud Deploys

Date: November 5, 2019

Author: Chris White

# Status
Accepted

# Context
Certain Prefect Cloud users encounter a non-trivial friction when deploying their Core flows to Cloud because of Docker.  There are three big reasons for this:
- recreating your Flow inside a Docker container can sometimes require a non-trivial amount of PATH manipulation overhead due to cloudpickle
- some users are just not familiar with Docker, and fail to successfully build their own custom images or host their own registries
- certain Flows require significant refactors to be dockerized (e.g., imagine a local ETL flow which writes to a SQLite database - Dockerizing requires a fundamental change in the DB stack)

Additionally, executing Flows on Cloud requires the use of an Agent which isn't difficult but _is_ an extra step.

The design philosophy of Prefect is that we offer sensible defaults for users to get off the ground as quickly and efficiently as possible, while exposing a highly configurable interface / API for producing robust production setups.  With Cloud, we are currently _requiring_ our robust dockerized framework as the smallest possible implementation, which conflicts with our stated design philosophy.  

# Proposal

This PIN re-imagines what "running a Cloud flow locally" looks like to make it _just as simple_ as running a Flow in Core:

```python
flow.deploy("My Project") # uses `flow.save` to store the flow to disk
flow.run_agent()
```

The proposed `run_agent` method will:
- create a local agent using the user's USER token (note: the current local agent will be renamed `DockerAgent`)
- label the agent with highly specific labels for only running this particular flow (e.g., `["HOSTNAME", "flow-name"]` where `HOSTNAME` is the hostname of the deploying machine)
- run the Cloud flow in-process

In addition, we will begin providing a `prefect agent install local` CLI endpoint for producing a [supervisor](http://supervisord.org/) configuration file designed for your Local Prefect Agent - this will allow us to promote this as a production worthy setup.

# Consequences

The proposed setup has many consequences:
- running a Cloud flow is now possible from literally anywhere that you can install Prefect
- transitioning from Core -> Cloud is now _actually_ as simple as authenticating with Cloud and calling two new methods
- debugging Cloud flows will be significantly easier (e.g., breakpoints can be called within tasks)
- users can craft their own flow deployments with custom dockerization techniques, etc.

Of course, there are other consequences as well: 
- we'll need better documentation of Storage interfaces to explain why one might choose Local vs. Docker vs. some other storage
- documenting why one might deploy using this technique vs. agents (which are still recommended when orchestrating multiple flows)
- documenting that recreating a Flow interactively each time won't work unless it is always accompanied by a redeploy, due to the nature of Task IDs

# Actions
There are many action items to successfully realize this PIN:
- change the default storage option to `Local` from `Docker`
- rename the current `LocalAgent` to `DockerAgent` and implement a true `LocalAgent` for running Flows stored in `Local` storage (on disk)
- a very large amount of clear documentation
- implement the method 
- introduce new storage options such as S3, GCS and Azure Blob for sharing Flows across machines
