from contextlib import contextmanager
from contextvars import Context, ContextVar, Token
from typing import Dict


@contextmanager
def temporary_context(context: Context):
    tokens: Dict[ContextVar, Token] = {}
    for key, value in context.items():
        token = key.set(value)
        tokens[key] = token
    try:
        yield
    finally:
        for key, token in tokens.items():
            key.reset(token)
