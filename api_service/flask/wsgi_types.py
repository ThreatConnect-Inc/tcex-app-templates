"""Backport of WSGI type definitions from the 3.11 wsgi.types module.

We're developing for 3.6, so missing several features like explicit type aliases and protocols,
but we can still define useful types.
"""
# standard library
from typing import Any, Callable, Dict, Iterable, List, Optional

# we mostly just want the appliation definitoin.
__all__ = ['WSGIApplication']

StartResponse = Callable[
    [str, List[tuple[str, str]], Optional[BaseException]], Callable[[bytes], object]
]
WSGIEnvironment = Dict[str, Any]
WSGIApplication = Callable[[WSGIEnvironment, StartResponse], Iterable[bytes]]
