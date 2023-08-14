# How to Upgrade from Agents to Workers

Upgrading from agents to workers significantly enhances the experience of deploying flows, especially with regards to specifying its infrastructure and runtime environment. This guide provides an overview of the differences between agents and workers and describes how to upgrade.

## Enhancements

### Agents to workers

- Improved visibility into the status of each worker, including when a worker was started and when it last polled.
- Better handling of race conditions for high availability use cases.

### Agent infrastructure blocks to work pools

- Work pools expose a [base job template](/concepts/work-pools/#base-job-template) that enables an unprecedented level of customization and governance over workers in that pool.
- New [push work pools](/guides/deployment/push-work-pools/) (beta) allow for flow execution without the need to host a worker.

### New `prefect.yaml` file for managing multiple deployments

- More easily define many multiple deployments at once through a [`prefect.yaml`](/concepts/deployments/#managing-deployments) file.
- Prefect provides [deployment actions](/concepts/deployments/#deployment-actions) that allow you to automatically build images for your flows.
- [Templating](/concepts/deployments/#templating-options) enables [dryer deployment definitions](/concepts/deployments/#reusing-configuration-across-deployments).
- You can use a [wizard now](/#step-5-deploy-the-flow)! 🧙

----------

## What's different

1. **Command to build deployments:** 
    
    `prefect deployment build <entrypoint>` --> [`prefect deploy`](/concepts/deployments/#deployment-declaration-reference) 
    
    Prefect will now automatically detect flows in your repo and provide a [wizard](/#step-5-deploy-the-flow) 🧙 to guide you through setting required attributes for your deployments.

2. **Configuring remote flow code storage:** 
    
    storage blocs --> [pull action](/concepts/deployments/#the-pull-action)
    
    Though you can still use an existing [storage block as your pull action](/guides/deployment/storage-guide/)!

3. **Configuring flow run infrastructure:** 
    
    run-infrastructure blocks --> [typed work pool](/concepts/work-pools/#worker-types) 
    
    Infra config is now set on the typed work pool.

4. **Managing multiple deployments:**
    
    Create and/or update many deployments at once through a [`prefect.yaml`](/concepts/deployments/#managing-deployments) file.


## What's the same

- Storage blocks can be set as the pull action in a `prefect.yaml` file.
- Infra blocks have similar configuration fields as typed work pools.
- Deployment-level infra-overrides operate in much the same way. 

    `infra_override` -> [`job_variable`](/concepts/deployments/#work-pool-fields)

- The process for starting an agent and [starting a worker](/concepts/work-pools/#starting-a-worker) in your environment are virtually identical.
    
    `prefect agent start <work pool>` --> `prefect worker start <work pool>`


## How to get started quickly

If you have a deployment with a storage block and infra block, here's how to quickly upgrade it to use Prefect's new features:

1. [Create a work pool](/concepts/work-pools/#work-pool-configuration) of the same type as the infrastructure block you are currently using.

    1. Any work pool infrastructure type other than `Prefect Agent` will work.
    2. Referencing the configurations you've set on the infrastructure block, set similar flow run infrastructure configurations on the work pool.

2. [Start a worker](/concepts/work-pools/#starting-a-worker) to poll this work pool. You should see the command to start the worker as soon as you save your new work pool. 

    !!! Tip "Process for starting a worker is very similar to the process for starting an agent"
        Notice the command to start a worker is very similar to the command to start an agent. If you previously used terraform, a helm chart, or other infrastructure-as-code method to start an agent, you should be able to continue using it for a worker, provided the word `agent` is changed to `worker`.

3. [Deploy your flow](/concepts/deployments/#deployment-mechanics):
    ```bash
    prefect deploy
    ```
4. In your prefect.yaml file, configure a [pull action](/guides/deployment/storage-guide/) referencing whatever configuration you used as your storage block.

