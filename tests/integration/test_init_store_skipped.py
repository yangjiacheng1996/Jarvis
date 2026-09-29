"""store.sqlite3 is never created (T048 / Verification §8)."""

from __future__ import annotations

from pathlib import Path

from jarvis.jarvis_core import init_workspace


def test_store_sqlite3_never_created(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)
    assert not (tmp_path / "memory" / "store.sqlite3").exists()


def test_store_sqlite3_never_created_even_with_force(tmp_path: Path) -> None:
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    # Corrupt provider.toml, then re-init with --force
    (tmp_path / "provider.toml").write_text("garbage", encoding="utf-8")
    init_workspace(path=tmp_path, name="TestAgent", force=True)

    assert not (tmp_path / "memory" / "store.sqlite3").exists()


def test_store_item_detail_on_first_init(tmp_path: Path) -> None:
    """Detail string for store.sqlite3 is 'Scheduler 阶段创建' on first init."""
    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    store_item = next(it for it in result.items if it.name == "memory/store.sqlite3")
    assert store_item.state == "skipped"
    assert store_item.detail == "Scheduler 阶段创建"


def test_store_item_detail_when_file_exists(tmp_path: Path) -> None:
    """If a pre-existing file is at the store.sqlite3 path (e.g. external copy),
    detail is '已存在，未校验'."""
    init_workspace(path=tmp_path, name="TestAgent", force=False)

    # Simulate a Scheduler-placed file
    (tmp_path / "memory" / "store.sqlite3").write_bytes(b"some scheduler data")

    result = init_workspace(path=tmp_path, name="TestAgent", force=False)
    store_item = next(it for it in result.items if it.name == "memory/store.sqlite3")
    assert store_item.state == "skipped"
    assert store_item.detail == "已存在，未校验"
    # counts["skipped"] includes store.sqlite3 plus any others that were also skipped
    # (e.g. only store.sqlite3 here).
    assert result.counts["skipped"] >= 1