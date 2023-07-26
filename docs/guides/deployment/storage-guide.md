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
    - s3
    - azure
    - blob storage
    - bucket
    - AWS
    - GCP
    - GCS
    - Google Cloud Storage
    - Azure Blob Storage
    - Docker
    - storage  
search:
  boost: 2
---

# Where to Store Your Flow Code

When you run a deployment, your execution environment needs access to your flow code. 
Your flow code is not stored in a Prefect server database instance or Prefect Cloud. 
When creating a deployment, you have several flow code storage options.

## Option 1: Local storage
Local flow code storage is often used with a Local Subprocess work pool for initial experimentation. 

To create a deployment with local storage and a Local Subprocess work pool do the following:

1. Run `prefect deploy` from the root of the directory containing your flow code.
1. Select that you want to create a new deployment, select the flow code entrypoint, and name your deployment. 
1. Select a *process* work pool. 

You are then shown the location that your flow code will be fetched from when a flow is run. 
For example:

<div class="terminal">
```bash
Your Prefect workers will attempt to load your flow from: 
/Users/jeffhale/Desktop/prefect/demos/storage/gh_storage_flow.py. To see more options for managing your flow's code, run:

    $ prefect project recipes ls
```
</div>

When creating a production deployment you most likely want code to be capable of running on infrastructure other than your local machine. 

One of the other remote flow code storage options is recommended for production deployments.

## Option 2: Git-based storage

Git-based version control platforms are popular locations for code storage. 
This solution provides redundancy, version control, and easier collaboration.

