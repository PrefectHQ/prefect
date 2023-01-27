---
description: Troubleshooting issues with Prefect Cloud.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - troubleshooting
---

# Troubleshooting Prefect Cloud

This page provides tips that may be helpful if you run into problems using Prefect Cloud.

## Prefect Cloud and proxies

Proxies intermediate network requests between a server and a client. 

To communicate with Prefect Cloud, the Prefect client library makes HTTPS requests. These requests are made using the [`httpx`](https://www.python-httpx.org/) Python library. `httpx` respects accepted proxy environment variables, so the Prefect client is able to communicate through proxies. 

To enable communication via proxies, simply set the `HTTPS_PROXY` and `SSL_CERT_FILE` environment variables as appropriate in your execution environment and things should “just work.”

See the [Using Prefect Cloud with proxies](https://discourse.prefect.io/t/using-prefect-cloud-with-proxies/1696) topic in Prefect Discourse for examples of proxy configuration.

## Prefect Cloud access via API

If the Prefect Cloud API key, environment variable settings, or account login for your execution environment are not configured correctly, you may experience errors or unexexpected flow run results when using Prefect CLI commands, running flows, or observing flow run results in Prefect Cloud.

Use the `prefect config view` CLI command to make sure your execution environment is correctly configured to access Prefect Cloud.

<div class="terminal">
```bash
$ prefect config view
PREFECT_PROFILE='cloud'
PREFECT_API_KEY='pnu_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' (from profile)
PREFECT_API_URL='https://api-beta.prefect.io/api/accounts/...' (from profile)
```
</div>

Make sure `PREFECT_API_URL` is configured to use `https://api-beta.prefect.io/api/...`.

Make sure `PREFECT_API_KEY` is configured to use a valid API key.

You can use the `prefect cloud workspace ls` CLI command to view or set the active workspace.

<div class="terminal">
```bash
$ prefect cloud workspace ls
┏━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃   Available Workspaces: ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━┩
│   g-gadflow/g-workspace │
│    * prefect/workinonit │
└─────────────────────────┘
    * active workspace
```
</div>

You can also check that the account and workspace IDs specified in the URL for `PREFECT_API_URL` match those shown in the URL bar for your Prefect Cloud workspace.

## Prefect Cloud login errors

If you're having difficulty logging in to Prefect Cloud, the following troubleshooting steps may resolve the issue, or will provide more information when sharing your case to the support channel.

- Are you logging into Prefect Cloud 2? Prefect Cloud 1 and Prefect Cloud 2 use separate accounts. Make sure to use the right Prefect Cloud 2 URL: https://app.prefect.cloud/
- Do you already have a Prefect Cloud account? If you’re having difficulty accepting an invitation, try creating an account first using the email associated with the invitation, then accept the invitation.
- Are you using a single sign-on (SSO) provider (Google or Microsoft) or just using a username and password login? 
- Did you utilize the “having trouble/forgot password” link on the login page? If so, did you receive the password reset email? Occasionally the password reset email can get filtered into your spam folder.

Other tips to help with login difficulties:

- Hard refresh your browser with Cmd+Shift+R.
- Try in a different browser. We actively test against the following browsers:
    - Chrome
    - Edge
    - Firefox
    - Safari
- Clear recent browser history/cookies

In some cases, logging in to Prefect Cloud results in a "404 Page Not Found" page or fails with the error: "Failed to load module script: Expected a JavaScript module script but the server responded with a MIME type of “text/html”. Strict MIME type checking is enforced for module scripts per HTML spec."

This error may be caused by a bad service worker. 

To resolve the problem, we recommend unregistering service workers. 

In your browser, start by opening the developer console. 

- In Chrome: **View > Developer > Developer Tools**
- In Firefox: **Tools > Browser Tools > Web Developer Tools**

Once the developer console is open:

1. Go to the **Application** tab in the developer console.
1. Select **Storage**.
1. Make sure **Unregister service workers** is selected.
1. Select **Clear site data**, then hard refresh the page with CMD+Shift+R (CTRL+Shift+R on Windows).

See the [Login to Prefect Cloud fails...](https://discourse.prefect.io/t/login-to-prefect-cloud-fails-with-an-error-failed-to-load-module-script-expected-a-javascript-module-script-but-the-server-responded-with-a-mime-type-of-text-html-strict-mime-type-checking-is-enforced-for-module-scripts-per-html-spec/1722/1) topic in Prefect Discourse for a video demonstrating these steps.

None of this worked?

Email us at help@prefect.io and provide answers to the questions above in your email to make it faster to troubleshoot and unblock you. Make sure you add the email address with which you were trying to log in, your Prefect Cloud account name, and, if applicable, the organization to which it belongs.