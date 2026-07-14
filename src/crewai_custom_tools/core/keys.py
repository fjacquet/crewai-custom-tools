"""Fail-fast API key validation for tool classes.

Tools call :func:`require_api_key` in ``model_post_init`` so a missing key
raises ``ValueError`` at instantiation — not at first API call. Consumers that
want to skip key-less tools gracefully catch ``ValueError`` at construction.
"""

import os


def require_api_key(*env_vars: str, tool_name: str) -> str:
    """Return the first non-empty value among ``env_vars`` or raise ``ValueError``."""
    for var in env_vars:
        value = os.getenv(var)
        if value:
            return value
    names = " or ".join(env_vars)
    raise ValueError(f"{tool_name} requires {names} environment variable")
