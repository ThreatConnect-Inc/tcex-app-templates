"""Backport of WSGI type definitions from the 3.11 wsgi.types module.

We're developing for 3.6, so missing several features like explicit type aliases and protocols,
but we can still define useful types.
"""
# standard library
from collections.abc import Callable, Iterable
from typing import Any

# we mostly just want the application definition.
__all__ = ['WSGIApplication']

StartResponse = Callable[
    [str, list[tuple[str, str]], BaseException | None], Callable[[bytes], object]
]
WSGIEnvironment = dict[str, Any]
WSGIApplication = Callable[[WSGIEnvironment, StartResponse], Iterable[bytes]]
