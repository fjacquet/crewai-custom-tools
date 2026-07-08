"""Hardened, no-shell subprocess runner for CLI-backed tools.

Safety properties (ported from osint_tools, infra coupling dropped):
- never invokes a shell (``shell=False``, argv list);
- ``validate_target`` rejects shell metacharacters and argument-injection (a
  leading ``-`` a downstream binary could read as a flag);
- resolves the binary on PATH (``BinaryMissing`` when absent; ``available`` for a
  boolean check);
- mandatory timeout (``CliTimeout`` on expiry);
- stdout truncated to a maximum byte size.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

_TARGET_RE = re.compile(r"^[A-Za-z0-9._-]{1,253}$")


class CliError(Exception):
    """Base exception for CLI runner errors."""


class BinaryMissing(CliError):
    """Raised when the requested binary cannot be resolved via PATH."""


class CliTimeout(CliError):
    """Raised when the subprocess exceeds the configured timeout."""


@dataclass
class CliResult:
    """Outcome of a CLI invocation."""

    ok: bool
    stdout: str
    returncode: int
    truncated: bool = False


def available(binary: str) -> bool:
    """Return True if ``binary`` is resolvable on PATH."""
    return shutil.which(binary) is not None


def validate_target(target: str) -> str:
    """Validate ``target`` as a safe CLI argument (domain/host/username).

    Allows only ``[A-Za-z0-9._-]``, 1-253 chars, and forbids a leading ``-``
    (which a downstream binary could misread as a flag — argument injection).
    Raises ``ValueError`` for anything else (spaces, shell metacharacters, flags).
    """
    if (
        not isinstance(target, str)
        or not _TARGET_RE.match(target)
        or target.startswith("-")
    ):
        raise ValueError(f"unsafe CLI target: {target!r}")
    return target


def run_cli(
    binary: str,
    args: list[str],
    *,
    timeout: float = 60.0,
    stdin: str | None = None,
    max_bytes: int = 8 * 1024 * 1024,
) -> CliResult:
    """Run ``binary`` with ``args`` as an argv list (never via a shell).

    Resolves ``binary`` on PATH (``BinaryMissing`` if absent), enforces
    ``timeout`` (``CliTimeout`` on expiry), and truncates stdout to ``max_bytes``.
    """
    path = shutil.which(binary)
    if path is None:
        raise BinaryMissing(binary)
    try:
        proc = subprocess.run(
            [path, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as e:
        raise CliTimeout(binary) from e
    out = proc.stdout or ""
    truncated = len(out.encode()) > max_bytes
    if truncated:
        out = out.encode()[:max_bytes].decode(errors="ignore")
    return CliResult(
        ok=proc.returncode == 0,
        stdout=out,
        returncode=proc.returncode,
        truncated=truncated,
    )
