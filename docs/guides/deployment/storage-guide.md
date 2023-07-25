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
If you select yes, Prefect will ask you to confirm the URL of your git repository and the branch name. 

<div class="terminal">
```bash
? Your Prefect workers will need access to this flow's code in order to run it. 
Would you like your workers to pull your flow code from its remote repository when running this flow? [y/n] (y): 
? Is https://github.com/my_username/my_repo.git the correct URL to pull your flow code from? [y/n] (y): 
? Is main the correct branch to pull your flow code from? [y/n] (y): 
? Is this a private repository? [y/n]: y
```
</div>

In the example above, the git repository is linked to GitHub. 
If you are using Bitbucket or GitLab, the URL will match the provider.
If the repository is public, enter "n" and you are on your way.

If the repository is private, enter a token that can be used to access your private repository. This token will be saved in an encrypted Prefect Secret block. 

<div class="terminal">
```bash

? Please enter a token that can be used to access your private repository. This token will be saved as a Secret block via the Prefect API: "123_abc_this_is_my_token"
```
</div>

Verify that you have a new Secret block in your active workspace named in the format "deployment-my-deployment-my-flow-name-repo-token".

Creating personal access tokens is different for each provider.

=== "GitHub"

    See the GitHub docs for [Personal Access Tokens (PATs)](https://docs.github.com/en/github/authenticating-to-github/creating-a-personal-access-token). 

    We recommend using HTTPS with [fine-grained Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token) so that you can limit access by repository. 

    Under *Your Profile->Developer Settings->Personal access tokens->Fine-grained token* choose *Generate New Token* and fill in the required fields. Under *Repository access* choose *Only select repositories* and grant the token permissions for *Contents*.

=== "GitLab"

    We recommend using HTTPS with [Project Access Tokens](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html).

    In your repository in the GitLab UI, select *Settings->Repository->Project Access Tokens* and check *read_repository* under *Select scopes*.


=== "Bitbucket"

    We recommend using HTTPS with Repository [Access Tokens](https://support.atlassian.com/bitbucket-cloud/docs/access-tokens/). 
    
    Create the token with Scopes->Repositories->Read. 


If you want to configure a Secret block ahead of time for use when deploying a `prefect.yaml` file, create the block via code or the Prefect UI and reference it like this:

    ```yaml

    pull:
        - prefect.deployments.steps.git_clone:
            repository: https://bitbucket.org/org/repo.git
            access_token: "{{ prefect.blocks.secret.my-block-name }}"
    ```

<!-- Alternatively, you can create a GitHub, Bitbucket, or GitLab block ahead of time and reference it in the `prefect.yaml` pull step. TK This is currently not working. See https://github.com/PrefectHQ/prefect/issues/9683 and add when fixed.
 -->


!!! Warn "Push your code"
    When you make a change to your code, Prefect does push your code to your git-based version control platform. 
    You need to do push your code manually or as part of your CI/CD pipeline. 
    This design decision is an intentional one to avoid confusion about the git history and push process.

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
        folder: project-name
        credentials: "{{ prefect.blocks.aws-credentials.dev-credentials }}" # if private

    # pull section allows you to provide instructions for cloning this project in remote locations
    pull:
    - prefect_aws.deployments.steps.pull_from_s3:
        id: pull_code
        requires: prefect-aws>=0.3.4
        bucket: '{{ push_code.bucket }}'
        folder: '{{ push_code.folder }}'
        credentials: "{{ prefect.blocks.aws-credentials.dev-credentials }}" # if private
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