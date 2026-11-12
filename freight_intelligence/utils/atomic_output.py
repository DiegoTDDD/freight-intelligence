"""Publish a single output only after its writer completes successfully."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_output(destination):
    """Keep an existing file intact on writer failure; stage on the same filesystem."""
    destination = Path(destination)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.stem}-", suffix=destination.suffix,
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
