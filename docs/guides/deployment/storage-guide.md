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

When you run a deployment, your execution environment needs access your flow code. Your flow code is not stored in the Prefect Cloud database or a prefect server database instance. When creating a deployment, you have several options for flow code storage.

## Option 1: Local storage
Local flow code storage is recommended for initial experimentation only. When creating a deployment you likely will want code capable of running on infrastructure other than your local machine. A version-controlled system accessible to other team members with redundancy is a best practice. One of the other remote flow code storage options is recommended for production deployments.

## Option 2: Git-based storage

A git repository is a popular location to store your code. When a git repository is hosted in the cloud you gain easier collaboration and redundancy, in addition to version control.

[GitHub](https://github.com/) is the most popular cloud-based repository hosting provider. [GitLab](https://www.gitlab.com) and [Bitbucket](https://bitbucket.org/) are other popular options.

### Creating a deployment with git-based storage

If you run `prefect deploy` from within a git repository and create a new deployment, Prefect presents a series of prompts.

Select that you want to create a new deployment, select the flow code entrypoint, and name your deployment.

Prefect detects that you are in a git repository and asks if you want to store your flow code in a git repository. If you select yes, Prefect will ask for the URL of your git repository and the branch name. 

<div class="terminal">
```bash
    ? Your Prefect workers will need access to this flow's code in order to run it. 
    Would you like your workers to pull your flow code from its remote repository 
    when running this flow? [y/n] (y): 
    ? Is https://github.com/my_username/my_repo.git the correct URL to pull your 
    flow code from? [y/n] (y): 
    ? Is main the correct branch to pull your flow code from? [y/n] (y): 
    ? Is this a private repository? [y/n]: y
    ? Please enter a token that can be used to access your private repository. This 
    token will be saved as a secret via the Prefect API: "123_abc_this_is_my_token"
```
</div>

TK show more of example here.

If the repository is public, you can skip the authentication step. If the repository is private, include a token that can be used to access your private repository. This token will be encrypted and saved in a Prefect block. 

Authentication options:

=== "GitHub"
    Personal Access Tokens (PATs) - Classic and fine grained.
    SSH keys.

    GitHub docs on [PATs](https://docs.github.com/en/github/authenticating-to-github/creating-a-personal-access-token) and [SSH keys](https://docs.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh).

=== "GitLab"
    [GitLab docs](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html) on PATs. 

    TK link to George's guide, or George fold in here

    A private GitLab token that goes into a Prefect block require Prefect GitLab integration or not?
    
    GitLab docs on PATs are here: https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html and SSH keys are here: https://docs.gitlab.com/ee/ssh/.

=== "Bitbucket"

     A private Bitbucket token that goes into a Prefect block require Prefect GitLab integration or not?

    Bitbucket docs on PATs are here: https://confluence.atlassian.com/bitbucketserver072/personal-access-tokens-1005335924.html and SSH keys are here: https://confluence.atlassian.com/bitbucketserver072/ssh-access-keys-for-system-use-1008045886.html.

    TK link to Taylor's guide, or Taylor fold in here

Does your worker need to have the same authentication as your git repo?

E.g. Worker is in K8s or a push work pool.

!!! Warn
When you make a change to your code, Prefect does not push your code to your cloud-based repository. You will need to do push your code manually or as part of your CI/CD pipeline. This design decision is to avoid confusion about the code push process.

## Option 2: Docker-based storage

Another popular way to store your flow code is directly inside a Docker image. 

When you create a deployment via the interactive prompts, specify a Docker-type [work pool](). You can create a Docker-type pool via the UI or the CLI. TK links. 

Then, when you run a flow, the Prefect worker (which matched the Docker work pool type) will pull the Docker image and spin up a container. The flow code baked into the image will be available in the container.

TK Link to Matt's guide or Matt, fold your guide into this one.

Your team can version control your Docker image via tags in a Docker registry. Your Docker image code can be version controlled in a git repository.

## Option 4: Cloud-provider storage
Cloud-provider storage is supported, but not recommended. Git-repository based storage or Docker-based storage are the recommended options due to their version control and collaborative capabilities. 

You can specify an S3 bucket, Azure storage blob, or GCP GCS bucket address directly in the `push` and `pull` steps of your `prefet.yaml` to send your flow code to a cloud-provider storage location. 

If you use this option with a private storage bucket, you will need to provide credentials for a cloud account role with suffiicient permissions via a block or other method. Also ensure that your Prefect worker has the correct credentials to access the cloud-provider storage location.

## Other code storage options
In versions of Prefect 2 before the`prefect deploy` experience, storage blocks were the recommended way to store flow code. Storage blocks are still supported, but are usually only necessary if you need to authenticate to a private repository. As you saw above, the credential blocks for git-based storage can be created automatically through the interactive deployment creation prompts.