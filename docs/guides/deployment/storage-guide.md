---
description: Store your flow code
tags:
    - guides
    - guide
    - flow code
    - storage
    - code storage
    - repository
    - github
    - git
    - gitlab
    - bitbucket
search:
  boost: 2
---

# Flow Code Storage

When you run a deployment, your execution environment needs access to your flow code. 
Your flow code is not stored in either the Prefect Cloud database or a Prefect server database instance. 
When creating a deployment, you have several flow code storage options.

## Option 1: Local storage
Local flow code storage is often used with a process work pool for initial experimentation. 

Run `prefect deploy` from the root of the directory containing your flow code. 
Select that you want to create a new deployment, select the flow code entrypoint, and name your deployment. 
Select a *process* work pool. 
You are then shown the location that your flow code will be fetched from when a flow is run. 
For example:

<div class="terminal">
```bash
Your Prefect workers will attempt to load your flow from: 
/Users/jeffhale/Desktop/prefect/demos/storage/gh_storage_flow.py. To see more options for managing your flow's code, run:

        $ prefect project recipes ls
```
</div>

When creating a production deployment you most likely want code capable of running on infrastructure other than your local machine. 
One of the other remote flow code storage options is recommended for production deployments.

## Option 2: Git-based storage

Git-based version control platforms are popular locations to store code. 
This solution provides redundancy, version control, and easier collaboration.

[GitHub](https://github.com/) is the most popular cloud-based repository hosting provider. 
[GitLab](https://www.gitlab.com) and [Bitbucket](https://bitbucket.org/) are other popular options. 
Prefect supports each of these options.

### Creating a deployment with git-based storage

Run `prefect deploy` from within a git repository and create a new deployment, you will see a series of prompts.
Select that you want to create a new deployment, select the flow code entrypoint, and name your deployment.
Prefect detects that you are in a git repository and asks if you want to store your flow code in a git repository. 
If you select yes, Prefect will ask you to confirm the URL of your git repository, the branch name, and whether the repository is private. 

<div class="terminal">
```bash
    ? Your Prefect workers will need access to this flow's code in order to run it. 
    Would you like your workers to pull your flow code from its remote repository 
    when running this flow? [y/n] (y): 
    ? Is https://github.com/my_username/my_repo.git the correct URL to pull your 
    flow code from? [y/n] (y): 
    ? Is main the correct branch to pull your flow code from? [y/n] (y): 
    ? Is this a private repository? [y/n]: y
```
</div>

In the example above, the git repository is linked to GitHub. If you are using Bitbucket or GitLab, the URL will match the provider.

If the repository is public, enter "n" and you are on your way.

If the repository is private, include a token that can be used to access your private repository. This token will be encrypted and saved in a Prefect block. 

TK there are other ways to get the token in with an environment variables - maybe an advanced guide on that later.

<div class="terminal">
```bash
You will then be asked to enter an authentication token that will be stored in a Prefect block.

    ? Please enter a token that can be used to access your private repository. This 
    token will be saved as a secret via the Prefect API: "123_abc_this_is_my_token"
```
</div>

TK - can you also reference an existing gh, bb, or gl credential block?

Authentication options for the different providers:

=== "GitHub"
    Personal Access Tokens (PATs) - Classic and fine grained.
    SSH keys.

    GitHub docs on [PATs](https://docs.github.com/en/github/authenticating-to-github/creating-a-personal-access-token) and [SSH keys](https://docs.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh).

=== "GitLab"
    [GitLab docs](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) on PATs. 

    A private GitLab token that goes into a Prefect block require Prefect GitLab integration or not? TK
    
    GitLab docs on PATs are here: https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html and SSH keys are here: https://docs.gitlab.com/ee/ssh/.

=== "Bitbucket"

     A private Bitbucket token that goes into a Prefect block require Prefect GitLab integration or not?

    Bitbucket docs on PATs are here: https://confluence.atlassian.com/bitbucketserver072/personal-access-tokens-1005335924.html and SSH keys are here: https://confluence.atlassian.com/bitbucketserver072/ssh-access-keys-for-system-use-1008045886.html.


Does your worker need to have the same authentication as your git repo? TK
E.g. Worker is in K8s or a push work pool.

!!! Warn "Push your code"
    When you make a change to your code or a deployment, Prefect does not automatically push your code to your git-based version control platform. 
    You need to do push your code manually or as part of your CI/CD pipeline. 
    This design decision is an intentional one to avoid confusion about the code push process.

## Option 3: Docker-based storage

Another popular way to store your flow code is to bake it directly into a Docker image. The following work pools use Docker containers, so the flow code can be directly baked into the image:

- Docker
- Kubernetes
- Serverless cloud-based options
    - AWS ECS
    - GCP Cloud Run
    - Microsoft ACI
- Push-based serverless cloud-based options
    - AWS ECS
    - GCP Cloud Run
    - Microsoft ACI

You can create your own Docker image or use the `prefect deploy` prompts or an existing `prefect.yaml` file's build step to create a Docker image.
Then, when you run a deployment, the worker will pull the Docker image and spin up a container. 
The flow code baked into the image will run in the container.

## Option 4: Cloud-provider storage
Cloud-provider storage is supported, but not recommended. Git-repository based storage or Docker-based storage are the recommended options due to their version control and collaborative capabilities. 

You can specify an S3 bucket, Azure Blob Storage container, or GCS bucket directly in the `push` and `pull` steps of your `prefet.yaml` to send your flow code to a cloud-provider storage location and retrieve it at runtime. 

Run `prefect init` and select the relevant cloud-provider storage option

Here's the relevant portion of an example `prefect.yaml`` file.

=== "AWS"

    Choose `s3` as the storage option and enter the bucket name when prompted. 

    
    ```yaml
    # push section allows you to manage if and how this project is uploaded to remote locations
    push:
    - prefect_aws.deployments.steps.push_to_s3:
        id: push_code
        requires: prefect-aws>=0.3.4
        bucket: my_bucket
        folder: prefect

    # pull section allows you to provide instructions for cloning this project in remote locations
    pull:
    - prefect_aws.deployments.steps.pull_from_s3:
        id: pull_code
        requires: prefect-aws>=0.3.4
        bucket: '{{ push_code.bucket }}'
        folder: '{{ push_code.folder }}'
    ``` 

    TK, can you use a block (from s3 or S3 block?) 

=== "GCS" 

=== "Azure Blob Storage"


If you use this option with a private storage bucket, you will need to provide credentials for a cloud account role with sufficient permissions via a block or other method. 
Also ensure that your Prefect worker has the correct credentials to access the cloud-provider storage location.

## Other code storage options
In versions of Prefect 2 before the`prefect deploy` experience, storage blocks were the recommended way to store flow code. 
Storage blocks are still supported, but are usually only necessary if you need to authenticate to a private repository. 
As shown above TK link, the credential blocks for git-based storage can be created automatically through the interactive deployment creation prompts.