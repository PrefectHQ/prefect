---
sidebarDepth: 2
editLink: false
---
# spaCy Tasks
---
This module contains a collection of tasks for interacting with the spaCy library.
 ## SpacyNLP
 <div class='class-sig' id='prefect-tasks-spacy-spacy-tasks-spacynlp'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyNLP</p>(text="", nlp=None, spacy_model_name="en_core_web_sm", disable=None, component_cfg=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L7">[source]</a></span></div>

Task for processing text with a spaCy pipeline.

**Args**:     <ul class="args"><li class="args">`text (unicode, optional)`: string to be processed, can be provided during construction         or when task is run     </li><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline, if provided, this pipeline will be used instead         of being created from spacy_model_name     </li><li class="args">`spacy_model_name (str, optional)`: name of the spaCy language model, default         model is 'en_core_web_sm', will be ignored if nlp is provided     </li><li class="args">`disable (List[str], optional)`: list of pipeline components         to disable, only applicable to pipelines loaded from spacy_model_name     </li><li class="args">`component_cfg (dict, optional)`: a dictionary with extra keyword         arguments for specific components, only applicable to pipelines loaded from         spacy_model_name     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-spacy-spacy-tasks-spacynlp-run'><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyNLP.run</p>(text="")<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L58">[source]</a></span></div>
<p class="methods">Task run method. Creates a spaCy document.<br><br>**Args**:     <ul class="args"><li class="args">`text (unicode, optional)`: text to be processed</li></ul> **Returns**:     <ul class="args"><li class="args">`Doc`: spaCy document</li></ul></p>|

---
<br>

 ## SpacyTagger
 <div class='class-sig' id='prefect-tasks-spacy-spacy-tasks-spacytagger'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyTagger</p>(nlp=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L74">[source]</a></span></div>

Task for returning tagger from a spaCy pipeline.

**Args**:     <ul class="args"><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-spacy-spacy-tasks-spacytagger-run'><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyTagger.run</p>(nlp=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L89">[source]</a></span></div>
<p class="methods">Task run method. Returns tagger component of spaCy pipeline.<br><br>**Args**:     <ul class="args"><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline, must be provided if not         specified in construction</li></ul> **Returns**:     <ul class="args"><li class="args">`Tagger`: spaCy Tagger object</li></ul></p>|

---
<br>

 ## SpacyParser
 <div class='class-sig' id='prefect-tasks-spacy-spacy-tasks-spacyparser'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyParser</p>(nlp=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L109">[source]</a></span></div>

Task for returning parser from a spaCy pipeline.

**Args**:     <ul class="args"><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-spacy-spacy-tasks-spacyparser-run'><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyParser.run</p>(nlp=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L124">[source]</a></span></div>
<p class="methods">Task run method. Returns parser component of spaCy pipeline.<br><br>**Args**:     <ul class="args"><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline, must be provided if not         specified in construction</li></ul> **Returns**:     <ul class="args"><li class="args">`Parser`: spaCy Parser object</li></ul></p>|

---
<br>

 ## SpacyNER
 <div class='class-sig' id='prefect-tasks-spacy-spacy-tasks-spacyner'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyNER</p>(nlp=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L144">[source]</a></span></div>

Task for returning named entity recognizer from a spaCy pipeline.

**Args**:     <ul class="args"><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-spacy-spacy-tasks-spacyner-run'><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyNER.run</p>(nlp=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L159">[source]</a></span></div>
<p class="methods">Task run method. Returns named entity recognition component of spaCy pipeline.<br><br>**Args**:     <ul class="args"><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline, must be provided if not         specified in construction</li></ul> **Returns**:     <ul class="args"><li class="args">`NER`: spaCy NER object</li></ul></p>|

---
<br>

 ## SpacyComponent
 <div class='class-sig' id='prefect-tasks-spacy-spacy-tasks-spacycomponent'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyComponent</p>(component_name="", nlp=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L179">[source]</a></span></div>

Task for returning named component from a spaCy pipeline.

**Args**:     <ul class="args"><li class="args">`component_name (str, optional)`: name of spaCy pipeline component to return,         must be provided during construction or run time     </li><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-spacy-spacy-tasks-spacycomponent-run'><p class="prefect-class">prefect.tasks.spacy.spacy_tasks.SpacyComponent.run</p>(component_name, nlp=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/spacy/spacy_tasks.py#L197">[source]</a></span></div>
<p class="methods">Task run method. Returns named component of spaCy pipeline.<br><br>**Args**:     <ul class="args"><li class="args">`component_name (str, optional)`: name of spaCy pipeline component to return,         must be provided during construction or run time     </li><li class="args">`nlp (spaCy text processing pipeline, optional)`: a custom spaCy text         processing pipeline, must be provided if not         specified in construction</li></ul> **Returns**:     <ul class="args"><li class="args">`Component`: spaCy pipeline component object</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>