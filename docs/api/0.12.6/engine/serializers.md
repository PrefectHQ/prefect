---
sidebarDepth: 2
editLink: false
---
# Result Serializers
---
 ## Serializer
 <div class='class-sig' id='prefect-engine-serializers-serializer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.serializers.Serializer</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L11">[source]</a></span></div>

Serializers are used by Results to handle the transformation of Python objects to and from bytes.

Subclasses should implement `serialize` and `deserialize`.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-serializers-serializer-deserialize'><p class="prefect-class">prefect.engine.serializers.Serializer.deserialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L34">[source]</a></span></div>
<p class="methods">Deserialize an object from bytes.<br><br>**Args**:     <ul class="args"><li class="args">`value (bytes)`: the value to deserialize</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the deserialized value</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-serializers-serializer-serialize'><p class="prefect-class">prefect.engine.serializers.Serializer.serialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L22">[source]</a></span></div>
<p class="methods">Serialize an object to bytes.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to serialize</li></ul>**Returns**:     <ul class="args"><li class="args">`bytes`: the serialized value</li></ul></p>|

---
<br>

 ## PickleSerializer
 <div class='class-sig' id='prefect-engine-serializers-pickleserializer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.serializers.PickleSerializer</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L47">[source]</a></span></div>

A `Serializer` that uses cloudpickle to serialize Python objects.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-serializers-pickleserializer-deserialize'><p class="prefect-class">prefect.engine.serializers.PickleSerializer.deserialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L62">[source]</a></span></div>
<p class="methods">Deserialize an object from bytes using cloudpickle.<br><br>**Args**:     <ul class="args"><li class="args">`value (bytes)`: the value to deserialize</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the deserialized value</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-serializers-pickleserializer-serialize'><p class="prefect-class">prefect.engine.serializers.PickleSerializer.serialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L50">[source]</a></span></div>
<p class="methods">Serialize an object to bytes using cloudpickle.<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to serialize</li></ul>**Returns**:     <ul class="args"><li class="args">`bytes`: the serialized value</li></ul></p>|

---
<br>

 ## JSONSerializer
 <div class='class-sig' id='prefect-engine-serializers-jsonserializer'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.serializers.JSONSerializer</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L84">[source]</a></span></div>

A Serializer that uses JSON to serialize objects

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-serializers-jsonserializer-deserialize'><p class="prefect-class">prefect.engine.serializers.JSONSerializer.deserialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L99">[source]</a></span></div>
<p class="methods">Deserialize an object from JSON<br><br>**Args**:     <ul class="args"><li class="args">`value (bytes)`: the value to deserialize</li></ul>**Returns**:     <ul class="args"><li class="args">`Any`: the deserialized value</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-serializers-jsonserializer-serialize'><p class="prefect-class">prefect.engine.serializers.JSONSerializer.serialize</p>(value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/serializers.py#L87">[source]</a></span></div>
<p class="methods">Serialize an object to JSON<br><br>**Args**:     <ul class="args"><li class="args">`value (Any)`: the value to serialize</li></ul>**Returns**:     <ul class="args"><li class="args">`bytes`: the serialized value</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>