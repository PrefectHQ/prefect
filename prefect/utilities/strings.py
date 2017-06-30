import keyword

def is_valid_identifier(string):
    """
    Determines whether a string is a valid Python identifier (meaning it can
    be used as a variable name or keyword argument).

    Example:
        >>> is_valid_identifier('hi5')
        True
        >>> is_valid_identifier('5hi')
        False
        >>> is_valid_identifier('from')
        False
        >>> is_valid_identifier('hi.5')
        False
    """
    return string.isidentifier() and not keyword.iskeyword(string)


def name_with_suffix(
        name,
        predicate,
        first_suffix=1,
        delimiter='_',
        max_iters=1000,
        always_add_suffix=False):
    """
    Automatically adds a number suffix to a name until it becomes valid.

    Example:
        >>> name_with_suffix('name', predicate=lambda n: True)
        name_1
        >>> name_with_suffix('name', predicate=lambda n: int(n[-1]) > 2)
        name_3

    Args:
        name (string): the desired name

        predicate (callable): a function that takes the current name and
            returns whether it is valid. The numerical suffix will be
            incremented as long as the predicate returns False.

        first_suffix (int): the first suffix number that will be tried

        delimiter (string): a delimiter placed between the name and the suffix

        max_iters (int): evaluation will stop after this many iterations. An
            error will be raised.

        always_add_suffix (bool): if True, a suffix will be added to the name
            even if the provided name is valid. Defaults to False.
    """
    i = 0

    if always_add_suffix:
        new_name = '{}{}{}'.format(name, delimiter, first_suffix + i)
        i += 1
    else:
        new_name = name

    while not predicate(new_name) and i <= max_iters:
        new_name = '{}{}{}'.format(name, delimiter, first_suffix + i)
        i = i + 1

    if i > max_iters:
        raise ValueError('Maximum iterations reached.')

    return new_name
