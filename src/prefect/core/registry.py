import os
import uuid
from collections import Counter
from typing import Dict
from warnings import warn as _warn

import cloudpickle
import xxhash
from cryptography.fernet import Fernet

import prefect
from prefect.core.flow import Flow
from prefect.core.task import Task
from prefect.utilities.json import dumps

FLOW_REGISTRY = {}


def register_flow(flow: Flow) -> None:
    """
    Registers a flow
    """
    if not isinstance(flow, Flow):
        raise TypeError("Expected a Flow; received {}".format(type(flow)))

    key = (flow.project, flow.name, flow.version)

    if (
        prefect.config.flows.registry.warn_on_duplicate_registration
        and key in FLOW_REGISTRY
    ):
        _warn(
            "Registering this flow overwrote a previously-registered flow "
            "with the same project, name, and version: {}".format(flow)
        )

    FLOW_REGISTRY[key] = flow


def load_flow(project, name, version) -> Flow:
    key = (project, name, version)
    if key not in FLOW_REGISTRY:
        raise KeyError("Flow not found: {}".format(key))
    return FLOW_REGISTRY[key]


def serialize_registry(path):
    serialized = cloudpickle.dumps(FLOW_REGISTRY)

    encryption_key = prefect.config.flows.registry.encryption_key
    if not encryption_key:
        _warn("No encryption key found in `config.toml`.")
    else:
        serialized = Fernet(encryption_key).encrypt(serialized)

    with open(path, "wb") as f:
        f.write(serialized)


def deserialize_registry(path):
    with open(path, "rb") as f:
        serialized = f.read()

    encryption_key = prefect.config.flows.registry.encryption_key
    if not encryption_key:
        _warn("No encryption key found in `config.toml`.")
    else:
        serialized = Fernet(encryption_key).decrypt(serialized)

    deserialized = cloudpickle.loads(serialized)
    FLOW_REGISTRY.update(deserialized)


def generate_flow_id(flow: Flow) -> str:
    """
    The flow id (for the purposes of hashing task IDs) depends only on project and name,
    not version. This is to allow tasks to be identified when versions change (if possible)
    """
    return str(uuid.UUID(bytes=_hash(flow.project) + _hash(flow.name)))


