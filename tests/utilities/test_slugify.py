import inspect

from prefect.utilities.slugify import slugify


def test_slugify_has_expected_params():
    expected_params = {"lowercase", "max_length", "regex_pattern"}
    slugify_params = set(inspect.signature(slugify).parameters)
    assert expected_params.issubset(slugify_params)
