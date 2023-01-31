---
description: Create an API key to access Prefect Cloud from a local execution environment.
icon: material/cloud-outline
tags:
    - Prefect Cloud
    - API keys
    - configuration
---

# Manage Prefect Cloud API Keys <span class="badge cloud"></span>

API keys enable you to authenticate an a local environment to work with Prefect Cloud. See [Configure execution environment](#configure-execution-environment) for details on how API keys are configured in your execution environment.

See [Configure Local Environments](/ui/cloud-local-environment/) for details on setting up access to Prefect Cloud from a local development environment or remote execution environment.

## Create an API key

To create an API key, select the account icon at the bottom-left corner of the UI and select your account name. This displays your account profile.

Select the **API Keys** tab. This displays a list of previously generated keys and lets you create new API keys or delete keys.

![Viewing and editing API keys in the Cloud UI.](../img/ui/cloud-api-keys.png)

Select the **+** button to create a new API key. You're prompted to provide a name for the key and, optionally, an expiration date. Select **Create API Key** to generate the key.

![Creating an API key in the Cloud UI.](../img/ui/cloud-new-api-key.png)

Note that API keys cannot be revealed again in the UI after you generate them, so copy the key to a secure location.

## Service account API keys <span class="badge orgs"></span>

Service accounts are a feature of Prefect Cloud [organizations](/ui/organizations/) that enable you to create a Prefect Cloud API key that is not associated with a user account. 

Service accounts are typically used to configure API access for running agents or executing flow runs on remote infrastructure. Events and logs for flow runs in those environments are then associated with the service account rather than a user, and API access may be managed or revoked by configuring or removing the service account without disrupting user access.

See the [service accounts](/ui/service-accounts/) documentation for more information about creating and managing service accounts in a Prefect Cloud organization.
