---
description: Learn about the Prefect orchestration engine and API.
tags:
    - work pools
    - agents
    - orchestration
    - database
    - API
    - UI
    - storage
search:
  boost: 2
---

From our previous steps we now have:

1. A flow
2. A work pool
3. A worker
4. An understanding of Prefect Deployments

Now it’s time to put it all together.

In your terminal (not the terminal associated with the worker), let’s run the following command to begin deploying your flow.  Ensure that the current directory is set to the same directory as when you were running the flow locally.  You can double check this by typing `ls` in the terminal and you should see the flow file in the output.

```bash
prefect deploy my_flow.py:get_repo_info
```

This deployment command follows the following format that you can use to deploy your flows in the future:  `prefect deploy path_to_flow/my_flow_file.py:flow_func_name` 

<aside>
☝🏼 Warning:
Ensure that you run the prefect deploy command from the top/root/base of your repo, otherwise the worker may struggle to get to the same entrypoint during remote execution.

</aside>

- <<Screenshot of Deployment Wizard for our reference>>
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/b1087417-16f3-49a2-93e7-9b3897c8f5b0/Untitled.png)
    

Now that you have run the deploy command, the CLI will prompt you through different options you can set with your deployment.

- name your deployment `my-deployment`
- type n for now, you can set up a schedule later
- select the work pool you just created, tutorial-process-pool
- When asked if you would like your workers to pull your flow code from its remote repository, select yes if you’ve been following along and defining your flow code script from within a github repository.
    - y: Reccomended: Prefect will automatically register your GitHub repo as the the location of this flow’s remote flow code. This means a worker started on any machine, on your laptop, on your team-mate’s laptop, or in your cloud provider
    - n: If you would like to continue this tutorial without the use of GitHub, thats ok, Prefect will always look first to see if the flow code exists locally before referring to remote flow code storage.

Prefect becomes powerful when it allows you to trigger flow runs in a variety of executions environments, so understanding how Prefect workers access flow code remotely is an important concept to grasp. 

Note that Prefect has automatically done a few things for you:

- registered the existence of this flow [with your local project](https://docs.prefect.io/concepts/projects/#the-prefect-directory)
- created a description for this deployment based on the docstring of your flow function
- parsed the parameter schema for this flow function in order to expose an API for running this flow

<aside>
☝🏼 Aside from GitHub, Prefect offers a variety of options for remote flow code storage.

</aside>

## Deployment YAML

You can use a deployment.yaml file to define this deployment along with all deployments you might create for a given repository of flow code. 

<aside>
❗ Tip: A flow can have one or many deployments.

</aside>

To start a deployment.yaml file, type:

`prefect project init`

And populate the deployment object information in the `deployment.yaml` like shown below:

```yaml
deployments:
- name: my-deployment
  tags: [my-tag]
  description: a flow that checks github
  schedule: null
  entrypoint: my_flow.py:get_repo_info
  parameters: {}
  work_pool:
    name: tutorial-process-pool
```

The Push/Pull/Build steps help us get our flows out into the universe. Each step contains instructions for an integral part of deployment:

Build

Push

Pull

The Build Section is where we can add steps that, for example, build a docker image on our behalf.

The Push Section contains steps that push our Flow code to remote storage locations, like S3, GCS or Azure blob.

The pull section contains the most important steps which contain instructions for preparing our execution environment to run our deployments.

The build section of `prefect.yaml` is where any necessary side effects for running your deployments are built - the most common type of side effect produced here is a Docker image. If you initialize with the docker recipe, you will be prompted to provide required information, such as image name and tag:

The push section is most critical for situations in which code is not stored on persistent filesystems or in version control. In this scenario, code is often pushed and pulled from a Cloud storage bucket of some kind (e.g., S3, GCS, Azure Blobs, etc.). The push section allows users to specify and customize the logic for pushing this project to arbitrary remote locations.

The pull section is the most important section within the `prefect.yaml` file as it contains instructions for preparing this project for a deployment run. These instructions will be executed each time a deployment created within this project is run via a worker.

- What are Projects?
    - [Projects](https://docs.prefect.io/2.10.12/concepts/projects/) act as both an interface and directory for managing flow code and deployments.
    - Projects can be tailored to the infrastructure and storage that you’d like to use.
        - `prefect recipe ls`
- What are Projects good for?
    - Defining the process of deploying flows.
    - Making your workflows portable.
- Continuation of tutorial steps:
    - `prefect init`
    - exploration of prefect.yaml
        - The `prefect.yaml` file contains default configuration for all deployments created from within this project.
        - GitHub pull step out for now (then maybe add a version with it)