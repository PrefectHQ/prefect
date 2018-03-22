import copy
import random
import xxhash
import jsonpickle


def hash_object(obj, as_int=False):
    pkl = jsonpickle.encode(obj, unpicklable=False).encode()
    xhash = xxhash.xxh64(pkl)
    if as_int:
        return xhash.intdigest()
    else:
        return xhash.hexdigest()


def get_task_hashes(flow, seed=None):
    """
    Generates a unique ID for each task in a Flow, as well as the flow itself,
    using an optional seed for determinism.

    Flows can contain multiple copies of (identical) tasks, so a task's
    characteristics are not enough to determine a unique and stable ID.
    Moreover, the order of tasks in a flow is not defined, so the simple
    relationships between tasks are also inappropriate.

    The algorithm used here starts with a representation of each task.
    It then walks the tasks in topographical order, recomputing each task's
    representation by hashing it with the hashes of all preceding tasks.
    The result is that each task is now defined in terms of any ancestor
    tasks it has.

    Next, the algorithm walks backwards in topographical order, repeating
    the hashing process. The result is that each task is now defined in
    terms of its ancestors and its descendents.

    Next, the algorithm walks forwards again. Each task is now uniquely
    defined in terms of every other task it is connected to. However,
    it is still possible to have duplicates - tasks which have identical
    ancestors and descendents. When we encounter a duplicate, we modify
    the representation slightly, so that any downstream tasks pick up the
    modification. While the choice of which duplicate to modify is random,
    it is also practically inconsequential.

    """
    if seed is None:
        seed = random.getrandbits(128)

    # compute the initial
    hashes = {t: hash_object([t, seed]) for t in flow.tasks}
    edges_to = {}
    edges_from = {}
    sorted_tasks = flow.sorted_tasks()

    # precompute the edge lookups for performance
    for task in sorted_tasks:
        edges_to[task] = set()
        edges_from[task] = set()
    for edge in flow.edges:
        edges_to[edge.downstream_task].add(edge)
        edges_from[edge.upstream_task].add(edge)

    # forward pass
    for t in sorted_tasks:
        edges = [(hashes[e.upstream_task], e.key) for e in edges_to[t]]
        hashes[t] = hash_object([hashes[t], *sorted(edges)])

    # backward pass
    for t in reversed(sorted_tasks):
        edges = [(hashes[e.downstream_task], e.key) for e in edges_from[t]]
        hashes[t] = hash_object([hashes[t], *sorted(edges)])

    # forward pass with duplicate check
    final_hashes = {}
    for t in sorted_tasks:
        edges = [(hashes[e.upstream_task], e.key) for e in edges_to[t]]
        hash_candidate = hash_object([hashes[t], *sorted(edges)], as_int=True)
        while hash_candidate in final_hashes:
            hash_candidate = hash_object(hash_candidate, as_int=True)
        hashes[t] = hash_candidate
        final_hashes[hash_candidate] = t

    return final_hashes
