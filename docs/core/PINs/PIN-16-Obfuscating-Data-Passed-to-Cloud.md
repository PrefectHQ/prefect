---
title: 'PIN-16: Obfuscating Data Passed to Cloud'
sidebarDepth: 0
---

# PIN-16: Obfuscating Data Passed to Cloud

Date: March 6, 2020

Authors: Laura Lorenz, Nathan Atkins, Alex Goodman

## Status
Draft

## Context

Businesses that deal with customer, medical or otherwise sensitive data are concerned about sending that data outside of their controlled environment. This includes exception messages and stack traces, partial or entire log messages that contain sensitive information, and task-produced data such as Result values being sent to Prefect Cloud. 

Despite these concerns, there are some users who wish to still use features from Prefect Cloud if they can feel more confident that the data Cloud stores to provide those features is non-sensitive or obfuscated from the cloud database if so.

Though the hybrid model provides protection from most of the canonical surface area of this risk by isolating user code from Cloud persistence systems, some specific types of leaks are still possible and even enforced by the library today. Currently, the Prefect logger can be bypassed if users always log to their own logger instance, but this is not immediately obvious and does not prevent exceptions from being sent through the Prefect logger to Cloud since the exception is ultimately raised during the Prefect TaskRunner. In addition, any accidental usage of JSONResultHandler (including today’s hardcoded case for Parameter type tasks) emits the return value of a task to the cloud database.

This PIN seeks to argue that more configuration options, including a set-it-and-forget-it global configuration, that protects the data boundary to Cloud is a valid “safe default” scenario that should be provided alongside the current safe default scenario that prioritizes convenience.

In addition, we also considered the need for dynamic obfuscation of logs by Prefect administrators that want peace of mind that data they can infer to be sensitive, such as logs containing certain terms or strings that look like keys, can be interrupted during any accidental transmission to Cloud.

Here are the obfuscation / redaction scenarios that we considered:

1. **Full Redaction**: total obfuscation of information in a LogRecord besides log level. The obfuscated LogRecord is still delivered to the logging destination.
```
   logger.info("this is sensitive", private=True)
   |
   |
   Logged: “INFO: ***************”
```
2. **Partial Redaction**: search and replace partial strings from individual LogRecords. 
```
   logger.info("this is sensitive")
   |
   |
   logged: "INFO: this is ******"
```
3. **Per-Handler Full Redaction**: total obfuscation of information in a LogRecord when sent to a specific log handler or handlers
```
    x logger.info("this is sensitive", private=True)
    |
+---+
|   |
|   |
|   logged: "INFO: this is sensitive"
|
logged: “INFO: ***************”
```

4. **Per-Handler Partial Redaction**: search and replace partial strings from individual LogRecords when sent to a specific log handler or handlers

```
    x logger.info("this is sensitive")
    |
+---+
|   |
|   |
|   logged: "INFO: this is sensitive"
|
logged: "INFO: this is ****"
```

While developing this PIN, a fifth scenario was postponed to a later PIN. All considered API designs for (5) were tightly coupled to a more complex abstraction that allowed information from handlers to be passed to other handlers. Due to its complexity, we will propose options for (5) in a secondary PIN for independent debate.

5. **Value Relocation**: fully redact content from the LogRecord and annotate where the user can find where sensitive information has been logged to. 

```
    x logger.info("this is sensitive", private=True)
    |
+---+
|   |
|   |
|   logged: "INFO: please see 'bucket-name/path/file' for more info"
|
logged @ 'bucket-name/path/file': "INFO: this is sensitive"
```

In addition, two scenarios were specifically dropped from consideration. (6) and (7) protect information by filtering LogRecords entirely from a handler’s emit method. Since this proposal is inspired by users who _do_ want to use Cloud logging, just on their own terms, these scenarios are considered irrelevant.

6. **Simple Filtering**: all or nothing inclusion or removal of the LogRecord. 

```
   logger.info("this is sensitive", private=True)
   |
   |
   X (not logged)
```

7. **Per-handler Filtering**: all or nothing inclusion or removal of LogRecords for specific Handlers. 
```
    x logger.info("this is sensitive")
    |
+---+
|   |
|   |
|   logged: "this is sensitive"
|
X (not logged)
```

## Proposal

::: tip
During the draft phase, these proposals are purposefully listed in outline form to enable precise Github comments.
:::

