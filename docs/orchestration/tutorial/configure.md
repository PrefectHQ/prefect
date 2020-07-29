# Configure Your Environment  

## Select an Orchestration Backend

Prefect supports two different orchestration backends:

- `cloud` - our [hosted service](https://cloud.prefect.io)
- `server` - the open source backend, deployed on your infrastructure

To use Prefect with either backend, you must first select that backend via
the CLI:

:::: tabs
::: tab Cloud
```bash
$ prefect backend cloud
```
:::

::: tab Server
```bash
$ prefect backend server
```
:::
::::

Note that you can change backends at any time by rerunning the `prefect backend
...` command.

## Authenticating with Prefect Cloud <Badge text="Cloud"/>

If you're using Prefect Cloud, you'll also need to authenticate with the
backend before you can proceed further.

### Create a Personal Access Token

To authenticate, you'll need to create a [Personal Access
Token](/orchestration/concepts/tokens.html#user) and configure it with the
[Prefect Command Line Interface](/orchestration/concepts/cli.html#cli).

- Login to [https://cloud.prefect.io](https://cloud.prefect.io) 
- In the hamburger menu in the top left corner go to **User** -> **Personal
  Access Tokens** -> **Create A Token**.
- Copy the created token
- Configure the CLI to use the access token by running

```bash
prefect auth login -t <COPIED_TOKEN>
```

### Create a Runner Token

Running deployed Flows with an [Agent](/orchestration/agents/overview.html)
also requires a `RUNNER`-scoped API token for the Agent. You can create one
using the CLI:

```bash
prefect auth create-token -n my-runner-token -s RUNNER
```

You'll need this token later in the tutorial. You can save it in your local
configuration either as an environment variable or by storing it in
`~/.prefect/config.toml`:

:::: tabs
::: tab "Environment Variable"

```bash
export PREFECT__CLOUD__AGENT__AUTH_TOKEN=<COPIED_RUNNER_TOKEN>
```
:::

::: tab config.toml

```toml
# ~/.prefect/config.toml
[cloud.agent]
auth_token = <COPIED_RUNNER_TOKEN>
```
:::
::::
