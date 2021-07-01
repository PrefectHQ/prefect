---
sidebarDepth: 2
editLink: false
---
# Secrets
---
::: warning Secret Tasks are preferred
While this Secrets API is fully supported, using a [Prefect Secret Task](../tasks/secrets) is
typically preferred for better reuse of Secret values and visibility into the secrets used
within Tasks / Flows.
:::

A Secret is a serializable object used to represent a secret key & value.

The value of the `Secret` is not set upon initialization and instead is set
either in `prefect.context` or on the server, with behavior dependent on the value
of the `use_local_secrets` flag in your Prefect configuration file.

To set a Secret in Prefect Cloud, you can use `prefect.Client.set_secret`, or set it directly
via GraphQL:

```graphql
mutation {
  set_secret(input: { name: "KEY", value: "VALUE" }) {
    success
  }
}
```

To set a _local_ Secret, either place the value in your user configuration file (located at
`~/.prefect/config.toml`):

```
[context.secrets]
MY_KEY = "MY_VALUE"
```

or directly in context:

```python
import prefect

prefect.context.setdefault("secrets", {}) # to make sure context has a secrets attribute
prefect.context.secrets["MY_KEY"] = "MY_VALUE"
```

or specify the secret via environment variable:

```bash
export PREFECT__CONTEXT__SECRETS__MY_KEY="MY_VALUE"
```

::: tip Default secrets
Special default secret names can be used to authenticate to third-party systems in a
installation-wide way. Read more about this in our [Secrets concept
documentation](/core/concepts/secrets.md#default-secrets).
:::

::: tip
When settings secrets via `.toml` config files, you can use the [TOML
Keys](https://github.com/toml-lang/toml#keys) docs for data structure specifications. Running
`prefect` commands with invalid `.toml` config files will lead to tracebacks that contain
references to: `..../toml/decoder.py`.
:::
 ## Secret
 <div class='class-sig' id='prefect-client-secrets-secret'><p class="prefect-sig">class </p><p class="prefect-class">prefect.client.secrets.Secret</p>(name)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/client/secrets.py#L71">[source]</a></span></div>

A Secret is a serializable object used to represent a secret key & value.

**Args**:     <ul class="args"><li class="args">`name (str)`: The name of the secret</li></ul> The value of the `Secret` is not set upon initialization and instead is set either in `prefect.context` or on the server, with behavior dependent on the value of the `use_local_secrets` flag in your Prefect configuration file.

If using local secrets, `Secret.get()` will attempt to call `json.loads` on the value pulled from context.  For this reason it is recommended to store local secrets as JSON documents to avoid ambiguous behavior (e.g., `"42"` being parsed as `42`).

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-client-secrets-secret-exists'><p class="prefect-class">prefect.client.secrets.Secret.exists</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/client/secrets.py#L96">[source]</a></span></div>
<p class="methods">Determine if the secret exists.<br><br>**Returns**:     <ul class="args"><li class="args">`bool`: a boolean specifying whether the Secret is accessible or not</li></ul></p>|
 | <div class='method-sig' id='prefect-client-secrets-secret-get'><p class="prefect-class">prefect.client.secrets.Secret.get</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/client/secrets.py#L112">[source]</a></span></div>
<p class="methods">Retrieve the secret value.  If not found, returns `None`.<br><br>If using local secrets, `Secret.get()` will attempt to call `json.loads` on the value pulled from context.  For this reason it is recommended to store local secrets as JSON documents to avoid ambiguous behavior.<br><br>**Returns**:     <ul class="args"><li class="args">`Any`: the value of the secret; if not found, raises an error</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if `.get()` is called within a Flow building context, or if         `use_local_secrets=True` and your Secret doesn't exist     </li><li class="args">`KeyError`: if `use_local_secrets=False` and the Client fails to retrieve your secret     </li><li class="args">`ClientError`: if the client experiences an unexpected error communicating with the         backend</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>