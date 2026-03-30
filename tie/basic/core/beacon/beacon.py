"""Extremely late-binding and update-propogating dependency injection"""

# standard library
import contextlib
import inspect
import os
import threading
import weakref
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

from .proxy import LazyLoadType

B = TypeVar('B')


class InjectionError(Exception):
    """Injection error"""

    def __init__(self, type_, available_types: set[type]) -> None:
        """."""
        super().__init__(
            f'Cannot resolve {type_} in injector, available types are '
            f'[{", ".join(sorted([str(s) for s in available_types]))}]'
        )


class Injector:
    """Injects dependencies into objects"""

    _lock = threading.Lock()

    def __init__(self):
        """."""
        self._environment = None
        self._values: dict[type, Any] = {}
        self._factories = {}
        self._pid = os.getpid()
        self._proxies: dict[str, weakref.ref] = defaultdict(list)

    def factory(
        self,
        factory_fn: type[B] | Callable[[], B],
        provides: type[B] | None = None,
        *,
        singleton=True,
    ) -> type[B] | Callable[[], B]:
        """Add a factory to the injector.

        Can be called directly or used as a decorator
        """
        type_ = provides or factory_fn
        # check if this is as function decorator
        if not isinstance(factory_fn, type) and callable(factory_fn):
            annotations = inspect.get_annotations(factory_fn)
            if (return_type := annotations.get('return')) and isinstance(return_type, type):
                type_ = return_type
            else:
                ex_msg = 'Factory function must have a return type annotation'
                raise TypeError(ex_msg)

        self._factories[type_] = (factory_fn, singleton)

        old_value = self._values.pop(type_, None)

        if type_ in self._proxies:
            for proxy_ref in self._proxies[type_]:
                if proxy := proxy_ref():
                    new_value = self._resolve(type_)
                    if old_value is not None:
                        with contextlib.suppress(AttributeError):
                            old_value.__transpose__(new_value, type_)
                    object.__setattr__(proxy, '__resolved', new_value)

        return factory_fn

    def provide(self, value, *, type_: type[B] | None = None):
        """Add a value to the injector."""
        type_ = type_ or type(value)
        self._values[type_] = value

        if type_ in self._proxies:
            for proxy_ref in self._proxies[type_]:
                if proxy := proxy_ref():
                    object.__setattr__(proxy, '__resolved', value)

    def scan(self, type_):
        """Scan the injector for all values and factories of a given type."""
        for key in self._values:
            if issubclass(key, type_):
                yield key

        for key in self._factories:
            if issubclass(key, type_):
                yield key

    def __call__(
        self,
        key: type[B],
        *,
        proxy: bool = True,
    ) -> B:
        """Get a value or factory from the injector."""
        if not proxy:
            return self._resolve(key)

        proxy = InjectionProxy(key, lambda: self._resolve(key))
        ref = weakref.ref(proxy)
        self._proxies[key].append(ref)

        def remove_proxy_ref(key, ref):
            self._proxies[key] = [r for r in self._proxies[key] if r is not ref]

        weakref.finalize(proxy, remove_proxy_ref, key, ref)
        return proxy

    def _store_new_value(self, key: type[B], value: Any):
        """Store a new value in the injector."""
        self._values[key] = value

        if key in self._proxies:
            for proxy_ref in self._proxies[key]:
                if proxy := proxy_ref():
                    object.__setattr__(proxy, '__resolved', value)

    def _resolve(self, key: type[B]) -> B:
        if key in self._values:
            return self._values[key]
        if key in self._factories:
            fact, singleton = self._factories[key]
            with contextlib.suppress(Exception):
                value = fact()
            if singleton:
                self._values[key] = value
            return value

        raise InjectionError(key, set(self._values.keys()).union(set(self._factories.keys())))


inject = Injector()
factory = inject.factory
provide = inject.provide


# TODO:
# - Add __str__ to list what's available as provide/factory
