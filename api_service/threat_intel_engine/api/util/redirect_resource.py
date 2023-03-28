"""Defines a resource to do redirects."""
# standard library
from collections.abc import Callable

# third-party
from falcon import HTTPPermanentRedirect  # pylint: disable=no-name-in-module

from ..resource_abc import ResourceABC


class RedirectResource(ResourceABC):
    """Redirects requests to the given URL."""

    supported_methods = [
        'GET',
        'HEAD',
        'POST',
        'PUT',
        'DELETE',
        'CONNECT',
        'OPTIONS',
        'TRACE',
        'PATCH',
    ]

    def __init__(self, redirect_to: Callable | str):
        """Create this resource.

        Args:
            redirect_to: either a path to redirect to, or a callable that will return the path to
            redirect to.  If a callable, it will be passed all parameters the on_* method receives.
        """
        self.redirect_to = redirect_to
        for method in RedirectResource.supported_methods:
            setattr(self, f'on_{method.lower()}', self._do_redirect)

    def _do_redirect(self, *args, **kwargs):
        if callable(self.redirect_to):
            raise HTTPPermanentRedirect(self.redirect_to(*args, **kwargs))

        raise HTTPPermanentRedirect(self.redirect_to)
