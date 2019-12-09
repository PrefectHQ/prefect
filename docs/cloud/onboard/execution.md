# Building Blocks of Deployment

[[toc]]

## Registration

As noted before, registering a Flow sends none of your actual code to Prefect Cloud; it sends a serialized _description_ of your Flow. This description contains attributes such as name, type, schedule, graph structure, environment, storage, etc. In the _ETL_ Flow from the previous document the serialized description of the Flow looks something like this (truncated for clarity):

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

Storage states _how_ and _where_ a Flow is stored. Before a Flow is registered with Prefect Cloud, its storage object is invoked in order to put the Flow's actual code into a known location. Once this is done, the Flow can be retrieved and executed once the Flow is deployed to your infrastructure. In this example the Flow uses its default [Local Storage]() which means your Flow will be stored in your root `/.prefect/flows` directory.

There are other storage types in Prefect such as [Docker](), [S3](), [GCS](), etc., each tailored to your platform of choice. For example Local Storage is appropriate when storing and deploying Flows on a singular machine using the [Local Agent](/cloud/agent/local.html) while Docker Storage is useful when you want to store your Flow code in a [container registry](https://docs.docker.com/registry/) and deploy to platforms like [Kubernetes](/cloud/agent/kubernetes.html) or [AWS Fargate](/cloud/agent/fargate.html).

## Environments

While storage deals with _how_ and _where_ a Flow is stored, Environments are responsible for determining how your Flow is _executed_. Running a Flow using an ephemeral Dask cluster on Kubernetes you could mean using the pre-built [Dask Kubernetes Environment](/cloud/execution/dask_k8s_environment.html), or running a Flow without additional infrastructure needs could be done using the default [Remote Environment](/cloud/execution/remote_environment.html). Registered Flows default to the Remote Environment, but Prefect offers other pre-built environments for your choosing. Should none of those satisfy your needs, Prefect allows for completely [custom environments](/cloud/execution/custom_environment.html).

_For more information on Storage and Environments visit the relevant [Execution Overview](/cloud/execution/overview.html) doc._

## Agents

Agents have two responsibilities: partitioning the necessary infrastructural resources for deploying your Flows and deploying your Flows. Once started, an Agent polls Prefect Cloud looking for work. As soon as it finds Flow Runs, it will grab the information about the registered Flow (storage, environment, etc.) and use it to deploy the Flow to the Agent's platform.

_For more information on Agents visit the relevant [Agent Overview](/cloud/agent/overview.html) doc._

#### What's Next

Now that you have registered your first Flow, executed it with an in-process Local Agent, and read through the fundamental building blocks of Flow deployment with Prefect Cloud the next step is to learn about standing up a Local Agent with supervisor!
