This section of our quick-start guide is aimed at [Prefect
  Cloud](https://cloud.prefect.io) users.  If you want to set up Prefect Server, skip to [Set Up Prefect Server](). 

## Create (or log into) your Prefect Cloud account
To use Prefect Cloud you'll need to go to our Prefect Cloud web app and set up (or join) an account.  

## Make sure your backend is set to Cloud

Once you have an account set up, make sure your backend is set to use Prefect Cloud by running 

  ```bash
$ prefect backend cloud
```

Note that you can change backends at any time by rerunning the `prefect backend ...` command.

## Authenticate with Prefect Cloud <Badge text="Cloud"/>

Next you'll need to authenticate with the backend before you can proceed further.

### Create an API key and login

To authenticate, you'll need to create an [API Key](/orchestration/concepts/api_keys.md) and save it. 

- Login to [https://cloud.prefect.io](https://cloud.prefect.io)
- Navigate to the [API Keys page](https://cloud.prefect.io/user/keys). In the User menu in the top right corner go to **Account Settings** -> **API Keys** -> **Create An API Key**.
- Copy the created key
- Login with the Prefect CLI `prefect auth login --key <YOUR-KEY>`

**IS THIS STILL POSSIBLE?*** - Do we need to update the UI Tutorial again?

- Save the key locally either in your `~/.prefect/config.toml` config file, or as an environment variable:

```bash
# ~/.prefect/config.toml
[cloud]
auth_token = <API_KEY>
```

```bash
export PREFECT__CLOUD__AUTH_TOKEN=<API_KEY>
```

# Create a Service Account Key

Running deployed Flows with an [Agent](https://docs.prefect.io/orchestration/agents/overview.html) also requires an API key for the Agent. You can create one in the [Service Accounts](/team/service-accounts) page of the UI.

You can save it locally either in your `~/.prefect/config.toml` config file, or as an environment variable:

```bash
# ~/.prefect/config.toml
[cloud.agent]
auth_token = <SERVICE_ACCOUNT_API_KEY>
```

```bash
export PREFECT__CLOUD__AGENT__AUTH_TOKEN=<SERVICE_ACCOUNT_API_KEY>
```