def generate_task_ids(flow: Flow) -> Dict[str, "Task"]:
    """
    Generates stable IDs for each task.

    If our goal was to create an ID for each task, we would simply produce a random
    hash. However, we would prefer to generate deterministic IDs. That way,
    identical flows will have the same task ids and near-identical flows will have
    overlapping task ids.

    If all tasks were unique, we could simply produce unique IDs by hashing the
    tasks themselves. However, Prefect allows duplicate tasks in a flow. Therefore,
    we take a few steps to iteratively produce unique IDs. There are five steps, and
    tasks go through each step until they have a unique ID:

        1. Generate an ID from the task's attributes.
            This fingerprints a task in terms of its own attributes.
        2. Generate an ID from the task's ancestors.
            This fingerprints a task in terms of the computational graph leading to it.
        3. Generate an ID from the task's descendents
            This fingerprints a task in terms of how it is used in a computational graph.
        4. Iteratively generate an ID from the task's neighbors
            This fingerprints a task in terms of a widening concentric circle of its neighbors.
        5. Adjust a root task's ID and recompute all non-unique descendents
            This step is only reached if a flow contains more than one unconnected but
            identical computational paths. The previous 4 steps are unable to distinguish
            between those two paths, so we pick one at random and adjust the leading tasks'
            IDs, as well as all following tasks. This is safe because we are sure that the
            computational paths are identical.
    """

    # precompute flow properties since we'll need to access them repeatedly
    tasks = flow.sorted_tasks()
    edges_to = flow.all_upstream_edges()
    edges_from = flow.all_downstream_edges()
    flow_id = generate_flow_id(flow)

    # -- Step 1 ---------------------------------------------------
    #
    # Generate an ID for each task by serializing it and hashing the serialized
    # representation with the flow's ID.
    #
    # This "fingerprints" each task in terms of its own characteristics.
    #
    # -----------------------------------------------------------

    ids = {t: _hash(dumps((t.serialize(), flow_id), sort_keys=True)) for t in tasks}

    # -- Step 2 ---------------------------------------------------
    #
    # Next, we iterate over the tasks in topological order and, for any task without
    # a unique ID, produce a new ID based on its current ID and the ID of any
    # upstream nodes. This fingerprints each task in terms of all its ancestors.
    #
    # -----------------------------------------------------------

    counter = Counter(ids.values())
    for task in tasks:
        if counter[ids[task]] == 1:
            continue

        # create a new id by hashing (task id, upstream edges, downstream edges)
        edges = sorted((e.key, ids[e.upstream_task]) for e in edges_to[task])
        ids[task] = _hash(str((ids[task], edges)))

    # -- Step 3 ---------------------------------------------------
    #
    # Next, we iterate over the tasks in reverse topological order and, for any task
    # without a unique ID, produce a new ID based on its current ID and the ID of
    # any downstream nodes. After this step, each task is fingerprinted by its
    # position in a computational chain (both ancestors and descendents).
    #
    # -----------------------------------------------------------

    counter = Counter(ids.values())
    for task in tasks:
        if counter[ids[task]] == 1:
            continue

        # create a new id by hashing (task id, upstream edges, downstream edges)
        edges = sorted((e.key, ids[e.downstream_task]) for e in edges_from[task])
        ids[task] = _hash(str((ids[task], edges)))

    # -- Step 4 ---------------------------------------------------
    #
    # It is still possible for tasks to have duplicate IDs. For example, the
    # following flow of identical tasks would not be able to differentiate between
    # y3 and z3 after a forward and backward pass.
    #
    #               x1 -> x2 -> x3 -> x4
    #                  \
    #               y1 -> y2 -> y3 -> y4
    #                  \
    #               z1 -> z2 -> z3 -> z4
    #
    # We could continue running forward and backward passes to diffuse task
    # dependencies through the graph, but that approach is inefficient and
    # introduces very long dependency chains. Instead, we take each task and produce
    # a new ID by hashing it with the IDs of all of its upstream and downstream
    # neighbors.
    #
    # Each time we repeat this step, the non-unique task ID incorporates information
    # from tasks farther and farther away, because its neighbors are also updating
    # their IDs from their own neighbors. (note that we could use this algorithm
    # exclusively, but starting with a full forwards and backwards pass is much
    # faster!)
    #
    # However, it is still possible for this step to fail to generate a unique ID
    # for every task. The simplest example of this case is a flow with two
    # unconnected but identical tasks; the algorithm will be unable to differentiate
    # between the two based solely on their neighbors.
    #
    # Therefore, we continue updating IDs in this step only until the number of
    # unique IDs stops increasing. At that point, any remaining duplicates can not
    # be distinguished on the basis of neighboring nodes.
    #
    # -----------------------------------------------------------

    counter = Counter(ids.values())

    # continue this algorithm as long as the number of unique ids keeps changing
    while True:

        # store the number of unique ids at the beginning of the loop
        starting_unique_id_count = len(counter)

        for task in tasks:

            # if the task already has a unique id, just go to the next one
            if counter[ids[task]] == 1:
                continue

            # create a new id by hashing the task ID with upstream dn downstream IDs
            edges = [
                sorted((e.key, ids[e.upstream_task]) for e in edges_to[task]),
                sorted((e.key, ids[e.downstream_task]) for e in edges_from[task]),
            ]
            ids[task] = _hash(str((ids[task], edges)))

        # recompute a new counter.
        # note: we can't do this incremenetally because we can't guarantee the
        # iteration order, and incremental updates would implicitly depend on order
        counter = Counter(ids.values())

        # if the new counter has the same number of unique IDs as the old counter,
        # then the algorithm is no longer able to produce useful ids
        if len(counter) == starting_unique_id_count:
            break

    # -- Step 5 ---------------------------------------------------
    #
    # If the number of unique IDs is less than the number of tasks at this stage, it
    # means that the algorithm in step 4 was unable to differentiate between some
    # tasks. This is only possible if the flow contains identical but unconnected
    # computational paths.
    #
    # To remedy this, we change the ids of the duplicated root tasks until they are
    # unique, then recompute the ids of all downstream tasks. While this chooses the
    # affected root task at random, we are confident that the tasks are exact
    # duplicates so this is of no consequence.
    #
    # -----------------------------------------------------------

    while len(counter) < len(tasks):
        for task in tasks:
            # recompute each task's ID until it is unique
            while counter[ids[task]] != 1:
                edges = sorted((e.key, ids[e.upstream_task]) for e in edges_to[task])
                ids[task] = _hash(str((ids[task], edges)))
                counter[ids[task]] += 1

    return {str(uuid.UUID(bytes=i * 2)): task for task, i in ids.items()}


def _hash(value):
    return xxhash.xxh64(value).digest()
