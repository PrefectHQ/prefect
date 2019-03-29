---
sidebarDepth: 2
editLink: false
---
# Logging
---

## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-utilities-logging-configure-logging'><p class="prefect-class">prefect.utilities.logging.configure_logging</p>(testing=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/logging.py#L44">[source]</a></span></div>
<p class="methods">Creates a "prefect" root logger with a `StreamHandler` that has level and formatting set from `prefect.config`.<br><br>**Args**:     <ul class="args"><li class="args">`testing (bool, optional)`: a boolean specifying whether this configuration         is for testing purposes only; this helps us isolate any global state during testing         by configuring a "prefect-test-logger" instead of the standard "prefect" logger</li></ul>**Returns**:     <ul class="args"><li class="args">`logging.Logger`: a configured logging object</li></ul></p>|
 | <div class='method-sig' id='prefect-utilities-logging-get-logger'><p class="prefect-class">prefect.utilities.logging.get_logger</p>(name=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/logging.py#L78">[source]</a></span></div>
<p class="methods">Returns a "prefect" logger.<br><br>**Args**:     <ul class="args"><li class="args">`name (str)`: if `None`, the root Prefect logger is returned. If provided, a child         logger of the name `"prefect.{name}"` is returned. The child logger inherits         the root logger's settings.</li></ul>**Returns**:     <ul class="args"><li class="args">`logging.Logger`: a configured logging object with the appropriate name</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.0 on March 29, 2019 at 17:39 UTC</p>
