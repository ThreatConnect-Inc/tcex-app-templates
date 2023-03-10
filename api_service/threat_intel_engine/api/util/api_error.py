"""."""
# third-party
import falcon


class APIError(falcon.HTTPError):
    """Thin wrapper around falcon.HTTPError to return a consistent error format.

    Returns a response body with error and detail fields.
    """

    def __init__(self, status, error: str, details: any):
        """."""
        super().__init__(status)
        self.error = error
        self.details = details

    def to_dict(self, obj_type=dict):
        """."""
        result = obj_type()
        result['error'] = self.error
        result['details'] = self.details

        return result
