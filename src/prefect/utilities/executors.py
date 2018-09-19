# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import dask
import dask.bag


def dict_to_list(dd):
    """
    Given a dictionary of keys to States (or lists of States) which need to be
    iterated over, effectively converts any states which return a list to a list of individual states and
    zips the values together to return a list of
    dictionaries, with each key now associated to a single element.

    Example:
        ```
        dict_to_list(dict(x=State(result=[1, 2]), y=[State(result=3), State(result=4)]))
        # [{'x': State(result=1), 'y': State(3)}, {'x': State(result=2), 'y': State(result=4)}]
        ```
    """
    mapped = {e: state_to_list(s) for e, s in dd.items() if e.mapped}
    unmapped = {e: s for e, s in dd.items() if not e.mapped}
    m_list = [dict(zip(mapped, vals)) for vals in zip(*mapped.values())]
    for d in m_list:
        d.update(unmapped)
    return m_list


def state_to_list(s):
    """
    Converts a State `s` with an iterator as its result to a list of states of the same type.

    Example:
        ```python
        s = State(result=[1, 2, 3])
        state_to_list(s) # [State(result=1), State(result=2), State(result=3)]
    """
    if isinstance(s, list):
        return s
    return [type(s)(result=elem) for elem in s.result]


@dask.delayed
def _bagged_list(ss):
    """
    Converts a list of states, each of which returns a list of the same size, to
    a list of lists of states.

    E.g. [State(result=[1, 2]), State(result=[7, 8])] -> [[State(result=1), State(result=7)], [State(result=2), State(result=8)]]
    """
    expanded = [[type(s)(result=elem) for elem in s.result] for s in ss]
    return [list(zz) for zz in zip(*expanded)]


def unpack_dict_to_bag(*values, keys):
    "Convenience function for packaging up all keywords into a dictionary"
    return {k: v for k, v in zip(keys, values)}


def create_bagged_list(mapped, unmapped):
    """
    Given two lists of states, creates a `dask.bag` which maps over
    the states in `mapped` while appending the states in `unmapped`
    untouched.
    """

    to_bag = [s for s in mapped if not isinstance(s, dask.bag.Bag)]
    upstreams = dask.bag.map(
        lambda *args, x: list(args) + x,
        *[s for s in mapped + unmapped if s not in to_bag],
        x=dask.bag.from_delayed(_bagged_list(to_bag)) if to_bag else []
    )
    return upstreams
