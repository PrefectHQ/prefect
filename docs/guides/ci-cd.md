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

Prefect is used by many organizations in CI/CD pipelines.
Each organization has their own unique setup, but there are some common patterns.
This guide provides links to repositories and resources that may be helpful when setting up Prefect in your CI/CD pipeline.
This guide is not meant to be exhaustive, but should provide you with jumping off points for your own setup.

Note that Prefect's `.deploy` flow method and ``prefect.yaml` configuration file are both designed with building and pushing images to a registry in mind.

## Prefect deployments

The following examples use GitHub Actions and can be adapted to other CI/CD tools.

| Description | Link |
| --- | --- |
| Deploy an image to AWS ECR when the contents of a file change. Uses `.deploy`  | [https://github.com/kevingrismore/prefect-select-actions]  |
| Deploy an image to Dockerhub. Uses `prefect.yaml`  |  |

TK Or maybe better format

- [Deploy an image to AWS ECR when the contents of a file change. Uses `.deploy`](https://github.com/kevingrismore/prefect-select-actions)

## Prefect GitHub Action

Prefect provides its own [GitHub Action for deployment creation](https://github.com/PrefectHQ/actions-prefect-deploy). TK not sure if you use this in your examples - didn't see it in brief look

## Other resources

Check out the [Prefect Cloud Terraform provider](https://registry.terraform.io/providers/PrefectHQ/prefect/latest/docs/guides/getting-started) if you're using Terraform to manage your infrastructure.
