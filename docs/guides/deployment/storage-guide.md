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

When your run a deployment, your execution environment needs access your flow code. Your flow code is not stored in the Prefect Cloud database or a prefect server database instance. You have several choices of where to shore your flow code.

TK idea: image of deployment with flow code part higlighted - could use similar image with relevant sections highlighted in guides and concepts

## Option 1: Git-based storage

A git repository is a popular location to store your code. When git repositories are hosted in the cloud you gain collaboative tools, version-control, and redunancy.

GitHub is the most common cloud-based repository hosting provider. You can also use GitLab or Bitbucket.

When you run `prefect deploy` in the root of an existing git repo to create a deployment, Prefect detects that you are in a repository.

If you would like to use a GitHub repository, you can clone the public repository at `https://github.com/PrefectHQ/test_flows` or use your own repository.

In the root of your deployment repositry run

```bash
    prefect deploy
```

You will then see a series of prompts.

Select that you want to creata new deployment, select the flow code entrypoint, and name your deployment.


 If you do not have a prefect.yaml file that specifies a pull step you will see the following prompts:

```bash

    ? Your Prefect workers will need access to this flow's code in order to run it. 
    Would you like your workers to pull your flow code from its remote repository 
    when running this flow? [y/n] (y): 
    ? Is https://github.com/my_username/my_repo.git the correct URL to pull your 
    flow code from? [y/n] (y): 
    ? Is main the correct branch to pull your flow code from? [y/n] (y): 
    ? Is this a private repository? [y/n]: y
    ? Please enter a token that can be used to access your private repository. This 
    token will be saved as a secret via the Prefect API:
```

TK show more of example here.

If the repository is public, you can skip the authentication step. If the repository is private, include a token that can be used to access your private repository. This token will be encrypted and saved in a Prefect block.

Authentication options:

=== "GitHub"
    Personal Access Tokens (PATs) - Classic and fine grained.
    SSH keys.

=== "GitLab"
    [GitLab docs](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) on PATs. 

    TK link to George's guide, or George fold in here

=== "Bitbucket"
    [Bitbucket docs](https://confluence.atlassian.com/bitbucketserver072/personal-access-tokens-1005335924.html) on PATs.

    TK link to Taylor's guide, or Taylor fold in here

If you don't specify one of the above, but your worker is running in an authenticated environment. TK Docker and service accts.

When you make a change to your code, Prefect does not push your code to your cloud-based repository. You will need to do push your code manually.

## Option 2: Docker-based storage

Another popular way to store your flow code is directly in a Docker image. 

When you create a deployment via the interactive prompts, specify a Docker-type work pool. You can create a Docker-type pool via the UI or the CLI. TK links. 

Then, when you run a flow, the Prefect worker (which matched the work pool type Docker) will pull the Docker image and spin up a container. The flow code baked into the image will be available in the container.

TK Link to Matt's guide or Matt, fold your guide into this one.

## Option 3: Local storage
This method is only suggested for testing. If you are creating a deployment, you likey want a version-controlled system accessible to other team members, and capable of running on infrastructure other than your local machine. One of the other remote flow code storage options is recommended.

## Option 4: Cloud-provider storage
Cloud-provider storage is supported, but not recommended. Git-repository based storage or Docker-based storage are the recommended options due to their version control and collaborative capabilities. 

You can specify an S3 bucket, Azure storage blob, or GCP GCS bucket address directly in the `push` and `pull` steps of your `prefet.yaml`. 

In earlier versions of Prefect 2, storage blocks were the recommended way to store flow code. Storage blocks are still supported, but are usually only necessary if you need to authenticate to a private repository. These credential blocks for git-based storage can be created automatically through the interactive deployment creation prompts.