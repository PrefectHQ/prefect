---
sidebarDepth: 2
editLink: false
---
# Exceptions
---
 ## PrefectSignal
 <div class='class-sig' id='prefect-exceptions-prefectsignal'><p class="prefect-sig">class </p><p class="prefect-class">prefect.exceptions.PrefectSignal</p>(message=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/exceptions.py#L10">[source]</a></span></div>

Signals inherit from `BaseException` and will not be caught by normal error handling. This allows us to bypass typical error handling by raising signals.

See `prefect.engine.signals` for additional subclasses used for raising state transitions.

**Args**:     <ul class="args"><li class="args">`message`: A message with additional information about the error</li></ul>


---
<br>

 ## VersionLockMismatchSignal
 <div class='class-sig' id='prefect-exceptions-versionlockmismatchsignal'><p class="prefect-sig">class </p><p class="prefect-class">prefect.exceptions.VersionLockMismatchSignal</p>(message=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/exceptions.py#L26">[source]</a></span></div>

Raised when version locking is enabled and a task run state version sent to Cloud does not match the version expected by the server.

This is not backwards compatible with `prefect.utilities.exceptions.VersionLockError`

**Args**:     <ul class="args"><li class="args">`message`: A message with additional information about the error</li></ul>


---
<br>

 ## TaskTimeoutSignal
 <div class='class-sig' id='prefect-exceptions-tasktimeoutsignal'><p class="prefect-sig">class </p><p class="prefect-class">prefect.exceptions.TaskTimeoutSignal</p>(message=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/exceptions.py#L41">[source]</a></span></div>

Raised when a task reaches a timeout limit

This is not backwards compatible with `prefect.utilities.exceptions.TaskTimeoutError`

**Args**:     <ul class="args"><li class="args">`message`: A message with additional information about the error</li></ul>


---
<br>

 ## PrefectException
 <div class='class-sig' id='prefect-exceptions-prefectexception'><p class="prefect-sig">class </p><p class="prefect-class">prefect.exceptions.PrefectException</p>(message=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/exceptions.py#L55">[source]</a></span></div>

The base exception type for all Prefect related exceptions

**Args**:     <ul class="args"><li class="args">`message`: A message with additional information about the error</li></ul>


---
<br>

 ## ClientError
 <div class='class-sig' id='prefect-exceptions-clienterror'><p class="prefect-sig">class </p><p class="prefect-class">prefect.exceptions.ClientError</p>(message=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/exceptions.py#L69">[source]</a></span></div>

Raised when there is error in Prefect Client <-> Server communication

**Args**:     <ul class="args"><li class="args">`message`: A message with additional information about the error</li></ul>


---
<br>

 ## AuthorizationError
 <div class='class-sig' id='prefect-exceptions-authorizationerror'><p class="prefect-sig">class </p><p class="prefect-class">prefect.exceptions.AuthorizationError</p>(message=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/exceptions.py#L93">[source]</a></span></div>

Raised when there is an issue authorizing with Prefect Cloud

**Args**:     <ul class="args"><li class="args">`message`: A message with additional information about the error</li></ul>


---
<br>

 ## FlowStorageError
 <div class='class-sig' id='prefect-exceptions-flowstorageerror'><p class="prefect-sig">class </p><p class="prefect-class">prefect.exceptions.FlowStorageError</p>(message=&quot;&quot;)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/exceptions.py#L105">[source]</a></span></div>

Raised when there is an error loading a flow from storage

**Args**:     <ul class="args"><li class="args">`message`: A message with additional information about the error</li></ul>


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>