# Orion Release Notes

## 2.0a4

We're excited to announce the fourth alpha release of Prefect's second generation workflow manager.

As we drive the Orion project to completion, we want to highlight some of the features in each release.

Here, the hot topic is executors. Executors are used to run tasks in Prefect workflows. 
In Orion, you can write a flow that contains no tasks. 
It can call many functions and execute arbitrary Python, but it will all happen sequentially and on a single machine.
Tasks allow you to track and orchestrate discrete chunks of your workflow while enabling powerful execution patterns.

[Executors](https://orion-docs.prefect.io/concepts/executors/) are the key building block which allow you to execute code in parallel, on other machines, or with other engines.

### Dask integration

Those of you familiar Prefect already have likely used our Dask executor.
The first release of Orion came with a Dask executor which could run simple local clusters.
This allowed tasks to run n parallel, but did not expose the full power of Dask.
In this release of Orion, we've reached feature parity with the existing Dask executor.
You can [create customizable temporary clusters](https://orion-docs.prefect.io/tutorials/dask-executor/#using-a-temporary-cluster) and [connect to existing Dask clusters](https://orion-docs.prefect.io/tutorials/dask-executor/#connecting-to-an-existing-cluster).
Additionally, because flows are not statically registered, we're able to easily expose Dask annotations which allow you to [specify fine-grained controls over the scheduling of your tasks](https://orion-docs.prefect.io/tutorials/dask-executor/#annotations) within Dask.


### Subflow executors

[Subflows](https://orion-docs.prefect.io/concepts/flows/#subflows) are a first-class concept in Orion and this enables new execution patterns.
For example, consider a flow where most of the tasks can run locally but for some subset of computationally intensive tasks you need more resources.
You can move your computationally intesive tasks into their own flow which uses a `DaskExecutor` to spin up a temporary Dask cluster in the cloud-provider of your choice.
Next, you simply call the flow from your other flow.
This pattern can be nested or reused multiple times, enabling groups of tasks to use the executor that makes sense for their workload.

Check out our [multiple executor documentation](https://orion-docs.prefect.io/concepts/executors/#using-multiple-executors) for an example.


### Other notes

While we're excited to talk about these new features, we're always hard at work fixing bugs and improving performance. This release also comes with

- Updates to database engine disposal to support large, ephemeral server flow runs
- Improvements and additions to the `flow-run` and `deployment` command-line interfaces
    - `prefect deployment ls`
    - `prefect deployment inspect <name>`
    - `prefect flow-run inspect <id>`
    - `prefect flow-run ls`
- Clarification of existing documentation and additional new documentation
- Fixes for database creation and startup issues
