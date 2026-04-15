"""Util Module

A Maybe object wraps a possibly-none value and allows you to traverse the wrappped value
without checks.

For example, given:
   >>> data = ...  # some dict data structure with optional pieces

the "normal" way:
   >>> ignore_body = (
   ...     dict.get('options', {})
   ...     .get('session', {})
   ...     .get('ignore_body', True)
   ... )

vs the maybe way:
   >>> ignore_body = maybe(data).options.session.ignore_body | True

Each Maybe object may be Something or Nothing.  If you try to move from a Something to a
non-existent index or key, you'll get Nothing. You can still traverse Nothing, it will just return
Nothing.

Note that each operation on a Maybe returns a Maybe *except* the final otherwise operation (the |
operator or the otherwise(maybe, default) function).  Otherwise unpacks a maybe and returns the
value it contains (if the Maybe is Something) or the given default value (if the Maybe is Nothing).

   >>> m = Maybe({'foo': 'bar'})
   <<< Something({'foo': 'bar'})
   >>> m.foo
   <<< Something('bar')
   >>> m.foo | 'Not there'
   <<< 'bar'
   >>> m.bash
   <<< Nothing
   >>> otherwise(m.bash, 'Not there')
   <<< "Not there"

There is no difference between using the | operator and using the otherwise() function.

You can also map a Maybe via the >> operator.  Map will return a
maybe wrapping the result of calling the given function with the wrapped value if the Maybe is
Something, else map will return Nothing:

   >>> maybe('foo') >> str.upper
   <<< Something("FOO")
   >>> Maybe(None) >> str.upper
   <<< Nothing


Note that sometimes you may not need to unwrap
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

T = TypeVar('T')
U = TypeVar('U')


class Maybe(ABC, Generic[T]):
    """."""

    @abstractmethod
    def __or__(self, default: U) -> T | U:
        """."""

    @abstractmethod
    def __rshift__(self, other: Callable[[T], U]) -> 'Maybe[U]':
        """."""

    @abstractmethod
    def __getattr__(self, item) -> 'Maybe[Any]':
        """."""

    @abstractmethod
    def __getitem__(self, name) -> 'Maybe[Any]':
        """."""


class _Nothing(Maybe[T]):
    """."""

    def __getattr__(self, item) -> '_Nothing[Any]':
        """."""
        return self

    def __getitem__(self, name) -> '_Nothing[Any]':
        """."""
        return self

    def __or__(self, default: U) -> U:
        """."""
        return default

    def __repr__(self):
        """."""
        return 'Nothing'

    def __rshift__(self, fn: Callable[[T], U]) -> '_Nothing[U]':
        """."""
        if not callable(fn):
            msg = 'Usage: maybe => callable to map a maybe.'
            raise TypeError(msg)
        return self  # type: ignore


Nothing = _Nothing()


class Something(Maybe[T]):
    """."""

    __match_args__ = ('_value',)

    def __init__(
        self,
        value: T,
        enable_dot_notation_for_containers=True,
        suppress_exceptions=True,
    ):
        """."""
        self._value: T = value
        self._dot_notation = enable_dot_notation_for_containers
        self._suppress_exceptions = suppress_exceptions

    def __getattr__(self, item) -> 'Maybe[Any]':
        """."""
        if not hasattr(self._value, item):
            if self._dot_notation:
                try:
                    if item in self._value:
                        return Something(
                            self._value[item],
                            self._dot_notation,
                            self._suppress_exceptions,
                        )  # type: ignore
                except TypeError:
                    return Nothing
            return Nothing
        if callable(getattr(self._value, item)):
            msg = f'Maybe has no method {item}.'
            raise TypeError(msg)

        return maybe(getattr(self._value, item))

    def __getitem__(self, name) -> 'Maybe[Any] | _Nothing':
        """."""
        try:
            return maybe(self._value[name])  # type: ignore
        except (TypeError, IndexError):
            return Nothing
        except Exception:
            if self._suppress_exceptions:
                return Nothing
            raise

    def __or__(self, default: U) -> U:
        """."""
        return self._value  # type: ignore

    def __repr__(self):
        """."""
        return f'{type(self).__name__}({self._value.__repr__()})'

    def __rshift__(self, fn: Callable[[T], U]) -> 'Maybe[U] | _Nothing':
        """."""
        if not callable(fn):
            msg = 'Usage: maybe => callable to map a maybe.'
            raise TypeError(msg)
        return maybe(fn(self._value))


def maybe(value: T, **dragons) -> Maybe[T]:
    """Wrap a possibly-None _value in a Maybe() object.

    Compare:
       >>> profile = {'options': {}}
       >>> profile.get('options', {}).get('session', {}).get(
       ...     'ignore_body', True
       ... )
       True
       >>> maybe(profile)['options']['session']['ignore_body'] | True
       True

    Arbitrary operations are allowed on Maybe() objects.  If the object is Something(),
    the operation will be called on the underlying _value and a Maybe() will be returned for the
    result.  If the object is Nothing(), all operations will yield Nothing().
       >>> maybe({'foo': 2}).get('foo')
       Something(2)
       >>> maybe({'foo': 2}).get('bar')
       Nothing()

    To get the _value of a Maybe, use  otherwise() or the | operator.
       >>> otherwise(maybe({'foo': 2})['bar'], 3)
       3
       >>> maybe({'foo': 2})['bar'] | 3
       3

    To test if a Maybe is Something, you can use isinstance() or issomething():
       >>> isinstance(maybe({'foo': 2}), Something)
       True
       >>> issomething(maybe({'foo': 2})['bar'])
       False

    Args:
        value: the value to wrap in a Maybe
        dragons: arbitrary keyword arguments to pass to the underlying value's constructor.

    Kwargs:  *"Here be dragons".  You should rarely need these options.
        enable_dot_notation_for_containers - if True, enables dot notation for container types, i.e,
            maybe({}).foo.bar.bash
        suppress_exceptions - if True, Something's will suppress exceptions that arise when
           traversing.  Note that errors relating to index bounds and containers not containing
           items will be suppressed regardless.
    """
    if isinstance(value, Maybe):  # right-associative
        return value

    if value is not None:
        return Something(
            value,
            dragons.get('enable_dot_notation_for_containers', True),
            dragons.get('suppress_exceptions', True),
        )
    return Nothing


def otherwise(m: Something[T] | _Nothing, default: Any) -> Any:
    """Return the reified _value of a Something, or the default _value for a Nothing.

    Arguments:
        m: the Maybe to reify.
        default: the _value to return if m is Nothing.
    """
    return m | default


def issomething(m: Maybe) -> bool:
    """Test if m is Something.

    Arguments:
        m: the Maybe to test.
    """
    return isinstance(m, Something)
