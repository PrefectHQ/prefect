# Storage Overview

Overview of what storage is

## Storage Types and Flows

How they're serialized, put into storage...

### Pickle-based Storage

The default method for persisting actual [Flow]() objects uses [cloudpickle]() to serialize flows as
bytes and place them in their set storage option. This mode of storage effectively freezes the flow so it
can be loaded in the future when being run.

Add note about dependencies

### File-based Storage

Explaining the use of files, hot reloading flows, no registration deploys

### Non-Docker Storage for Containerized Environments

Prefect allows for flows to be stored in cloud storage services and executed in containerized environments. This has the added benefit of rapidly deploying new versions of flows without having to rebuild images each time. To enable this functionality add an image name to the flow's Environment metadata.

```python
from prefect import Flow
from prefect.environments import LocalEnvironment
from prefect.environments.storage import S3

flow = Flow("example")

# set flow storage
flow.storage = S3(bucket="my-flows")

# set flow environment
flow.environment = LocalEnvironment(metadata={"image": "repo/name:tag"})
```

This example flow can now be run using an agent that orchestrates containerized environments. When the flow is run the image set in the environment's metadata will be used and inside that container the flow will be retrieved from the storage object (which is S3 in this example).

Make sure that the agent's labels match the desired labels for the flow storage objects. For example, if you are using `prefect.environments.storage.s3` to store flows, the agent should get label `s3-flow-storage`. See the `"Sensible Defaults"` tips in the previous sections for more details.

```bash
# starting a kubernetes agent that will pull flows stored in S3
prefect agent start kubernetes -l s3-flow-storage
```

::: tip Default Labels
The addition of these default labels can be disabled by passing `add_default_labels=False` to the flow's storage option. If this is set then the agents can ignore having to also set these labels. For more information on labels visit [the documentation](/orchestration/execution/overview.html#labels).
:::

#### Authentication for using Cloud Storage with Containerized Environments

One thing to keep in mind when using cloud storage options in conjunction with containerized environments is authentication. Since the flow is being retrieved from inside a container then that container must be authenticated to pull the flow from whichever cloud storage it has set. This means that at runtime the container needs to have the proper authentication.

Prefect has a couple [default secrets](/core/concepts/secrets.html#default-secrets) which could be used for off-the-shelf authentication. Using the above snippet as an example it is possible to create an `AWS_CREDENTIALS` Prefect secret that will automatically be used to pull the flow from S3 storage at runtime without having to configure authentication in the image directly.

```python
flow.storage = S3(bucket="my-flows", secrets=["AWS_CREDENTIALS"])

flow.environment = LocalEnvironment(metadata={"image": "prefecthq/prefect:all_extras"})
```

::: warning Dependencies
It is important to make sure that the `image` set in the environment's metadata contains the dependencies required to use the storage option. For example, using `S3` storage requires Prefect's `aws` dependencies.

These are generally packaged with custom built images or optionally you could use the `prefecthq/prefect:all_extras` image which contains all of Prefect's optional extra packages.
:::

Add page for storage options ....
