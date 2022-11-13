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

Prefect Cloud's [Organization and Enterprise plans](https://www.prefect.io/pricing) offer single sign-on (SSO) integration with your team’s identity provider. SSO integration can bet set up with any identity provider that supports: 

- OIDC
- SAML 2.0

When using SSO, Prefect Cloud won't store passwords for any accounts managed by your identity provider. Members of your Prefect Cloud organization will instead log in to the organization and authenticate using your identity provider.

Once your SSO integration has been set up, non-admins will be required to authenticate through the SSO provider when accessing organization resources.

See the [Prefect Cloud plans](https://www.prefect.io/pricing) to learn more about options for supporting more users and workspaces, service accounts, and SSO.

## Configuring SSO

Within your organization, select the **SSO** page to enable SSO for users. 

If you haven't enabled SSO for a domain yet, enter the email domains for which you want to configure SSO in Prefect Cloud. Select **Save** to accept the domains.

![Adding an email domain for single sign-on in the Prefect Cloud UI.](/img/ui/cloud-sso.png)

Under **Enabled Domains**, select the domains from the **Domains** list, then select **Generate Link**. This step creates a link you can use to configure SSO with your identity provider.

![Generating a configuration link for single sign-on in the Prefect Cloud UI.](/img/ui/cloud-sso-provider.png)

Using the provided link navigate to the Identity Provider Configuration dashboard and select your identity provider to continue configuration. If your provider isn't listed, you can continue with the `SAML` or `Open ID Connect` choices instead.

![Opening the Identity Provider Configuration dashboard.](/img/ui/cloud-sso-dashboard.png)

Once you complete SSO configuration your users will be required to authenticate via your identity provider when accessing organization resources, giving you full control over application access.

## Directory sync

**Directory sync** automatically provisions and de-provisions users for your organization. 

Provisioned users are given basic “Member” roles and will have access to any resources that role entails. 

When a user is unassigned from the Prefect Cloud application in your identity provider, they will automatically lose access to Prefect Cloud resources, allowing your IT team to control access to Prefect Cloud without ever signing into the app. 