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