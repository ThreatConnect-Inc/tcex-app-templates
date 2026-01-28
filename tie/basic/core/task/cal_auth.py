"""CAL Authentication helper."""

# third-party
import requests


class CALAuth(requests.auth.AuthBase):  # pylint: disable=too-few-public-methods
    """Attach CAL auth headers to each request."""

    def __init__(self, token: str, timestamp: int) -> None:
        """Initialize class properties."""
        self.token = token
        self.timestamp = timestamp

    def __call__(self, r: requests.PreparedRequest):  # type: ignore[override]
        """Mutate request with CAL headers (Authorization + Timestamp)."""
        r.headers['Authorization'] = self.token
        r.headers['Timestamp'] = str(self.timestamp)
        return r