### Design goals
- Obfuscation behavior driven by prefect configuration: A global setting can obfuscate all task logs and exception traces from Cloud.
- Obfuscation behavior customizable at many levels: Redaction patterns, obfuscation functions, and setting privacy at log levels or per handler allow the user to customize obfuscation behavior.
- Warn users as early as possible if obfuscation mechanisms have been elected but there could be a known potential leak of information.
- Utilize as much of the Python standard logging subsystem as possible
- Don’t break the existing Cloud UI: The error log tile functionality in Cloud UI is not broken; it can still report number of errors and link to obfuscated error logs in Cloud UI like it does today

### Primary proposals:
#### Obfuscate Logs sent to Prefect Cloud
- User can elect all logs to be obfuscated in entirety, for example by setting `prefect.config.logger.set_all_private`. This would still send a LogRecord to Cloud indicating the log level, however, all content from a record’s `msg` attribute would be removed. This is useful for the Cloud UI to determine if there is a log entry indicating a failure within a Flow Run.
- User can elect individual logs to be obfuscated in this way, for example: `logger.info(msg, private=True)`
- User can elect partial logs to be obfuscated by specifying a pattern, for example: `logger.info(msg, redact_pattern=’A-*’)`
- Support providing obfuscation patterns at multiple levels:
    - Global prefect configuration: allow users to provide regex patterns that the main prefect logger (including Cloud logger) would honor. For example: `prefect.config.logging.redact_log_patterns = [r‘A-*’, <other regexes>]`
    - Flow level configuration: add a `redact_log_patterns` kwarg to the `Flow` class constructor, which is provided to the flow logger. Default pattern values derived from the `prefect.config.logging.redact_log_patterns`.
    - Task level configuration: add a `redact_log_patterns` kwarg to the `Task` class constructor, which is provided to the task logger. Default pattern values derived from the `prefect.config.logging.redact_log_patterns`.
- Support user provided obfuscation function to redact or remove log messages. The redact function would take a LogRecord and return a LogRecord (which may be modified). Redaction functions could be indicated in one of two ways:
    - Inline: `logger.info(msg, redact_fn=some_fn)`
    - On the logger, applied to all LogRecords observed by the logger: `logger.addRedactFn(some_fn)`. Note: multiple redact functions can be provided


#### Obfuscate Exceptions sent to Prefect Cloud
- Remove exceptions and stack traces from all LogRecords that have been flagged to be obfuscated that are sent to the Cloud Handler

#### Emphasize alternative logging handlers, including 3rd party, for unobfuscated log messages
Once information is obfuscated such that the Prefect Cloud logger does not send sensitive information to Cloud, users may want to persist the original sensitive information in other data stores (such as S3, GCS, StackDriver, DataDog, etc). 
- Users already can supply any other handlers to the root Prefect logger; any configuration by Prefect Core of user supplied handlers should _not_ apply obfuscation by default
- Documentation will be updated to reflect more diverse logger configurations, including users using non-Prefect loggers and controlling logging entirely on their own


#### Check Flows for known leaky configuration
- If users have set `prefect.config.logger.set_all_private`, Flow registration should check for the presence of JSONResultHandlers in the flow (and any other future tagged leaky options) and warn the user


## Consequences

- Cloud users that _do not_ need this level of data protection should see no change
- Cloud users that __do__ need this level of data protection do not need to change any code, but can update their prefect config to turn on the configuration globally
- Cloud users that __do__ need this level of data protection will feel more friction when deploying to Cloud if their flow is not validated as leakproof 
- Cloud users that __do__ need this level of data protection will experience a weakened user experience on Cloud (UI log view is less useful, UI parameter submission is difficult)
- Future Core or Cloud features that seek to send data to Cloud for convenience must support obfuscation and should disable themselves if a user configures this PINs global privacy configuration

## Actions

- Create a new Formatter class that is capable of redacting log messages by regex, function, or wholesale
- Expose configuration of regex or python functions to the user at the global, flow, or task level with implementations of `prefect.config.logging.redact_log_patterns` and `logger.addRedactFn`
- Expose a Prefect config `prefect.config.logging.set_all_private` that automatically attaches the Formatter class to the Prefect logger’s CloudHandler
- Implement a check during Flow registration that checks for `set_all_private` and emits warnings for any leaky structures (such as JSONResultHandler) in the flow
- Update logging documentation to emphasize other production grade third party handlers outside CloudHandler; showcase how to attach the obfuscating Formatter class to those handlers if desired
- Update the derivative PIN regarding postponed scenario 5 with anything learned from implementing this PIN
