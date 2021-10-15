---
sidebarDepth: 2
editLink: false
---
# Logging
---
Utility functions for interacting with and configuring logging.  The main entrypoint for
retrieving loggers for customization is the `get_logger` utility.

Note that Prefect Tasks come equipped with their own loggers.  These can be accessed via:
    - `self.logger` if implementing a Task class
    - `prefect.context.get("logger")` if using the `task` decorator

When running locally, log levels and message formatting are set via your Prefect configuration file.

## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-utilities-logging-configure-logging'><p class="prefect-class">prefect.utilities.logging.configure_logging</p>(testing=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/logging.py#L222">[source]</a></span></div>
<p class="methods">Creates a "prefect" root logger with a `StreamHandler` that has level and formatting set from `prefect.config`.<br><br>**Args**:     <ul class="args"><li class="args">`testing (bool, optional)`: a boolean specifying whether this configuration         is for testing purposes only; this helps us isolate any global state during testing         by configuring a "prefect-test-logger" instead of the standard "prefect" logger</li></ul>**Returns**:     <ul class="args"><li class="args">`logging.Logger`: a configured logging object</li></ul></p>|
 | <div class='method-sig' id='prefect-utilities-logging-get-logger'><p class="prefect-class">prefect.utilities.logging.get_logger</p>(name=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/logging.py#L265">[source]</a></span></div>
<p class="methods">Returns a "prefect" logger.<br><br>**Args**:     <ul class="args"><li class="args">`name (str)`: if `None`, the root Prefect logger is returned. If provided, a child         logger of the name `"prefect.{name}"` is returned. The child logger inherits         the root logger's settings.</li></ul>**Returns**:     <ul class="args"><li class="args">`logging.Logger`: a configured logging object with the appropriate name</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>