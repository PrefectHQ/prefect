---
sidebarDepth: 2
editLink: false
---
# Triggers
---
Triggers are functions that determine if task state should change based on
the state of preceding tasks.

## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-triggers-all-finished'><p class="prefect-class">prefect.triggers.all_finished</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L10">[source]</a></span></div>
<p class="methods">This task will run no matter what the upstream states are, as long as they are finished.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (set[State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-manual-only'><p class="prefect-class">prefect.triggers.manual_only</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L25">[source]</a></span></div>
<p class="methods">This task will never run automatically, because this trigger will always place the task in a Paused state. The only exception is if the "resume" keyword is found in the Prefect context, which happens automatically when a task starts in a Resume state.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (set[State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-all-finished'><p class="prefect-class">prefect.triggers.all_finished</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L10">[source]</a></span></div>
<p class="methods">This task will run no matter what the upstream states are, as long as they are finished.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (set[State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-all-successful'><p class="prefect-class">prefect.triggers.all_successful</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L41">[source]</a></span></div>
<p class="methods">Runs if all upstream tasks were successful. Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (set[State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-all-failed'><p class="prefect-class">prefect.triggers.all_failed</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L57">[source]</a></span></div>
<p class="methods">Runs if all upstream tasks failed. Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (set[State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-any-successful'><p class="prefect-class">prefect.triggers.any_successful</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L73">[source]</a></span></div>
<p class="methods">Runs if any tasks were successful. Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (set[State])`: the set of all upstream states</li></ul></p>|
 | <div class='method-sig' id='prefect-triggers-any-failed'><p class="prefect-class">prefect.triggers.any_failed</p>(upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/triggers.py#L89">[source]</a></span></div>
<p class="methods">Runs if any tasks failed. Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED` tasks are considered failures.<br><br>**Args**:     <ul class="args"><li class="args">`upstream_states (set[State])`: the set of all upstream states</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.0 on March 29, 2019 at 17:39 UTC</p>
