"""Retry official-source downloads through transient network failures.

The gov.br servers that publish ANP and ANTT files sometimes reset connections from hosted CI
runners. A reset, a timeout or an HTTP 429/5xx says nothing about the data, so those are
retried with a growing pause. Anything else (an unexpected redirect, an invalid file, a
checksum or validation error) is raised at once, exactly as before.
"""

import http.client
import socket
import time
import urllib.error

TRANSIENT_HTTP_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
DELAYS_SECONDS = (5, 15, 45)


class SourceUnavailable(Exception):
    """The official source could not be reached after every retry."""

    def __init__(self, url, attempts, error):
        super().__init__(f"{url} unreachable after {attempts} attempts: {type(error).__name__}: {error}")
        self.url = url
        self.attempts = attempts
        self.last_error = type(error).__name__


def is_transient(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in TRANSIENT_HTTP_STATUS
    if isinstance(error, urllib.error.URLError):
        reason = error.reason
        return isinstance(reason, (ConnectionError, TimeoutError, socket.timeout, socket.gaierror))
    return isinstance(error, (ConnectionError, TimeoutError, socket.timeout,
                              http.client.RemoteDisconnected, http.client.IncompleteRead))


def with_retries(url, download, *, delays=DELAYS_SECONDS, sleep=time.sleep):
    """Call download() until it succeeds; retry only transient network errors."""
    attempts = len(delays) + 1
    for attempt in range(1, attempts + 1):
        try:
            return download()
        except Exception as error:
            if not is_transient(error):
                raise
            if attempt == attempts:
                raise SourceUnavailable(url, attempts, error) from error
            sleep(delays[attempt - 1])
