# Building Blocks of Deployment

[[toc]]

## Registration

As noted before, when you register your Flows with Prefect Cloud no actual code from your Flows and Tasks are sent during registration. Instead Prefect Cloud is sent a serialized _description_ of your Flow. This consists of aspects such as name, type, schedule, graph structure, environment, storage, etc. In the _ETL_ Flow from the previous document the serialized description of the Flow looks something like this (truncated for clarity):

```json
{
   "name":"ETL",
   "type":"prefect.core.flow.Flow",
   "schedule":"None",
   "parameters":[],
   "tasks":[...],
   "edges":[...],
   "reference_tasks":[],
   "environment":{
      "labels":[
         "your-machine.localdomain"
      ],
      "executor":"prefect.engine.executors.LocalExecutor",
      "executor_kwargs":{},
      "__version__":"0.8.0",
      "type":"RemoteEnvironment"
   },
   "__version__":"0.8.0",
   "storage":{
      "directory":"/Users/you/.prefect/flows",
      "flows":{
         "ETL":"/Users/you/.prefect/flows/etl.prefect"
      },
      "__version__":"0.8.0",
      "type":"Local"
   }
}
```

The key parts of this serialized version of your Flow that need some explanation are the `storage` and `environment`.

## Storage

Storage is the part of Flow deployment that states _how_ and _where_ a Flow is stored. Before a Flow is registered with Prefect Cloud its storage object is invoked in order to put the Flow's actual code into a known location so that when you deploy that Flow to your infrastructure it can be retrieved and executed. In this example the Flow uses its default [Local Storage]() which means your Flow will be stored in your root `/.prefect/flows` directory.

As you may be able to tell there are other storage types in Prefect such as [Docker](), [S3](), [GCS](), etc. Each storage type is appropriate for different platforms of deployment akin to your choosing. For example Local Storage is appropriate when storing and deploying Flows on a singular machine using the [Local Agent](/cloud/agent/local.html) while Docker Storage is useful when you want to store your Flow code in a [container registry](https://docs.docker.com/registry/) and deploy to platforms like [Kubernetes](/cloud/agent/kubernetes.html) or [AWS Fargate](/cloud/agent/fargate.html).

## Environments

While storage deals with _how_ and _where_ a Flow is stored, Environments are responsible for determining _how_ to execute your Flow. This means that if you want to run your Flow using an ephemeral Dask cluster on Kubernetes you could use the pre-built [Dask Kubernetes Environment](/cloud/execution/dask_k8s_environment.html) or if you only want to run your Flow without any extra infrastructure needs you could do it using the default [Remote Environment](/cloud/execution/remote_environment.html). The Remote Environment is an Environment that runs your Flow in process during deployment and allows for [executor](/core/concepts/engine.html#executors) specification if desired, otherwise, it will use the default [Local Executor](/api/unreleased/engine/executors.html#localexecutor). By default the Remote Environment is attached to all Flows registered to Prefect Cloud however there are other other pre-built environments for your choosing and if none of those satisfy your needs Prefect allows for completely [custom environments](/cloud/execution/custom_environment.html)!

_For more information on Storage and Environments visit the relevant [Execution Overview](/cloud/execution/overview.html) doc._

## Agents

Agents are responsible for partitioning the necessary infrastructural resources for deploying your Flows and are tasked with the job of deploying your Flows. When an Agent is started it polls Prefect Cloud looking for work. Once it finds Flow Runs which are ready to be deployed it will grab the information about the registered Flow (storage, environment, etc.) and use it to deploy the Flow to the Agent's platform.

_For more information on Agents visit the relevant [Agent Overview](/cloud/agent/overview.html) doc._

## How Everything Fits Together

