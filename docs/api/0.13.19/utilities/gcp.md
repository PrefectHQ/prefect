---
sidebarDepth: 2
editLink: false
---
# Google Utilities
---
Utility functions for interacting with Google Cloud.

## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-utilities-gcp-get-storage-client'><p class="prefect-class">prefect.utilities.gcp.get_storage_client</p>(credentials=None, project=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/gcp.py#L37">[source]</a></span></div>
<p class="methods">Utility function for instantiating a Google Storage Client from a given set of credentials.<br><br>**Args**:     <ul class="args"><li class="args">`credentials (dict, optional)`: a dictionary of Google credentials used to initialize         the Client; if not provided, will attempt to load the Client using ambient         environment settings     </li><li class="args">`project (str, optional)`: the Google project to point the Client to; if not provided,         Client defaults will be used</li></ul> **Returns**:     <ul class="args"><li class="args">`Client`: an initialized and authenticated Google Client</li></ul></p>|
 | <div class='method-sig' id='prefect-utilities-gcp-get-bigquery-client'><p class="prefect-class">prefect.utilities.gcp.get_bigquery_client</p>(credentials=None, project=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/gcp.py#L56">[source]</a></span></div>
<p class="methods">Utility function for instantiating a Google BigQuery Client from a given set of credentials.<br><br>**Args**:     <ul class="args"><li class="args">`credentials (dict, optional)`: a dictionary of Google credentials used to initialize         the Client; if not provided, will attempt to load the Client using ambient         environment settings     </li><li class="args">`project (str, optional)`: the Google project to point the Client to; if not provided,         Client defaults will be used</li></ul> **Returns**:     <ul class="args"><li class="args">`Client`: an initialized and authenticated Google Client</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>