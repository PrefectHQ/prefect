import hashlib
import itertools
import random
import uuid
from collections import Counter

import jsonpickle

FLOWS = {}
TASKS = {}


def get_hash(obj):
    if isinstance(obj, str):
        obj = obj.encode()
    return hashlib.md5(obj).digest()


def xor(hash1, hash2):
    """
    Computes the bitwise XOR between two byte hashes
    """
    return bytes([x ^ y for x, y in zip(hash1, itertools.cycle(hash2))])


def generate_flow_id(flow, seed=None):
    if seed is None:
        seed = random.getrandbits(128)
    seed = get_hash(str(seed))

    hsh = get_hash('{}{}'.format(flow.name, flow.version))
    return str(uuid.UUID(bytes=xor(seed, hsh)))


def generate_task_ids(flow, seed=None):
    flow_id = generate_flow_id(flow, seed=seed)
    if seed is None:
        seed = random.getrandbits(128)
    seed = xor(uuid.UUID(flow_id).bytes, get_hash(str(seed)))

    # initial pass
    # define each task based on its own structure
    hashes = {
        t: get_hash(jsonpickle.encode((t, seed), unpicklable=False))
        for t in flow.sorted_tasks()
    }
    counter = Counter(hashes.values())
    final_hashes = {}

    # forward pass
    # define each task in terms of the computational path of its ancestors
    for t in flow.sorted_tasks():
        if counter[hashes[t]] == 1:
            final_hashes[t] = hashes[t]
            continue

        edge_hashes = sorted(
            (e.key, hashes[e.upstream_task]) for e in flow.edges_to(t))
        hashes[t] = get_hash(str((hashes[t], edge_hashes)))
        counter[hashes[t]] += 1

    # backward pass
    # define each task in terms of the computational path of its descendents
    for t in reversed(flow.sorted_tasks()):
        if counter[hashes[t]] == 1:
            final_hashes[t] = hashes[t]
            continue

        edge_hashes = sorted(
            (e.key, hashes[e.downstream_task]) for e in flow.edges_from(t))
        hashes[t] = get_hash(str((hashes[t], edge_hashes)))
        counter[hashes[t]] += 1

    # forward pass #2
    # define each task in terms of the computational path of every task it's
    # connected to
    #
    # any task that is still a duplicate at this stage is TRULY a duplicate;
    # there is nothing about its computational path that differentiates it.
    # We can randomly choose one and modify its hash (and the hash of all
    # following tasks) without consequence.
    for t in flow.sorted_tasks():
        if counter[hashes[t]] == 1:
            final_hashes[t] = hashes[t]
            continue

        edge_hashes = sorted(
            (e.key, hashes[e.upstream_task]) for e in flow.edges_to(t))
        hashes[t] = get_hash(str((hashes[t], edge_hashes)))
        counter[hashes[t]] += 1

        # duplicate check
        while counter[hashes[t]] > 1:
            hashes[t] = get_hash(hashes[t])
            counter[hashes[t]] += 1
        final_hashes[t] = hashes[t]

    return {
        t: str(uuid.UUID(bytes=xor(seed, h)))
        for t, h in final_hashes.items()
    }


def register_flow(flow, seed=None):
    flow_id = generate_flow_id(flow, seed=seed)
    task_ids = generate_task_ids(flow, seed=seed)
    FLOWS[flow_id] = flow
    TASKS.update({i: task for task, i in task_ids.items()})
    return dict(flow_id=flow_id, task_ids=task_ids)


def get_flow_from_id(flow_id):
    if flow_id in FLOWS:
        return FLOWS[flow_id]
    else:
        raise ValueError('Flow not found: {}'.format(flow_id))


def get_task_from_id(task_id):
    if task_id in TASKS:
        return TASKS[task_id]
    else:
        raise ValueError('Task not found: {}'.format(task_id))
