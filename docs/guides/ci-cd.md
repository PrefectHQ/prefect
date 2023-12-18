---
description: CI/CD resources for working with Prefect.
tags:
    - CI/CD
    - continuous integration
    - continuous delivery
search:
  boost: 2
---

# CI/CD with Prefect

Prefect is used by many organizations in their CI/CD pipelines.
Each organization has their own unique setup, but there are some common patterns.
This guide provides links to repositories and resources that may be helpful when setting up Prefect in your CI/CD pipeline.
This guide is not meant to be exhaustive, but should provide you with jumping off points for your own setup.

Note that Prefect's `.deploy` flow method and `prefect.yaml` configuration file are both designed with building and pushing images to a Docker registry in mind.

## Getting started with GitHub Actions and Prefect

In this example, you'll write a GitHub Actions workflow that will run each time you push to your repository's `main` branch. This workflow will build and push a Docker image containing your flow code to Docker Hub, then deploy the flow to Prefect Cloud.

### Repository secrets

Your CI/CD pipeline must be able to authenticate to Prefect in order to deploy flows.

Deploying flows securely and non-interactively in your CI/CD pipeline can be accomplished by saving your `PREFECT_API_URL` and `PREFECT_API_KEY` [as secrets in your repository's settings](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions) so they can be accessed in your CI/CD runner's environment without exposing them in any scripts or configuration files.

Since deploying flows in this scenario also includes building and pushing Docker images, add `DOCKER_USERNAME` and `DOCKER_PASSWORD` as secrets to your repository as well.

You can create secrets for GitHub Actions in your repository under **Settings -> Secrets and variables -> Actions -> New repository secret**:

![Creating a GitHub Actions secret](/img/guides/github-secrets.png)

### Writing a GitHub workflow

To deploy your flow via GitHub Actions, you'll need a workflow YAML file. GitHub will look for workflow YAML files in the `.github/workflows/` directory in the root of your repository. In their simplest form, GitHub workflow files are made up of triggers and jobs.

The `on:` trigger is set to run the workflow each time a push occurs on the `main` branch of the repository.

The `deploy` job is comprised of four `steps`:

- **`Checkout`** clones your repository into the GitHub Actions runner so you can reference files or run scripts from your repository in later steps.
- **`Log in to Docker Hub`** authenticates to DockerHub so your image can be pushed to the Docker registry in your DockerHub account. [docker/login-action](https://github.com/docker/login-action) is an existing GitHub action maintained by Docker and is compatible with a wide range of image registry services. `with:` passes values into the Action, similar to passing parameters to a function.
- **`Setup Python`** installs your selected version of Python.
- **`Prefect Deploy`** installs the dependencies used in your flow, then deploys your flow. `env:` makes the `PREFECT_API_KEY` and `PREFECT_API_URL` secrets from your repository available as environment variables during this step's execution.

=== ".deploy"

    `flow.py`

    ```python
    from prefect import flow

    @flow(log_prints=True)
    def hello():
      print("Hello!")

    if __name__ == "__main__":
        hello.deploy(
            name="my-deployment",
            work_pool_name="my-work-pool",
            image="my_registry/my_image:my_image_tag",
        )
    ```

    `.github/workflows/deploy-prefect-flow.yaml`

    ```yaml
    name: Deploy Prefect flow

    on:
      push:
        branches:
          - main

    jobs:
      deploy:
        name: Deploy
        runs-on: ubuntu-latest

        steps:
          - name: Checkout
            uses: actions/checkout@v4

          - name: Log in to Docker Hub
            uses: docker/login-action@v3
            with:
              username: ${{ secrets.DOCKER_USERNAME }}
              password: ${{ secrets.DOCKER_PASSWORD }}

          - name: Setup Python
            uses: actions/setup-python@v5
            with:
              python-version: '3.11'

          - name: Prefect Deploy
            env:
              PREFECT_API_KEY: ${{ secrets.PREFECT_API_KEY }}
              PREFECT_API_URL: ${{ secrets.PREFECT_API_URL }}
            run: |
              pip install -r requirements.txt
              python flow.py
    ```

=== "prefect.yaml"

    `flow.py`

    ```python
    from prefect import flow

    @flow(log_prints=True)
    def hello():
      print("Hello!")
    ```

    `prefect.yaml`

    ```yaml
    name: cicd-example
    prefect-version: 2.14.11

    build:
      - prefect_docker.deployments.steps.build_docker_image:
          id: build_image
          requires: prefect-docker>=0.3.1
          image_name: my_registry/my_image
          tag: my_image_tag
          dockerfile: auto

    push:
      - prefect_docker.deployments.steps.push_docker_image:
          requires: prefect-docker>=0.3.1
          image_name: "{{ build_image.image_name }}"
          tag: "{{ build_image.tag }}"

    pull: null

    deployments:
      - name: my-deployment
        entrypoint: flow.py:hello
        work_pool:
          name: my-work-pool
          work_queue_name: default
          job_variables:
            image: "{{ build-image.image }}"
    ```

    `.github/workflows/deploy-prefect-flow.yaml`

    ```yaml
    name: Deploy Prefect flow

    on:
      push:
        branches:
          - main

    jobs:
      deploy:
        name: Deploy
        runs-on: ubuntu-latest

        steps:
          - name: Checkout
            uses: actions/checkout@v4

          - name: Log in to Docker Hub
            uses: docker/login-action@v3
            with:
              username: ${{ secrets.DOCKER_USERNAME }}
              password: ${{ secrets.DOCKER_PASSWORD }}

          - name: Setup Python
            uses: actions/setup-python@v5
            with:
              python-version: '3.11'

          - name: Prefect Deploy
            env:
              PREFECT_API_KEY: ${{ secrets.PREFECT_API_KEY }}
              PREFECT_API_URL: ${{ secrets.PREFECT_API_URL }}
            run: |
              pip install -r requirements.txt
              prefect deploy -n my-deployment
    ```

## Prefect GitHub Actions

Prefect provides its own GitHub Actions for [authentication](https://github.com/PrefectHQ/actions-prefect-auth) and [deployment creation](https://github.com/PrefectHQ/actions-prefect-deploy). These actions can simplify deploying with CI/CD when using `prefect.yaml`, especially in cases where a repository contains flows that are used in multiple deployments across multiple Prefect Cloud workspaces. 

Here's an example of integrating these actions into the pipeline we created above:

```yaml
name: Deploy Prefect flow

on:
  push:
    branches:
      - main

jobs:
  deploy:
    name: Deploy
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Prefect Auth
        uses: PrefectHQ/actions-prefect-auth@v1
        with:
          prefect-api-key: ${{ secrets.PREFECT_API_KEY }}
          prefect-workspace: ${{ secrets.PREFECT_WORKSPACE }}

      - name: Run Prefect Deploy
        uses: PrefectHQ/actions-prefect-deploy@v3
        with:
          deployment-names: my-deployment
          requirements-file-paths: requirements.txt
```

## Additional examples

The following examples use GitHub Actions and can be adapted to other CI/CD tools.

| Description | Link |
| --- | --- |
| Deploy an image to AWS ECR when pushing to main. Uses `.deploy`  | [repo_link]()  |
| Deploy an image to AWS ECR when pushing to main. Uses `prefect.yaml`  | [repo_link]()  |






## Other resources

Check out the [Prefect Cloud Terraform provider](https://registry.terraform.io/providers/PrefectHQ/prefect/latest/docs/guides/getting-started) if you're using Terraform to manage your infrastructure.
