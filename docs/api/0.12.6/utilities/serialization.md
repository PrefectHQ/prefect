---
sidebarDepth: 2
editLink: false
---
# Serialization
---
 ## JSONCompatible
 <div class='class-sig' id='prefect-utilities-serialization-jsoncompatible'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.serialization.JSONCompatible</p>(*args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/serialization.py#L168">[source]</a></span></div>

Field that ensures its values are JSON-compatible during serialization and deserialization

**Args**:     <ul class="args"><li class="args">`*args (Any)`: the arguments accepted by `marshmallow.Field`     </li><li class="args">`**kwargs (Any)`: the keyword arguments accepted by `marshmallow.Field`</li></ul>


---
<br>

 ## Nested
 <div class='class-sig' id='prefect-utilities-serialization-nested'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.serialization.Nested</p>(nested, value_selection_fn, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/serialization.py#L192">[source]</a></span></div>

An extension of the Marshmallow Nested field that allows the value to be selected via a value_selection_fn.

Note that because the value_selection_fn is always called, users must return `marshmallow.missing` if they don't want this field included in the resulting serialized object.

**Args**:     <ul class="args"><li class="args">`nested (type)`: the nested schema class     </li><li class="args">`value_selection_fn (Callable)`: a function that is called whenever the object is         serialized, to retrieve the object (if not available as a simple attribute of the         parent schema)     </li><li class="args">`**kwargs (Any)`: the keyword arguments accepted by `marshmallow.Field`</li></ul>


---
<br>

 ## Bytes
 <div class='class-sig' id='prefect-utilities-serialization-bytes'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.serialization.Bytes</p>(*args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/serialization.py#L234">[source]</a></span></div>

A Marshmallow Field that serializes bytes to a base64-encoded string, and deserializes a base64-encoded string to bytes.

**Args**:     <ul class="args"><li class="args">`*args (Any)`: the arguments accepted by `marshmallow.Field`     </li><li class="args">`**kwargs (Any)`: the keyword arguments accepted by `marshmallow.Field`</li></ul>


---
<br>

 ## UUID
 <div class='class-sig' id='prefect-utilities-serialization-uuid'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.serialization.UUID</p>(*args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/serialization.py#L256">[source]</a></span></div>

Replacement for fields.UUID that performs validation but returns string objects, not UUIDs

**Args**:     <ul class="args"><li class="args">`*args (Any)`: the arguments accepted by `marshmallow.Field`     </li><li class="args">`**kwargs (Any)`: the keyword arguments accepted by `marshmallow.Field`</li></ul>


---
<br>

 ## FunctionReference
 <div class='class-sig' id='prefect-utilities-serialization-functionreference'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.serialization.FunctionReference</p>(valid_functions, reject_invalid=True, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/serialization.py#L299">[source]</a></span></div>

Field that stores a reference to a function as a string and reloads it when deserialized.

**Args**:     <ul class="args"><li class="args">`valid_functions (List[Callable])`: a list of functions that will be serialized as string         references     </li><li class="args">`reject_invalid (bool)`: if True, functions not in `valid_functions` will be rejected.         If False, any value will be allowed, but only functions in `valid_functions` will         be deserialized.     </li><li class="args">`**kwargs (Any)`: the keyword arguments accepted by `marshmallow.Field`</li></ul>


---
<br>


## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-utilities-serialization-to-qualified-name'><p class="prefect-class">prefect.utilities.serialization.to_qualified_name</p>(obj)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/serialization.py#L26">[source]</a></span></div>
<p class="methods">Given an object, returns its fully-qualified name, meaning a string that represents its Python import path<br><br>**Args**:     <ul class="args"><li class="args">`obj (Any)`: an importable Python object</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the qualified name</li></ul></p>|
 | <div class='method-sig' id='prefect-utilities-serialization-from-qualified-name'><p class="prefect-class">prefect.utilities.serialization.from_qualified_name</p>(obj_str)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/serialization.py#L40">[source]</a></span></div>
<p class="methods">Retrives an object from a fully qualified string path. The object must be imported in advance.<br><br>**Args**:     <ul class="args"><li class="args">`obj_str (str)`: the qualified path of the object</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the object retrieved from the qualified path</li></ul>**Raises**:     <ul class="args"><li class="args">`ValueError`: if the object could not be loaded from the supplied path. Note that         this function will not import objects; they must be imported in advance.</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>