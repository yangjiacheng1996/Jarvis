"""Shared pytest fixtures (T011)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace() -> Path:
    """Return a fresh empty temp directory; cleanup on teardown.

    Not autouse — must be requested explicitly in test signatures.
    """
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)