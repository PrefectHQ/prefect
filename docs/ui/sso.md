---
description: Configure single sign-on (SSO) for your Prefect Cloud users.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - enterprise
    - teams
    - workspaces
    - organizations
    - single sign-on
    - SSO
    - authentication
---

# Single Sign-on (SSO) <span class="badge cloud"></span> <span class="badge orgs"></span> <span class="badge enterprise"></span>

Prefect Cloud [Enterprise plans](https://www.prefect.io/pricing) offer single sign-on (SSO) integration with your team’s identity provider. SSO integration can bet set up with any identity provider that supports: 

- OIDC
- SAML 2.0

When using SSO, Prefect Cloud won't store passwords for any accounts managed by your identity provider. Members of your Prefect Cloud organization will instead log in to the organization and authenticate using your identity provider.

When SSO integration has been set up, all other authentication methods are disabled, so that you can ensure that authentication is managed exclusively by your identity provider.

See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting more users and workspaces, service accounts, and SSO.

## Configuring SSO

Within your organization, select the **SSO** page to enable SSO for users. 

If you haven't enabled SSO for a domain yet, enter the email domains for which you want to configure SSO in Prefect Cloud. Select **Save** to accept the domains.

![Adding an email domain for single sign-on in the Prefect Cloud UI.](/img/ui/cloud-sso.png)

Under **Enabled Domains**, select the domains from the **Domains** list, then select **Generate Link**. This step creates a WorkOS link you can use to configure SSO with your identity provider.

![Generating a WorkOS configuration link for single sign-on in the Prefect Cloud UI.](/img/ui/cloud-sso-provider.png)

Using the provided link, navigate to the WorkOS Identity Provider Configuration dashboard. Select your identity provider to continue configuration. WorkOS provides instructions specific you your identity provider.

![Opening the WorkOS Identity Provider Configuration dashboard in WorkOS.](/img/ui/cloud-sso-workos.png)

When you complete SSO configuration in WorkOS, your configured users will be able to log into Prefect Cloud using SSO authentication via your identity provider, giving you full control over application access.

![Logging in to Prefect Cloud using Google ID SSO.](/img/ui/cloud-sso-login.png)

See the [WorkOS Integrations](https://workos.com/docs/integrations) documentation for further details about individual identity provider configurations.