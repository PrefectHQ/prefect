import sys


if sys.version_info < (3, 6):
    collect_ignore = ["test_generate_docs.py"]
