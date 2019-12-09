# Configure Your Environment

[[toc]]

## Log in to Prefect Cloud

Before you are able to use the many features of Prefect Cloud, you'll need to authenticate your local machine. This is achievable by retrieving a [Personal Access Token](/cloud/concepts/tokens.html#user) from the UI and using it to log in from the [Prefect Command Line Interface](/cloud/concepts/cli.html#cli).

Navigate to [https://cloud.prefect.io](https://cloud.prefect.io) and through the hamburger menu in the top left corner go **User** -> **Personal Access Tokens** -> **Create A Token**. This token is unique to your individual account and can be revoked whenever you desire. Copy the token and move your focus over to your command line where it will be used to log in through the Prefect CLI.

Run the auth login command to authenticate your machine with Prefect Cloud:

```
$ prefect auth login -t COPIED_TOKEN
Login successful!
```

:::warning CLI not installed
If the `prefect` command is not found then Prefect may not be installed. Go [here](/core/getting_started/installation.html) for instructions on how to install Prefect.
:::

The Personal Access Token used to log in is persisted in your root `.prefect` directory and will be overwritten if `prefect auth login` is called again.

## Create a Runner Token

Deploying your Flows using an Agent requires a `RUNNER`-scoped API token. This `RUNNER` token isn't necessary until the [Run Flow with Prefect Cloud](/cloud/onboard/first.html#run-flow-w-prefect-cloud) step on the next page, but let's go ahead and generate it now.

To create a `RUNNER`-scoped token from the CLI, run the following command, providing a name for your token and setting the role to `RUNNER`. It's worth noting that this token can always be revoked lated if needed.

```
$ prefect auth create-token -n TOKEN_NAME -r RUNNER
...token output here...
```

Executing the command above will output your token, and you should keep it in a safe place. Ultimately you can persist this token any way you desire and you will be using it when working with [Agents](/cloud/agent/overview.html). An Agent's `RUNNER` token can be provided manually (as you will see in future steps), read through the environment variable `PREFECT__CLOUD__AGENT__AUTH_TOKEN`, or from the Prefect config as `config.cloud.agent.auth_token`.

## Create a Project

With your local machine authenticated with Prefect Cloud, you can begin working with some of the Cloud features through the CLI! Before registering a Flow with Prefect Cloud, you'll need to make a [project](/cloud/concepts/projects.html). Projects are a way of organizing Flows registered with Prefect Cloud.

To create your first project run the `create` command:

```
$ prefect create project Demo
Demo created
```

Now you have a project named _Demo_ and you can see your newly created project with the `get` command:

```
$ prefect get projects
NAME    FLOW COUNT  AGE                 DESCRIPTION
Demo    0           A few seconds ago
```

As you can see, the _Demo_ project has been created and it does not currently have any registered Flows. You can change that by deploying your first Flow to Prefect Cloud!
