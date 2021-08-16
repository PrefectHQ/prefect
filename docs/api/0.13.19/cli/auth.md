---
sidebarDepth: 2
editLink: false
---
# auth
---
<h3>login</h3>
  Log in to Prefect Cloud with an api token to use for Cloud communication.

  <pre><code>Options:<br>      --token, -t         TEXT    A Prefect Cloud api token  [required]<br><br></code></pre><h3>logout</h3>
  Log out of Prefect Cloud

<pre><code>Options:<br>  --help  Show this message and exit.</code></pre><h3>list-tenants</h3>
  List available tenants

<pre><code>Options:<br>  --help  Show this message and exit.</code></pre><h3>switch-tenants</h3>
  Switch active tenant

  <pre><code>Options:<br>      --id, -i    TEXT    A Prefect Cloud tenant id<br>      --slug, -s  TEXT    A Prefect Cloud tenant slug<br><br></code></pre><h3>create-token</h3>
  Create a Prefect Cloud API token.

  For more info on API tokens visit
  https://docs.prefect.io/orchestration/concepts/api.html

  <pre><code>Options:<br>      --name, -n      TEXT    A name to give the generated token<br>      --scope, -s     TEXT    A scope for the token<br><br></code></pre><h3>list-tokens</h3>
  List your available Prefect Cloud API tokens.

<pre><code>Options:<br>  --help  Show this message and exit.</code></pre><h3>revoke-token</h3>
  Revote a Prefect Cloud API token

  <pre><code>Options:<br>      --id, -i    TEXT    The id of a token to revoke<br><br></code></pre>
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>