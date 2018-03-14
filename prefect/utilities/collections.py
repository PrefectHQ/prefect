def merge_dicts(d1, d2):
    """
    Updates d1 from d2 by replacing each (k, v1) pair in d1 with the
    corresponding (k, v2) pair in d2.

    If the value of each pair is itself a dict, then the value is updated
    recursively.
    """

    new_dict = d1.copy()

    for k, v in d2.items():
        if isinstance(new_dict.get(k), dict) and isinstance(v, dict):
            new_dict[k] = merge_dicts(new_dict[k], d2[k])
        else:
            new_dict[k] = d2[k]
    return new_dict


class DotDict(dict):
    """
    A dict that also supports attribute ("dot") access
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self

    def __repr__(self):
        return 'DotDict({})'.format(super().__repr__())


def dict_to_dotdict(dct):
    """
    Given a dct formatted as a dictionary, returns an object
    that also supports "dot" access:

    dct['data']['child']
    dct.data.child
    """
    if not isinstance(dct, dict):
        return dct
    for key, value in list(dct.items()):
        if isinstance(value, dict):
            dct[key] = dict_to_dotdict(value)
        elif isinstance(value, list):
            dct[key] = [dict_to_dotdict(v) for v in value]
    return DotDict(dct)
