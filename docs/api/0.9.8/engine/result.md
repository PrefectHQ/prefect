---
sidebarDepth: 2
editLink: false
---
# Results
---
Results represent Prefect Task inputs and outputs.  In particular, anytime a Task runs, its output
is encapsulated in a `Result` object.  This object retains information about what the data is, and how to "handle" it
if it needs to be saved / retrieved at a later time (for example, if this Task requests for its outputs to be cached or checkpointed).

An instantiated Result object has the following attributes:

- a `value`: the value of a Result represents a single piece of data
- a `safe_value`: this attribute maintains a reference to a `SafeResult` object
    which contains a "safe" representation of the `value`; for example, the `value` of a `SafeResult`
    might be a URI or filename pointing to where the raw data lives
- a `result_handler` that holds onto the `ResultHandler` used to read /
    write the value to / from its handled representation

To distinguish between a Task that runs but does not return output from a Task that has yet to run, Prefect
also provides a `NoResult` object representing the _absence_ of computation / data.  This is in contrast to a `Result`
whose value is `None`.
 ## Result
 <div class='class-sig' id='prefect-engine-result-result'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result.Result</p>(value, result_handler=None, validators=None, run_validators=True, cache_for=None, cache_validator=None, filename_template=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L66">[source]</a></span></div>

A representation of the result of a Prefect task; this class contains information about the value of a task's result, a result handler specifying how to serialize or store this value securely, and a `safe_value` attribute which holds information about the current "safe" representation of this result.

**Args**:     <ul class="args"><li class="args">`value (Any)`: the value of the result     </li><li class="args">`result_handler (ResultHandler, optional)`: the result handler to use         when storing / serializing this result's value; required if you intend on persisting this result in some way     </li><li class="args">`validators (Iterable[Callable], optional)`: Iterable of validation functions to apply to         the result to ensure it is `valid`.     </li><li class="args">`run_validators (bool)`: Whether the result value should be validated.     </li><li class="args">`cache_for (timedelta, optional)`: The amount of time to maintain a cache         of this result.  Useful for situations where the containing Flow         will be rerun multiple times, but this task doesn't need to be.     </li><li class="args">`cache_validator (Callable, optional)`: Validator that will determine         whether the cache for this result is still valid (only required if `cache_for`         is provided; defaults to `prefect.engine.cache_validators.duration_only`)     </li><li class="args">`filename_template (str, optional)`: Template file name to be used for saving the         result to the destination.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-result-exists'><p class="prefect-class">prefect.engine.result.Result.exists</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L126">[source]</a></span></div>
<p class="methods">Checks whether the target result exists.<br><br>Does not validate whether the result is `valid`, only that it is present.<br><br>**Returns**:     <ul class="args"><li class="args">`bool`: whether or not the target result exists.</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-result-read'><p class="prefect-class">prefect.engine.result.Result.read</p>(loc=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L137">[source]</a></span></div>
<p class="methods">Reads from the target result.<br><br>**Args**:     <ul class="args"><li class="args">`loc (str)`: Location of the result in the specific result target.</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: The value saved to the result.</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-result-store-safe-value'><p class="prefect-class">prefect.engine.result.Result.store_safe_value</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L110">[source]</a></span></div>
<p class="methods">Populate the `safe_value` attribute with a `SafeResult` using the result handler</p>|
 | <div class='method-sig' id='prefect-engine-result-resultinterface-to-result'><p class="prefect-class">prefect.engine.result.ResultInterface.to_result</p>(result_handler=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L47">[source]</a></span></div>
<p class="methods">If no result handler provided, returns self.  If a ResultHandler is provided, however, it will become the new result handler for this result.<br><br>**Args**:     <ul class="args"><li class="args">`result_handler (optional)`: an optional result handler to override the current handler</li></ul>**Returns**:     <ul class="args"><li class="args">`ResultInterface`: a potentially new Result object</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-result-result-write'><p class="prefect-class">prefect.engine.result.Result.write</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L149">[source]</a></span></div>
<p class="methods">Serialize and write the result to the target location.<br><br>**Returns**:     <ul class="args"><li class="args">`Any`: Result specific metadata about the written data.</li></ul></p>|

---
<br>

 ## SafeResult
 <div class='class-sig' id='prefect-engine-result-saferesult'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result.SafeResult</p>(value, result_handler)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L159">[source]</a></span></div>

A _safe_ representation of the result of a Prefect task; this class contains information about the serialized value of a task's result, and a result handler specifying how to deserialize this value

**Args**:     <ul class="args"><li class="args">`value (Any)`: the safe representation of a value     </li><li class="args">`result_handler (ResultHandler)`: the result handler to use when reading this result's value</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-saferesult-to-result'><p class="prefect-class">prefect.engine.result.SafeResult.to_result</p>(result_handler=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L177">[source]</a></span></div>
<p class="methods">Read the value of this result using the result handler and return a fully hydrated Result. If a new ResultHandler is provided, it will instead be used to read the underlying value and the `result_handler` attribute of this result will be reset accordingly.<br><br>**Args**:     <ul class="args"><li class="args">`result_handler (optional)`: an optional result handler to override the current handler</li></ul>**Returns**:     <ul class="args"><li class="args">`ResultInterface`: a potentially new Result object</li></ul></p>|

---
<br>

 ## NoResultType
 <div class='class-sig' id='prefect-engine-result-noresulttype'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.result.NoResultType</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L197">[source]</a></span></div>

A `SafeResult` subclass representing the _absence_ of computation / output.  A `NoResult` object returns itself for its `value` and its `safe_value`.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-result-noresulttype-to-result'><p class="prefect-class">prefect.engine.result.NoResultType.to_result</p>(result_handler=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result.py#L218">[source]</a></span></div>
<p class="methods">Performs no computation and returns self.<br><br>**Args**:     <ul class="args"><li class="args">`result_handler (optional)`: a passthrough for interface compatibility</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on March 30, 2020 at 17:55 UTC</p>