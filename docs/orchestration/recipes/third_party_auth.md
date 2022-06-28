# Third Party Authentication

This recipe describes various ways to securely authenticate your flow runs with third party services.

[[toc]]

### The Basics 

Most use cases that rely on Prefect involve connecting to third party services in a secure manner.  Prefect provides many ways to authenticate with third party services that range from the simple to the complex.  Which you choose depends on the nature of your goal and how much customization you need.  

!!! warning Best Practices
    Be mindful of where you choose to store your secure credentials.  In general it is best practice to store such information in dedicated secret stores; when this is not an option, you should make sure that you are storing your sensitive information in a location that you fully understand and control.  

    Moreover, when generating new credentials you should aim to provide only the permissions you need to achieve the task at hand and _no more_.  This helps reduce the chances of a misused credential.


Ultimately there are two distinct authentication patterns to choose from:

- configuring your runtime environment independently of Prefect
- using native Prefect hooks to authenticate

We will cover each of these along with the varying degrees of configurability in the sections below, ranging from the simplest to the most complex.

### Configuring your runtime environment externally to Prefect

Because your flows always run on infrastructure you control, you can always configure your runtime environment to authenticate with whatever services your tasks and flows need access to.  Most Python clients have ways of configuring authentication external to your code, for example through the use of environment variables or well-placed configuration files. 

The benefit of this technique is that you have full control; the drawbacks are that Prefect can't be as helpful in informing you when your credentials are not present and of course you need to understand your system setup rather well to do this securely and correctly.

Some common patterns for achieving this:
- setting the appropriate library-specific environment variables / config files on the machines responsible for executing your flows
- using things like Kubernetes Secrets to do so in a secure way

!!! tip This is always the final fallback
    Note that if no Prefect Secrets are configured as described below, all Prefect tasks will fall back on the standard default authentication logic for whatever library you are using. 


### Using Secrets to configure your flow

For a more off-the-shelf experience, you can also use [Prefect Secrets](../concepts/secrets.html) to help you set up your authentication.  As with most things in Prefect, you have many options ranging from sensible defaults to highly customizable auth patterns.

#### Declaring Secrets on Storage <Badge text="Cloud"/>

All Prefect interfaces for third party services have default secrets they attempt to pull for authenticating ([the full list of names and expected types can be found below](#list-of-default-secret-names)).  There are a number of ways you can auto-populate these secrets.  Perhaps the easiest way is to [set your secret values in Prefect Cloud](../concepts/secrets.html#setting-a-secret) and declare them on your flow's storage option.  As an example:

```python
from prefect import Flow
from prefect.storage import GCS


storage = GCS(bucket="my-bucket", 
              secrets=["GCP_CREDENTIALS"])

f = Flow("empty-flow", storage=storage)
```

Once this flow is registered and run through an Agent, the first thing it will do is pull the value of the `"GCP_CREDENTIALS"` secret from Prefect Cloud and place it into `prefect.context.secrets` under the appropriate key.  These credentials are now available for any task or Prefect API call to Google, _including for pulling the Flow itself from GCS_.

Any number of secrets can be declared on your `Storage` option.

!!! warning This only applies to Prefect built-ins
    This off-the-shelf experience generally only applies to interfaces that are natively included as a part of the Prefect package. Note that if you write a completely custom task for interacting with a third party service, you will also need to consider how this task will authenticate.  Whether you choose to use Prefect Secrets or another option is up to you.


#### Passing Secrets from an Agent

Recall that users can autopopulate Prefect context with values through the use of environment variables.  In particular, all secrets can be set by providing an appropriate value to `PREFECT__CONTEXT__SECRETS__XXXX` in your runtime environment.  One way of achieving this through Prefect is by configuring your agent(s) to pass the appropriate value to each flow run it submits.  Using a Docker Agent as an example:

```
prefect agent docker start \\
    -e PREFECT__CONTEXT__SECRETS__AWS_CREDENTIALS=${AWS_CREDENTIALS}
```

This will then ensure that the `AWS_CREDENTIALS` secret is globally present in `prefect.context` for all flow runs submitted through this agent; in this case, it's value will be whatever value the `AWS_CREDENTIALS` environment variable has in the agent's own environment (which itself might have been set through some secure mechanism such as a Kubernetes Secret).

### Providing Secrets on a per-task basis

In some instances you may need to override the global options presented above on a per-task basis, or you may choose to explicitly provide credentials to every task that needs them.  Either way, all Prefect tasks from the Task library which require credentials to authenticate offer optional runtime arguments for providing this information.


### Default Secret names

A few common secrets, such as authentication keys for GCP or AWS, have a standard naming convention as Prefect secrets for use by the Prefect pipeline or tasks in Prefect's task library. If you follow this naming convention when storing your secrets, all supported Prefect interactions with those services will be automatically configured.

See the list of default secret names on the [Secrets concept documentation](../../core/concepts/secrets.md#default-secrets).
