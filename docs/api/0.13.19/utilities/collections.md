---
sidebarDepth: 2
editLink: false
---
# Collections
---
 ## DotDict
 <div class='class-sig' id='prefect-utilities-collections-dotdict'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.collections.DotDict</p>(init_dict=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/collections.py#L37">[source]</a></span></div>

A `dict` that also supports attribute ("dot") access. Think of this as an extension to the standard python `dict` object.  **Note**: while any hashable object can be added to a `DotDict`, _only_ valid Python identifiers can be accessed with the dot syntax; this excludes strings which begin in numbers, special characters, or double underscores.

**Args**:     <ul class="args"><li class="args">`init_dict (dict, optional)`: dictionary to initialize the `DotDict`     with     </li><li class="args">`**kwargs (optional)`: key, value pairs with which to initialize the     `DotDict`</li></ul> **Example**:     
```python
    dotdict = DotDict({'a': 34}, b=56, c=set())
    dotdict.a # 34
    dotdict['b'] # 56
    dotdict.c # set()

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-utilities-collections-dotdict-copy'><p class="prefect-class">prefect.utilities.collections.DotDict.copy</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/collections.py#L105">[source]</a></span></div>
<p class="methods">Creates and returns a shallow copy of the current DotDict</p>|
 | <div class='method-sig' id='prefect-utilities-collections-dotdict-get'><p class="prefect-class">prefect.utilities.collections.DotDict.get</p>(key, default=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/collections.py#L65">[source]</a></span></div>
<p class="methods">This method is defined for MyPy, which otherwise tries to type the inherited `.get()` method incorrectly.<br><br>**Args**:     <ul class="args"><li class="args">`key (str)`: the key to retrieve     </li><li class="args">`default (Any)`: a default value to return if the key is not found</li></ul> **Returns**:     <ul class="args"><li class="args">`Any`: the value of the key, or the default value if the key is not found</li></ul></p>|
 | <div class='method-sig' id='prefect-utilities-collections-dotdict-to-dict'><p class="prefect-class">prefect.utilities.collections.DotDict.to_dict</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/collections.py#L109">[source]</a></span></div>
<p class="methods">Converts current `DotDict` (and any `DotDict`s contained within) to an appropriate nested dictionary.</p>|

---
<br>


## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-utilities-collections-merge-dicts'><p class="prefect-class">prefect.utilities.collections.merge_dicts</p>(d1, d2)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/collections.py#L118">[source]</a></span></div>
<p class="methods">Updates `d1` from `d2` by replacing each `(k, v1)` pair in `d1` with the corresponding `(k, v2)` pair in `d2`.<br><br>If the value of each pair is itself a dict, then the value is updated recursively.<br><br>**Args**:     <ul class="args"><li class="args">`d1 (MutableMapping)`: A dictionary to be replaced     </li><li class="args">`d2 (MutableMapping)`: A dictionary used for replacement</li></ul> **Returns**:     <ul class="args"><li class="args">A `MutableMapping` with the two dictionary contents merged</li></ul></p>|
 | <div class='method-sig' id='prefect-utilities-collections-as-nested-dict'><p class="prefect-class">prefect.utilities.collections.as_nested_dict</p>(obj, dct_class=<class 'prefect.utilities.collections.DotDict'>)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/collections.py#L146">[source]</a></span></div>
<p class="methods">Given a obj formatted as a dictionary, transforms it (and any nested dictionaries) into the provided dct_class<br><br>**Args**:     <ul class="args"><li class="args">`obj (Any)`: An object that is formatted as a `dict`     </li><li class="args">`dct_class (type)`: the `dict` class to use (defaults to DotDict)</li></ul> **Returns**:     <ul class="args"><li class="args">A `dict_class` representation of the object passed in <br></li></ul></p>|
 | <div class='method-sig' id='prefect-utilities-collections-dict-to-flatdict'><p class="prefect-class">prefect.utilities.collections.dict_to_flatdict</p>(dct, parent=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/collections.py#L185">[source]</a></span></div>
<p class="methods">Converts a (nested) dictionary to a flattened representation.<br><br>Each key of the flat dict will be a CompoundKey tuple containing the "chain of keys" for the corresponding value.<br><br>**Args**:     <ul class="args"><li class="args">`dct (dict)`: The dictionary to flatten     </li><li class="args">`parent (CompoundKey, optional)`: Defaults to `None`. The parent key     (you shouldn't need to set this)</li></ul> **Returns**:     <ul class="args"><li class="args">`dict`: A flattened dict</li></ul></p>|
 | <div class='method-sig' id='prefect-utilities-collections-flatdict-to-dict'><p class="prefect-class">prefect.utilities.collections.flatdict_to_dict</p>(dct, dct_class=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/collections.py#L211">[source]</a></span></div>
<p class="methods">Converts a flattened dictionary back to a nested dictionary.<br><br>**Args**:     <ul class="args"><li class="args">`dct (dict)`: The dictionary to be nested. Each key should be a         `CompoundKey`, as generated by `dict_to_flatdict()`     </li><li class="args">`dct_class (type, optional)`: the type of the result; defaults to `dict`</li></ul> **Returns**:     <ul class="args"><li class="args">`D`: An instance of `dct_class` used to represent a nested dictionary, bounded         as a MutableMapping or dict</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>