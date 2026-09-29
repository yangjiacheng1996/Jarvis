"""Performance timing gates (T050).

NFR-001: idempotent re-run on healthy workspace < 500 ms (median over 100 iters)
NFR-001a: 0 sqlite3.connect calls during idempotent re-run (byte-level check)
NFR-002: first-time init < 2 s (median over 100 iters)

Marked @pytest.mark.slow — deselected by default; run with `pytest -m slow`.
"""

from __future__ import annotations

import sqlite3
import statistics
from pathlib import Path

import pytest

from jarvis.jarvis_core import init_workspace


@pytest.mark.slow
def test_idempotent_re_run_under_500ms(tmp_path: Path) -> None:
    """NFR-001: median of 100 iterations < 500 ms."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    # Warmup
    for _ in range(5):
        init_workspace(path=tmp_path, name="TestAgent", force=False)

    times: list[float] = []
    for _ in range(100):
        t0 = _perf()
        init_workspace(path=tmp_path, name="TestAgent", force=False)
        times.append(_perf() - t0)

    median = statistics.median(times)
    assert median < 0.5, f"idempotent re-run median {median*1000:.1f} ms >= 500 ms"


@pytest.mark.slow
def test_idempotent_re_run_no_sqlite_connect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001a: byte-level check must NOT call sqlite3.connect()."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    counter = {"n": 0}
    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        counter["n"] += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counting_connect)

    # Warmup
    for _ in range(5):
        init_workspace(path=tmp_path, name="TestAgent", force=False)

    counter["n"] = 0  # reset
    for _ in range(100):
        init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert counter["n"] == 0, f"sqlite3.connect was called {counter['n']} times"


@pytest.mark.slow
def test_first_time_init_under_2s(tmp_path: Path) -> None:
    """NFR-002: first-time init < 2 s (median over 100 iters on fresh dirs)."""
    times: list[float] = []
    for i in range(100):
        ws = tmp_path / f"ws_{i}"
        ws.mkdir()
        # Warmup: skip — first 5 iterations are warmup but measured.
        t0 = _perf()
        init_workspace(path=ws, name="TestAgent", force=False)
        times.append(_perf() - t0)

    median = statistics.median(times)
    assert median < 2.0, f"first-time init median {median:.3f} s >= 2 s"


def _perf() -> float:
    import time

    return time.perf_counter()