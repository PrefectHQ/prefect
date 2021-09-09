import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory

from typing_extensions import Literal


def exceptions_equal(a, b):
    """
    Exceptions cannot be compared by `==`. They can be compared using `is` but this
    will fail if the exception is serialized/deserialized so this utility does its
    best to assert equality using the type and args used to initialize the exception
    """
    if a == b:
        return True
    return type(a) == type(b) and getattr(a, "args", None) == getattr(b, "args", None)


def check_for_type_errors(code: str, expect: Literal["fail", "success"] = "success"):
    """
    Run mypy on a string of code
    """
    from mypy import api

    code = textwrap.dedent(code).strip()

    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test-file.py"
        path.write_text(code)
        stdout, stderr, result = api.run([str(path)])

    code_linenum = "\n".join(f"{i + 1}:\t{l}" for i, l in enumerate(code.split("\n")))
    output = textwrap.dedent(
        f"""
        Ran mypy on the following code
        
        {multiline_indent(code_linenum, 8)}

        Received the following output

        {multiline_indent(stdout.replace(f"{path}:", ""), 8)}
        {multiline_indent(stderr, 8)}
        """
    )

    if expect == "fail":
        assert result, output

    else:
        assert not result, output


def multiline_indent(string: str, spaces: int) -> str:
    """
    Utility to indent all but the first line in a string to the specified level,
    especially useful in textwrap.dedent calls where multiline strings are formatted in
    """
    return string.replace("\n", "\n" + " " * spaces)
