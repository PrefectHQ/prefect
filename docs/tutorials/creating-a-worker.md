---
description: Learn how to create a Prefect worker to run your flows.
tags:
    - work pools
    - workers
    - orchestration
    - flow runs
    - deployments
    - storage
    - infrastructure
    - tutorial
    - recipes
---

# Creating a Worker

!!! warning "Advanced Topic"
    This tutorial is for users who are want to extend the Prefect framework and will require deep knowledge of Prefect concepts. If you want to run your flows, we recommend using one of the [available workers](/concepts/work-pools/#worker-types) instead.


Prefect workers are responsible for creating execution environments and starting flow runs within those execution environments. 

A list of available workers can be found in the [Work Pools, Workers & Agents documentation](/concepts/work-pools/#worker-types). What if you want to execute your flow runs on infrastructure that doesn't have a worker available? This tutorial will walk you through creating a custom worker that can run your flows on your chosen infrastructure.

## Worker Configuration

When setting up an execution environment for a flow run, a worker receives configuration for the infrastructure it is designed to work with. Examples of configuration values include memory allocation, CPU allocation, credentials, image name, etc. The worker then uses this configuration to create the execution environment and start the flow run.

!!! tip "How are the configuration values populated?"
    The work pool that a worker polls for flow runs has a [base job template](/concepts/work-pools/#base-job-template) associated with it which is the contract for how configuration values populate for each flow run.
    
    The keys in the `job_configuration` section of this base job template match the worker's configuration class attributes. The values in the `job_configuration` section of the base job template are used to populate the attributes of the worker's configuration class.

    The work pool creator gets to decide how they want to populate the values in the `job_configuration` section of the base job template. The values can be hard-coded, templated using placeholders, or a mix these two approaches. Because you, as the worker developer, don't know how the work pool creator will populate the values, so you should set sensible defaults for your configuration class attributes.

### Implementing a `BaseJobConfiguration` Subclass

A worker developer defines the configuration their worker needs to function with a class extending [`BaseJobConfiguration`](/api-ref/prefect/workers/base/#prefect.workers.base.BaseJobConfiguration). 

`BaseJobConfiguration` has attributes that are common to all workers: 

| Attribute | Description |
| --------- | ----------- |
| `name` | The name to assign to the created execution environment. |
| `env` | Environment variables to set in the created execution environment. |
| `labels` | The labels assigned to the created execution environment for metadata purposes. |
| `command` | The command to use when starting a flow run. |

Prefect sets values for each attribute before giving the configuration to the worker. If you want to customize the values of these attributes, use the [`prepare_for_flow_run`](/api-ref/prefect/workers/base/#prefect.workers.base.BaseJobConfiguration.prepare_for_flow_run) method.

Here's an example `prepare_for_flow_run` method that sets add a label to the execution environment:

```python
def prepare_for_flow_run(
    self, flow_run, deployment = None, flow = None,
):  
    super().prepare_for_flow_run(flow_run, deployment, flow)  
    self.labels.append("my-custom-label")
```

A worker configuration class is a [Pydantic model](https://docs.pydantic.dev/usage/models/), so you can add additional attributes to your configuration class as Pydantic fields. For example, if you want to allow memory and CPU requests for your worker, you can do so like this:

```python
from pydantic import Field
from prefect.workers.base import BaseJobConfiguration

class MyWorkerConfiguration(BaseJobConfiguration):
    memory: int = Field(
            default=1024,
            description="Memory allocation for the execution environment."
        )
    cpu: int = Field(
            default=500, 
            description="CPU allocation for the execution environment."
        )
```

This configuration class will populate the `job_configuration` section of the resulting base job template. 

For this example, the base job template would look like this:

```yaml
job_configuration:
    name: "{{ name }}"
    env: "{{ env }}"
    labels: "{{ labels }}"
    command: "{{ command }}"
    memory: "{{ memory }}"
    cpu: "{{ cpu }}"
variables:
    type: object
    properties:
        name:
          title: Name
          description: Name given to infrastructure created by a worker.
          type: string
        env:
          title: Environment Variables
          description: Environment variables to set when starting a flow run.
          type: object
          additionalProperties:
            type: string
        labels:
          title: Labels
          description: Labels applied to infrastructure created by a worker.
          type: object
          additionalProperties:
            type: string
        command:
          title: Command
          description: The command to use when starting a flow run. In most cases,
            this should be left blank and the command will be automatically generated
            by the worker.
          type: string
        memory:
            title: Memory
            description: Memory allocation for the execution environment.
            type: integer
            default: 1024
        cpu:
            title: CPU
            description: CPU allocation for the execution environment.
            type: integer
            default: 500
```

This base job template defines what values can be provided by deployment creators on a per-deployment basis and how those provided values will be translated into the configuration values that the worker will use to create the execution environment.

Notice that each attribute for the class was added in the `job_configuration` section with placeholders whose name matches the attribute name. The `variables` section was also populated with the OpenAPI schema for each attribute. If a configuration class is used without explicitly declaring any template variables, then the template variables will be inferred from the configuration class attributes.

### Customizing Configuration Attribute Templates

You can customize the template for each attribute for situations where the configuration values should use more sophisticated templating. For example, if you want to add units for the `memory` attribute, you can do so like this:

```python
from pydantic import Field
from prefect.workers.base import BaseJobConfiguration

class MyWorkerConfiguration(BaseJobConfiguration):
    memory: str = Field(
            default="1024Mi",
            description="Memory allocation for the execution environment."
            template="{{ memory_request }}Mi"
        )
    cpu: str = Field(
            default="500m", 
            description="CPU allocation for the execution environment."
            template="{{ cpu_request }}m"
        )
```

Notice that we changed the type of each attribute to `str` to accommodate the units, and we added a new `template` attribute to each attribute. The `template` attribute is used to populate the `job_configuration` section of the resulting base job template.

For this example, the `job_configuration` section of the resulting base job template would look like this:

```yaml
job_configuration:
    name: "{{ name }}"
    env: "{{ env }}"
    labels: "{{ labels }}"
    command: "{{ command }}"
    memory: "{{ memory_request }}Mi"
    cpu: "{{ cpu_request }}m"
```

Note that to use custom templates, you will need to declare the template variables used in the template because the names of those variables can no longer be inferred from the configuration class attributes. We will cover how to declare the default variable schema in the [Worker Template Variables](#worker-template-variables) section.

### Configuring Credentials

When executing flow runs within cloud services, workers will often need credentials to authenticate with those services. For example, a worker that executes flow runs in AWS Fargate will need AWS credentials. As a worker developer, you can use blocks to accept credentials configuration from the user.

For example, if you want to allow the user to configure AWS credentials, you can do so like this:

```python
from prefect_aws import AwsCredentials

class MyWorkerConfiguration(BaseJobConfiguration):
    aws_credentials: AwsCredentials = Field(
        default=None,
        description="AWS credentials to use when creating AWS resources."
    )
```

Users can create and assign a block to the `aws_credentials` attribute in the UI and the worker will use these credentials when interacting with AWS resources.

## Worker Template Variables

Providing template variables for a base job template defines the fields that deployment creators can override per deployment. The work pool creator ultimately defines the template variables for a base job template, but the worker developer is able to define default template variables for the worker to make it easier to use.

Default template variables for a worker are defined by implementing the `BaseVariables` class. Like the `BaseJobConfiguration` class, the `BaseVariables` class has attributes that are common to all workers:

| Attribute | Description |
| --------- | ----------- |
| `name` | The name to assign to the created execution environment. |
| `env` | Environment variables to set in the created execution environment. |
| `labels` | The labels assigned the created execution environment for metadata purposes. |
| `command` | The command to use when starting a flow run. |

Additional attributes can be added to the `BaseVariables` class to define additional template variables. For example, if you want to allow memory and CPU requests for your worker, you can do so like this:

```python
from pydantic import Field
from prefect.workers.base import BaseVariables

class MyWorkerTemplateVariables(BaseVariables):
    memory_request: int = Field(
            default=1024,
            description="Memory allocation for the execution environment."
        )
    cpu_request: int = Field(
            default=500, 
            description="CPU allocation for the execution environment."
        )
```

When `MyWorkerTemplateVariables` is used in conjunction with `MyWorkerConfiguration` from the [Customizing Configuration Attribute Templates](#customizing-configuration-attribute-templates) section, the resulting base job template will look like this:

```yaml
job_configuration:
    name: "{{ name }}"
    env: "{{ env }}"
    labels: "{{ labels }}"
    command: "{{ command }}"
    memory: "{{ memory_request }}Mi"
    cpu: "{{ cpu_request }}m"
variables:
    type: object
    properties:
        name:
          title: Name
          description: Name given to infrastructure created by a worker.
          type: string
        env:
          title: Environment Variables
          description: Environment variables to set when starting a flow run.
          type: object
          additionalProperties:
            type: string
        labels:
          title: Labels
          description: Labels applied to infrastructure created by a worker.
          type: object
          additionalProperties:
            type: string
        command:
          title: Command
          description: The command to use when starting a flow run. In most cases,
            this should be left blank and the command will be automatically generated
            by the worker.
          type: string
        memory_request:
            title: Memory Request
            description: Memory allocation for the execution environment.
            type: integer
            default: 1024
        cpu_request:
            title: CPU Request
            description: CPU allocation for the execution environment.
            type: integer
            default: 500
```

Note that template variable classes are never used directly. Instead, they are used to generate a schema that is used to populate the `variables` section of a base job template and validate the template variables provided by the user. 

We don't recommend using template variable classes within your worker implementation for validation purposes because the work pool creator ultimately defines the template variables. The configuration class should handle any necessary run-time validation.

## Worker Implementation

Workers handle creating execution environments using provided configuration. Workers also observe the execution environment as the flow run executes and report any crashes to the Prefect API.

To implement a worker, you must implement the `BaseWorker` class and provide it with the following attributes:

| Attribute | Description | Required |
| --------- | ----------- | -------- |
| `type` | The type of the worker. | Yes |
| `job_configuration` | The configuration class for the worker. | Yes |
| `job_configuration_variables` | The template variables class for the worker. | No |
| `_documentation_url` | Link to documentation for the worker. | No |
| `_logo_url` | Link to a logo for the worker. | No |
| `_description` | A description of the worker. | No |

In addition to the attributes above, you must also implement a `run` method. The `run` method is called for each flow run the worker receives for execution from the work pool.

The `run` method has the following signature:

```python
 async def run(
        self, flow_run: FlowRun, configuration: BaseJobConfiguration, task_status: Optional[anyio.abc.TaskStatus] = None,
    ) -> BaseWorkerResult:
        ...
```

The `run` method is passed the flow run to execute, the execution environment configuration for the flow run, and a task status object that allows the worker to track whether the flow run was submitted successfully.

The `run` method must also return a `BaseWorkerResult` object. The `BaseWorkerResult` object returned contains information about the flow run execution. For the most part, you can implement the `BaseWorkerResult` with no modifications like so:

```python
from prefect.workers.base import BaseWorkerResult

class MyWorkerResult(BaseWorkerResult):
    """Result returned by the MyWorker."""
```

If you would like to return more information about a flow run, then additional attributes can be added to the `BaseWorkerResult` class.

### Worker Implementation Example

Below is an example of a worker implementation. This example is not intended to be a complete implementation but to illustrate the abovementioned concepts.

```python
from prefect.workers.base import BaseWorker, BaseWorkerResult, BaseJobConfiguration, BaseVariables

class MyWorkerConfiguration(BaseJobConfiguration):
    memory: str = Field(
            default="1024Mi",
            description="Memory allocation for the execution environment."
            template="{{ memory_request }}Mi"
        )
    cpu: str = Field(
            default="500m", 
            description="CPU allocation for the execution environment."
            template="{{ cpu_request }}m"
        )

class MyWorkerTemplateVariables(BaseVariables):
    memory_request: int = Field(
            default=1024,
            description="Memory allocation for the execution environment."
        )
    cpu_request: int = Field(
            default=500, 
            description="CPU allocation for the execution environment."
        )

class MyWorkerResult(BaseWorkerResult):
    """Result returned by the MyWorker."""

class MyWorker(BaseWorker):
    type = "my-worker"
    job_configuration = MyWorkerConfiguration
    job_configuration_variables = MyWorkerTemplateVariables
    _documentation_url = "https://example.com/docs"
    _logo_url = "https://example.com/logo"
    _description = "My worker description."

    async def run(
        self, flow_run: FlowRun, configuration: BaseJobConfiguration, task_status: Optional[anyio.abc.TaskStatus] = None,
    ) -> BaseWorkerResult:
        # Create the execution environment and start execution
        job = await self._create_and_start_job(configuration)

        if task_status:
            task_status.started(job.id) # Use a unique ID to mark the run as started

        # Monitor the execution
        job_status = await self._watch_job(job, configuration)

        exit_code = job_status.exit_code if job_status else -1 # Get result of execution for reporting
        return MyWorkerResult(
            status_code=exit_code,
            identifier=job.id,
        )
```

Most of the execution logic is omitted from the example above, but it shows that the typical flow for execution in the `run` method is:
    1. Create the execution environment and start the flow run execution
    2. Mark the flow run as started via the passed `task_status` object
    3. Monitor the execution
    4. Get the execution's final status from the infrastructure and return a `BaseWorkerResult` object

To see other examples of worker implementations, see the [`ProcessWorker`]((/api-ref/prefect/workers/process/)) and [`KubernetesWorker`](https://prefecthq.github.io/prefect-kubernetes/worker/) implementations.

### Integrating with the Prefect CLI

Workers can be started via the Prefect CLI by providing the `--type` option to the `prefect worker start` CLI command. To make your worker type available via the CLI, it must be available at import time. 

If your worker is in a package, you can add an entry point to your setup file in the following format:

```python
entry_points={
    "prefect.collections": [
        "my_pacakge_name = my_worker_module",
    ]
},
```

Prefect will discover this entry point and load your work module in the specified module. The entry point will allow the worker to be available via the CLI.