[GitHub](https://github.com/) is the most popular cloud-based repository hosting provider. 
[GitLab](https://www.gitlab.com) and [Bitbucket](https://bitbucket.org/) are other popular options. 
Prefect supports each of these platforms.

### Creating a deployment with git-based storage

Run `prefect deploy` from within a git repository and create a new deployment. You will see a series of prompts. Select that you want to create a new deployment, select the flow code entrypoint, and name your deployment.

Prefect detects that you are in a git repository and asks if you want to store your flow code in a git repository. Select "y" and you will be prompted to confirm the URL of your git repository and the branch name, as in the example below:

<div class="terminal">
```bash
? Your Prefect workers will need access to this flow's code in order to run it. 
Would you like your workers to pull your flow code from its remote repository when running this flow? [y/n] (y): 
? Is https://github.com/my_username/my_repo.git the correct URL to pull your flow code from? [y/n] (y): 
? Is main the correct branch to pull your flow code from? [y/n] (y): 
? Is this a private repository? [y/n]: y
```
</div>

In this example the git repository is hosted on GitHub. 
If you are using Bitbucket or GitLab, the URL will match the provider.
If the repository is public, enter "n" and you are on your way.

If the repository is private, you can enter a token that can be used to access your private repository. This token will be saved in an encrypted Prefect Secret block. 

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
        repository: https://bitbucket.org/org/my-private-repo.git
        access_token: "{{ prefect.blocks.secret.my-block-name }}"
```

Alternatively, you can create a Credentials block ahead of time and reference it in the `prefect.yaml` pull step.

=== "GitHub"

    1. Install the library with `pip install -U prefect-github`
    1. Register the blocks in that library to make them available on the server with `prefect block register -m prefect_github`.
    1. Create a GitHub credentials block via code or the Prefect UI and reference it as shown above.
    1. In addition to the block name, most users will need to fill in the *GitHub Username* and *GitHub Personal Access Token* fields.

    ```yaml

    pull:
        - prefect.deployments.steps.git_clone:
            repository: https://github.com/discdiver/my-private-repo.git
            credentials: "{{ prefect.blocks.github-credentials.my-block-name }}"
    ```
  
=== "Bitbucket"
    
    1. Install the relevant library with `pip install -U prefect-bitbucket`
    1. Register the blocks in that library with `prefect block register -m prefect_bitbucket` 
    1. Create a Bitbucket credentials block via code or the Prefect UI and reference it as shown above.
    1. In addition to the block name, most users will need to fill in the *Bitbucket Username* and *Bitbucket Personal Access Token* fields.

    ```yaml

    pull:
        - prefect.deployments.steps.git_clone:
            repository: https://bitbucket.org/org/my-private-repo.git
            credentials: "{{ prefect.blocks.bitbucket-credentials.my-block-name }}"
    ```

=== "GitLab"
    
    1. Install the relevant library with `pip install -U prefect-gitlab`
    1. Register the blocks in that library with `prefect block register -m prefect_gitlab` 
    1. Create a GitLab credentials block via code or the Prefect UI and reference it as shown above.
    1. In addition to the block name, most users will need to fill in the *GitLab Username* and *GitLab Personal Access Token* fields.

    ```yaml

    pull:
        - prefect.deployments.steps.git_clone:
            repository: https://gitlab.com/org/my-private-repo.git
            credentials: "{{ prefect.blocks.gitlab-credentials.my-block-name }}"
    ```

!!! Warning "Push your code"
    When you make a change to your code, Prefect does push your code to your git-based version control platform. 
    You need to do push your code manually or as part of your CI/CD pipeline. 
    This design decision is an intentional one to avoid confusion about the git history and push process.

## Option 3: Docker-based storage

Another popular way to store your flow code is to include it in a Docker image. The following work pools use Docker containers, so the flow code can be directly baked into the image:

- Docker
- Kubernetes
- Serverless cloud-based options
    - AWS Elastic Container Service 
    - Azure Container Instances
    - Google Cloud Run
- Push-based serverless cloud-based options (no worker required)
    - AWS Elastic Container Service - Push
    - Azure Container Instances - Push
    - Google Cloud Run - Push

1. Run `prefect init` in the root of your repository and choose `docker` for the project name and answer the prompts to create a `prefect.yaml` file with a build step that will create a Docker image with the flow code built in. See the [Docker guide](/guides/deployment/docker/) for more info.
1. Run `prefect deploy` to create a deployment. 
1. Upon deployment run the worker will pull the Docker image and spin up a container. 
1. The flow code baked into the image will run inside the container. 

## Option 4: Cloud-provider storage
Cloud-provider storage is supported, but not recommended. Git-repository based storage or Docker-based storage are the recommended options due to their version control and collaborative capabilities. 

You can specify an S3 bucket, Azure Blob Storage container, or GCS bucket directly in the `push` and `pull` steps of your `prefet.yaml` file to send your flow code to a cloud-provider storage location and retrieve it at runtime. 

Run `prefect init` and select the relevant cloud-provider storage option.

Here are the options and the relevant portions of the `prefect.yaml`` file.

=== "AWS"

    Choose *s3* as the storage option and enter the bucket name when prompted. TK or the URL 

    ```yaml
    # push section allows you to manage if and how this project is uploaded to remote locations
    push:
    - prefect_aws.deployments.steps.push_to_s3:
        id: push_code
        requires: prefect-aws>=0.3.4
        bucket: my_bucket
        folder: project-name
        credentials: "{{ prefect.blocks.aws-credentials.my-credentials-block }}" # if private

    # pull section allows you to provide instructions for cloning this project in remote locations
    pull:
    - prefect_aws.deployments.steps.pull_from_s3:
        id: pull_code
        requires: prefect-aws>=0.3.4
        bucket: '{{ push_code.bucket }}'
        folder: '{{ push_code.folder }}'
        credentials: "{{ prefect.blocks.aws-credentials.my-credentials-block }}" # if private
    ``` 


=== "Azure"

    Choose *azure*.

    When prompted, enter the container. TK format

    ```yaml
    
    push:
    - prefect_azure.deployments.steps.push_to_azure_blob_storage:
        id: push_code
        requires: prefect-azure>=0.2.8
        container: fdfs TK
        folder: storage

    # pull section allows you to provide instructions for cloning this project in remote locations
    pull:
    - prefect_azure.deployments.steps.pull_from_azure_blob_storage:
        id: pull_code
        requires: prefect-azure>=0.2.8
        container: '{{ push_code.container }}'
        folder: '{{ push_code.folder }}'
    ```

=== "GCP" 

    Choose *gcs*.

    When prompted, enter the bucket. TK format


If you use a cloud storage provider with a private storage bucket/blob/container, you will need to provide credentials for a cloud account. 

If you want to configure a Secret ahead of time for use when deploying a `prefect.yaml` file do the following:

=== "AWS"

    TK are 1 and 2 only necessary if self-hosting? a Prefect server instance? In my cloud workspace they are pre-installed.

    1. Install the relevant library with `pip install -U prefect-aws`
    1. Register the blocks in that library with `prefect block register -m prefect_aws` 
    1. Create an aws-credentials block via code or the Prefect UI. In addition to the block name, most users will need to fill in the *AWS Access Key ID* and *AWS Access Key Secret* fields.
    1. Reference the block as shown above.

    Ensure the role has read and write permissions to access the bucket.

=== "Azure"

    1. Install the relevant library with `pip install -U prefect-azure`
    1. Register the blocks in that library with `prefect block register -m prefect_azure` 
    1. Create a  block via code or the Prefect UI and reference it as shown above.
    1. In addition to the block name, most users will need to fill in the  and  fields.

    Ensure the role has sufficient (read and write) permissions to access the container.

=== "GCP"

    1. Install the relevant library with `pip install -U prefect-gcp`
    1. Register the blocks in that library with `prefect block register -m prefect_gcp` 
    1. Create a GCP block via code or the Prefect UI and reference it as shown above.
    1. In addition to the block name, most users will need to fill in the  and  fields.

    Ensure the role has read and write permissions to access the bucket.

## Including and excluding files from storage

By default, Prefect uploads all files in the current folder to the configured storage location when you create a deployment.

When using a git repository, Docker image, or cloud-provider storage location, you may want to exclude certain files or directories.
- If you are familiar with git you are likely familiar with the [`.gitignore`](https://git-scm.com/docs/gitignore) file. 
- If you are familiar with Docker you are likely familiar with the [`.dockerignore`](https://docs.docker.com/engine/reference/builder/#dockerignore-file) file. 
- For cloud-provider storage the `.prefectignore` file serves the same purpose and follows a similar syntax as those files. So an entry of `*.pyc` will exclude all `.pyc` files from upload.

## Other code storage creation methods

In earlier versions of Prefect [storage blocks](/concepts/blocks/) were the recommended way to store flow code. 
Storage blocks are still supported, but not recommended.

As shown above, repositories can be referenced directly through interactive prompts with `prefect deploy` or in a `prefect.yaml`. 
When authentication is needed, Secret or Credential blocks can be referenced, and in some cases created automatically through interactive deployment creation prompts. 

Another option for authentication is for the [worker](/concepts/work-pools/#worker-overview) to have access to the the storage location via SSH keys.

## Next steps

You've seen options for where to store your flow code. 

We recommend using Docker-based storage or git-based storage for your production deployments.

Check out more [guides](/guides/) to reach your goals with Prefect.