import sqlite3
import tarfile
import tempfile
from pathlib import Path
from backup import create, restore
from io import BytesIO

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    db=root/"live.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("create table fixture (value text)")
        conn.execute("insert into fixture values ('checked')")
    media=root/"media"
    media.mkdir()
    (media/"example.jpg").write_bytes(b"fixture")
    archive=root/"backup.tar.gz"
    create(db,media,archive)
    restored=root/"restore"
    restore(archive,restored)
    with sqlite3.connect(restored/"store.sqlite3") as conn:
        assert conn.execute("select value from fixture").fetchone()==("checked",)
    assert (restored/"media/example.jpg").read_bytes()==b"fixture"
    try:
        restore(archive,restored)
    except FileExistsError: pass
    else: raise AssertionError("restore overwrote existing destination")
    bad=root/"bad.tar.gz"
    with tarfile.open(bad,"w:gz") as tf:
        info=tarfile.TarInfo("../escape")
        info.size=1
        tf.addfile(info,BytesIO(b"x"))
    try:
        restore(bad,root/"unsafe")
    except ValueError: pass
    else: raise AssertionError("unsafe tar accepted")
    assert not (root/"escape").exists()
    print("PASS backup, restore, refusal to overwrite and traversal rejection")
