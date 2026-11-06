"""Retry only transient model request failures."""

import time

from openai import APIConnectionError, APIStatusError


def is_retryable(error):
    if isinstance(error, (APIConnectionError, ConnectionError, TimeoutError)):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code == 429 or 500 <= error.status_code < 600
    return False


def call_with_retry(func, max_retries=2, base_delay=1):
    """Call once, then retry eligible failures with exponential backoff."""
    if type(max_retries) is not int or max_retries < 0 or base_delay < 0:
        raise ValueError("Retry limits must be non-negative")
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as error:
            if attempt == max_retries or not is_retryable(error):
                raise
            time.sleep(base_delay * 2 ** attempt)
