---
sidebarDepth: 2
editLink: false
---
# Result Serializers
---
 ## Serializer
 <div class='class-sig' id='prefect-engine-serializers-serializer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.serializers.Serializer</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L21">[source]</a></span></div>

Serializers are used by Results to handle the transformation of Python objects to and from bytes.

Subclasses should implement `serialize` and `deserialize`.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-serializers-serializer-deserialize'><p class="prefect-class">prefect.engine.serializers.Serializer.deserialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L44">[source]</a></span></div>
<p class="methods">Deserialize an object from bytes.<br><br>**Args**:     <ul class="args"><li class="args">`value (bytes)`: the value to deserialize</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the deserialized value</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-serializers-serializer-serialize'><p class="prefect-class">prefect.engine.serializers.Serializer.serialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L32">[source]</a></span></div>
<p class="methods">Serialize an object to bytes.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to serialize</li></ul> **Returns**:     <ul class="args"><li class="args">`bytes`: the serialized value</li></ul></p>|

---
<br>

 ## PickleSerializer
 <div class='class-sig' id='prefect-engine-serializers-pickleserializer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.serializers.PickleSerializer</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L57">[source]</a></span></div>

A `Serializer` that uses cloudpickle to serialize Python objects.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-serializers-pickleserializer-deserialize'><p class="prefect-class">prefect.engine.serializers.PickleSerializer.deserialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L72">[source]</a></span></div>
<p class="methods">Deserialize an object from bytes using cloudpickle.<br><br>**Args**:     <ul class="args"><li class="args">`value (bytes)`: the value to deserialize</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the deserialized value</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-serializers-pickleserializer-serialize'><p class="prefect-class">prefect.engine.serializers.PickleSerializer.serialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L60">[source]</a></span></div>
<p class="methods">Serialize an object to bytes using cloudpickle.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to serialize</li></ul> **Returns**:     <ul class="args"><li class="args">`bytes`: the serialized value</li></ul></p>|

---
<br>

 ## JSONSerializer
 <div class='class-sig' id='prefect-engine-serializers-jsonserializer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.serializers.JSONSerializer</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L94">[source]</a></span></div>

A Serializer that uses JSON to serialize objects

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-serializers-jsonserializer-deserialize'><p class="prefect-class">prefect.engine.serializers.JSONSerializer.deserialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L109">[source]</a></span></div>
<p class="methods">Deserialize an object from JSON<br><br>**Args**:     <ul class="args"><li class="args">`value (bytes)`: the value to deserialize</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the deserialized value</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-serializers-jsonserializer-serialize'><p class="prefect-class">prefect.engine.serializers.JSONSerializer.serialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L97">[source]</a></span></div>
<p class="methods">Serialize an object to JSON<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to serialize</li></ul> **Returns**:     <ul class="args"><li class="args">`bytes`: the serialized value</li></ul></p>|

---
<br>

 ## DateTimeSerializer
 <div class='class-sig' id='prefect-engine-serializers-datetimeserializer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.serializers.DateTimeSerializer</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L122">[source]</a></span></div>

A Serializer for working with human-readable datetimes

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-serializers-datetimeserializer-deserialize'><p class="prefect-class">prefect.engine.serializers.DateTimeSerializer.deserialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L137">[source]</a></span></div>
<p class="methods">Deserialize an datetime from human-readable bytes<br><br>**Args**:     <ul class="args"><li class="args">`value (bytes)`: the value to deserialize</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the deserialized value</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-serializers-datetimeserializer-serialize'><p class="prefect-class">prefect.engine.serializers.DateTimeSerializer.serialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L125">[source]</a></span></div>
<p class="methods">Serialize a datetime to human-readable bytes<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to serialize</li></ul> **Returns**:     <ul class="args"><li class="args">`bytes`: the serialized value</li></ul></p>|

---
<br>

 ## PandasSerializer
 <div class='class-sig' id='prefect-engine-serializers-pandasserializer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.serializers.PandasSerializer</p>(file_type, deserialize_kwargs=None, serialize_kwargs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L150">[source]</a></span></div>

A Serializer for Pandas DataFrames.

**Args**:     <ul class="args"><li class="args">`file_type (str)`: The type you want the resulting file to be         saved as, e.g. "csv" or "parquet". Must match a type used         in a `DataFrame.to_` method and a `pd.read_` function.     </li><li class="args">`deserialize_kwargs (dict, optional)`: Keyword arguments to pass to the         serialization method.     </li><li class="args">`serialize_kwargs (dict, optional)`: Keyword arguments to pass to the         deserialization method.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-serializers-pandasserializer-deserialize'><p class="prefect-class">prefect.engine.serializers.PandasSerializer.deserialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L203">[source]</a></span></div>
<p class="methods">Deserialize an object to a Pandas DataFrame<br><br>**Args**:     <ul class="args"><li class="args">`value (bytes)`: the value to deserialize</li></ul> **Returns**:     <ul class="args"><li class="args">`DataFrame`: the deserialized DataFrame</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-serializers-pandasserializer-serialize'><p class="prefect-class">prefect.engine.serializers.PandasSerializer.serialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L180">[source]</a></span></div>
<p class="methods">Serialize a Pandas DataFrame to bytes.<br><br>**Args**:     <ul class="args"><li class="args">`value (DataFrame)`: the DataFrame to serialize</li></ul> **Returns**:     <ul class="args"><li class="args">`bytes`: the serialized value</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>