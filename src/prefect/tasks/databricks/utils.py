import six


def deep_string_coerce(content, json_path="json"):
    """
    Coerces content or all values of content if it is a dict to a string. The
    function will throw if content contains non-string or non-numeric types.

    The reason why we have this function is because the `self.json` field must be a
    dict with only string values. This is because `render_template` will fail
    for numerical values.
    """
    if isinstance(content, six.string_types):
        return content
    elif isinstance(content, six.integer_types + (float,)):
        # Databricks can tolerate either numeric or string types in the API backend.
        return str(content)
    elif isinstance(content, (list, tuple)):
        return [
            deep_string_coerce(content=item, json_path=f"{json_path}[{i}]")
            for i, item in enumerate(content)
        ]
    elif isinstance(content, dict):
        return {
            key: deep_string_coerce(content=value, json_path="f{json_path}[{k}]")
            for key, value in list(content.items())
        }
    else:
        raise ValueError(
            f"Type {type(content)} used for parameter {json_path} is not a number or a string"
        )
