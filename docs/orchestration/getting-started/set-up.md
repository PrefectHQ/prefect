# Orchestration Layer

## Server or Cloud?

If you want an orchestration layer, you have two options:  Prefect Server and Prefect Cloud. You can see an overview and comparison on the [welcome](/orchestration/README.md) page. 

As we encourage first time users to try the simpler Cloud layer first, this guide focusses on setting up Prefect Cloud. More information on Server is available in the [Prefect Server documentation](/orchestration/server/overview.html).

## Cloud 

### Create (or log into) your Prefect Cloud account
To use Prefect Cloud you'll need to go to login to (or set up an account for) Prefect Cloud at [https://cloud.prefect.io](https://cloud.prefect.io).

### Set backend 

Once you have an account set up, make sure your backend is set to use Prefect Cloud by running 

  ```bash
$ prefect backend cloud
```

Note that you can change backends at any time by rerunning the `prefect backend ...` command.

### Authenticate with Prefect Cloud 

Next you'll need to authenticate with the backend before you can proceed further.

### Create an API key and login

To authenticate, you'll need to create an [API Key](/orchestration/concepts/api_keys.md) and save it. 

- Navigate to the [API keys page](https://cloud.prefect.io/user/keys). In the User menu in the top right corner go to **Account Settings** -> **API Keys** -> **Create An API Key**.
- Copy the created key
- Login with the Prefect CLI `prefect auth login --key <YOUR-KEY>`

To learn more about API keys including how to save them, set them through environment varaiables and how to use API keys connected to a service account, check out the [API key documentation](/orchestration/concepts/api_keys.md). 



