---
sidebarDepth: 2
editLink: false
---
# Secrets
---
 ## Secret
 <div class='class-sig' id='prefect-client-secrets-secret'><p class="prefect-sig">class </p><p class="prefect-class">prefect.client.secrets.Secret</p>(name)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/client/secrets.py#L10">[source]</a></span></div>

A Secret is a serializable object used to represent a secret key & value.

**Args**:     <ul class="args"><li class="args">`name (str)`: The name of the secret</li></ul>The value of the `Secret` is not set upon initialization and instead is set either in `prefect.context` or on the server, with behavior dependent on the value of the `use_local_secrets` flag in your Prefect configuration file.

If using local secrets, `Secret.get()` will attempt to call `json.loads` on the value pulled from context.  For this reason it is recommended to store local secrets as JSON documents to avoid ambiguous behavior (e.g., `"42"` being parsed as `42`).

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-client-secrets-secret-get'><p class="prefect-class">prefect.client.secrets.Secret.get</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/client/secrets.py#L29">[source]</a></span></div>
<p class="methods">Retrieve the secret value.  If not found, returns `None`.<br><br>If using local secrets, `Secret.get()` will attempt to call `json.loads` on the value pulled from context.  For this reason it is recommended to store local secrets as JSON documents to avoid ambiguous behavior.<br><br>**Returns**:     <ul class="args"><li class="args">`Any`: the value of the secret; if not found, returns `None`</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if `.get()` is called within a Flow building context     </li><li class="args">`ValueError`: if `use_local_secrets=False` and the Client fails to retrieve your secret</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.3 on May 7, 2019 at 20:46 UTC</p>