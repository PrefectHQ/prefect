# Upgrade from Agents to Workers

Upgrading from agents to workers significantly enhances the experience of deploying flows. It simplifies the specification of each flow's infrastructure and runtime environment. 

A [worker](/concepts/work-pools/#worker-overview) is the fusion of an [agent](/concepts/agents/) with an [infrastructure block](/concepts/infrastructure/). Like agents, workers poll a work pool for flow runs that are scheduled to start. Like infrastructure blocks, workers are typed - they work with only one kind of infrastructure and they specify the default configuration for jobs submitted to that infrastructure.

Accordingly, workers are not a drop-in replacement for agents. **Using workers requires deploying flows differently.** In particular, deploying a flow with a worker does not involve specifying an infrastructure block. Instead, infrastructure configuration is specified on the [work pool](/concepts/work-pools/) and passed to each worker that polls work from that pool.

This guide provides an overview of the differences between agents and workers. It also describes how to upgrade from agents to workers in just a few quick steps.

## Enhancements

### Agents to workers

- Improved visibility into the status of each worker, including when a worker was started and when it last polled.
- Better handling of race conditions for high availability use cases.

### Agent infrastructure blocks to work pools

- Work pools expose a [base job template](/concepts/work-pools/#base-job-template) that enables an unprecedented level of customization and governance over workers in that pool.
- [Push work pools](/guides/deployment/push-work-pools/) allow for flow execution without the need to host a worker at all.

### New `prefect.yaml` file for managing multiple deployments

- More easily define multiple deployments at once through a [`prefect.yaml`](/concepts/deployments/#managing-deployments) file.
- Prefect provides [deployment actions](/concepts/deployments/#deployment-actions) that allow you to automatically build images for your flows.
- [Templating](/concepts/deployments/#templating-options) enables [dryer deployment definitions](/concepts/deployments/#reusing-configuration-across-deployments).
- You can use a deployment creation [wizard now](/#step-5-deploy-the-flow)! 🧙

----------

## What's different

1. **Command to build deployments:** 
    
    `prefect deployment build <entrypoint>` --> [`prefect deploy`](/concepts/deployments/#deployment-declaration-reference) 
    
    Prefect will now automatically detect flows in your repo and provide a [wizard](/#step-5-deploy-the-flow) 🧙 to guide you through setting required attributes for your deployments.

2. **Configuring remote flow code storage:** 
    
    storage blocks --> [pull action](/concepts/deployments/#the-pull-action)
    
    And you can still use an existing [storage block as your pull action](/guides/deployment/storage-guide/)!  The more general pull steps specification allows for explicit customization of the job that defines each run (for example, by adding an additional step that sets a working directory).

3. **Configuring flow run infrastructure:** 
    
    run-infrastructure blocks --> [typed work pool](/concepts/work-pools/#worker-types) 
    
    Default infra config is now set on the typed work pool, and can be overwritten by both individual deployments or individual runs.

4. **Managing multiple deployments:**
    
    Create and/or update many deployments at once through a [`prefect.yaml`](/concepts/deployments/#working-with-multiple-deployments) file.


## What's similar

- Storage blocks can be set as the pull action in a `prefect.yaml` file.
- Infrastructure blocks have similar configuration fields as typed work pools.
- Deployment-level infra-overrides operate in much the same way. 

    `infra_override` -> [`job_variable`](/concepts/deployments/#work-pool-fields)

- The process for starting an agent and [starting a worker](/concepts/work-pools/#starting-a-worker) in your environment are virtually identical.
    
    `prefect agent start --pool <work pool name>` --> `prefect worker start --pool <work pool name>`

    !!! Tip "If you use infrastructure-as-code"
        Notice the command to start a worker is very similar to the command to start an agent. If you previously used terraform, a [helm chart](https://github.com/PrefectHQ/prefect-helm/tree/main/charts/prefect-worker), or other infrastructure-as-code methods to start an agent, you should be able to continue using it for a worker, provided all uses of `agent` are changed to `worker`.

## How to upgrade quickly

If you have existing deployments that use infrastructure blocks, you can quickly upgrade them to be compatible with workers by following these steps:

1. [Create a work pool](/concepts/work-pools/#work-pool-configuration) of the same type as the infrastructure block you are currently using.

    1. Any work pool infrastructure type other than `Prefect Agent` will work.
    2. Referencing the configuration you've set on the infrastructure block, set similar flow run infrastructure configuration on the work pool.

2. [Start a worker](/concepts/work-pools/#starting-a-worker) to poll this work pool. You should see the command to start the worker as soon as you save your new work pool. 

    ```
    prefect worker start -p <work pool name>
    ```

3. [Deploy your flow](/#step-5-deploy-the-flow) guided by the deployment creation wizard:

    !!! warning "Always run `prefect deploy` commands from the **root** level of your repo!"
        With agents you might have had multiple `deployment.yaml` files, but under worker deployment patterns, each repo will have a single `prefect.yaml` file located at the **root** of the repo that contains [deployment configuration](/concepts/deployments/#working-with-multiple-deployments) for all flows in that repo.

    ```bash
    prefect deploy
    ```

    !!! Note "For step 4, select `y` on last prompt to save the configuration for the deployment."
        Saving the configuration for your deployment will result in a `prefect.yaml` file populated with your first deployment. You can use this YAML file to edit and [define multiple deployments](/concepts/deployments/#working-with-multiple-deployments) for this repo. 

4. In your `prefect.yaml` file, configure a [pull action](/guides/deployment/storage-guide/) referencing whatever configuration you used as your storage block.
5. Continue to create more [deployments](/concepts/deployments/#deployment-declaration-reference) that use workers by either adding them to the `deployments` list in the `prefect.yaml` file and/or by continuing to use the deployment creation wizard.

