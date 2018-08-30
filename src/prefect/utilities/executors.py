# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import dask
import dask.bag


def dict_to_list(dd):
    """
    Given a dictionary of keys to States (or lists of States) which need to be
    iterated over, effectively zips the values together and returns a list of
    dictionaries, with each key now associated to a single element.

    Example:
        ```
        dict_to_list(dict(x=State(result=[1, 2]), y=[State(result=3), State(result=4)]))
        # [{'x': State(result=1), 'y': State(3)}, {'x': State(result=2), 'y': State(result=4)}]
        ```
    """
    mapped_non_keyed = dd.pop(None, [])
    list_of_lists = list(zip(*[state_to_list(s) for s in mapped_non_keyed]))

    listed = {key: state_to_list(s) for key, s in dd.items()}
    if list_of_lists:
        listed.update({None: list_of_lists})
    return [dict(zip(listed, vals)) for vals in zip(*listed.values())]


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


def unpack_dict_to_bag(*other, upstreams=None, **kwargs):
    "Convenience function for packaging up all keywords into a dictionary"
    bag = list(other) or upstreams or []
    return dict({None: bag}, **kwargs)


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
