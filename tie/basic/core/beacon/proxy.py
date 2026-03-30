"""A proxy for a type that can be injected at runtime."""
from collections.abc import Callable
from typing import Type, TypeVar
from threading import Lock

class LazyLoadType:
    def __init__(self):
        pass

    def __getattribute__(self, attr):
        """Trigger proxy swap and return attribute."""
        if issubclass(object.__getattribute__(self, '__class__'), LazyLoadType):
            factory = object.__getattribute__(self, '__factory')
            resolve_lock= object.__getattribute__(self, '__resolve_lock')
            with resolve_lock:
                resolved_value = factory()
                __class__ = resolved_value.__class__
                try:
                    __dict__ = resolved_value.__dict__
                    object.__setattr__(self, '__dict__', __dict__)
                except AttributeError:
                    object.__setattr__(self, '__slots__', resolved_value.__slots__)

                object.__setattr__(self, '__class__', __class__)
        return getattr(self, attr)



    def __delattr__(self, attr):
        """Trigger the load and then perform the deletion."""
        # To trigger the load and raise an exception if the attribute
        # doesn't exist.
        self.__getattribute__(attr)
        delattr(self, attr)

class LazyLoadProxy:
    def __init__(self):
        pass

    def __getattribute__(self, attr):
        """Trigger proxy swap and return attribute."""
        factory = object.__getattribute__(self, '__factory')
        resolved = object.__getattribute__(self, '__resolved')
        if not resolved:
            resolve_lock= object.__getattribute__(self, '__resolve_lock')
            with resolve_lock:
                resolved_value = factory()
                __class__ = resolved_value.__class__
                # object.__setattr__(self, '__class__', __class__)
                object.__setattr__(self, '__factory', resolved_value)
                object.__setattr__(self, '__resolved', True)
                factory = resolved_value

        return getattr(factory, attr)



    def __delattr__(self, attr):
        """Trigger the load and then perform the deletion."""
        # To trigger the load and raise an exception if the attribute
        # doesn't exist.
        self.__getattribute__(attr)
        factory = object.__getattribute__(self, '__factory')
        delattr(factory, attr)


A = TypeVar('A')
def create_proxy(proxied_type: Type[A], factory: Callable[[], A]) -> A:
    __dict__ = dict(proxied_type.__dict__.items())
    if '__slots__' in __dict__:
        return type(
            f'Proxy[{proxied_type.__name__}]',
            (proxied_type, LazyLoadProxy),
            {
                '__init__': lambda s:None,
                '__factory': lambda s: factory(),
                '__resolve_lock': Lock(),
                '__resolved': False,
                '__slots__': (*proxied_type.__slots__, '__factory', '__resolve_lock', '__resolved')
            })() # type: ignore

    __dict__.pop('__init__', None) # make sure there is a default, no-arg init
    __dict__.pop('__name__', None) # we'll replace this (with the same thing)
    __dict__.update(
        {'__factory': lambda s: factory(), '__resolve_lock': Lock()}
    )

    return type(
        f'{proxied_type.__name__}',
        (LazyLoadType, proxied_type),
        __dict__)() # type: ignore
