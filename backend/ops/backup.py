"""Offline SQLite + media backup and non-destructive restore. Run with app stopped."""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def integrity(path):
    uri=path.resolve().as_uri()+"?mode=ro"
    with sqlite3.connect(uri,uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchall()!=[("ok",)]:
            raise ValueError("SQLite integrity check failed")

def safe_media(root):
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Invalid media root")
    for p in sorted(root.rglob("*")):
        mode=p.lstat().st_mode
        if stat.S_ISDIR(mode): continue
        if not stat.S_ISREG(mode): raise ValueError("Media symlink/special file rejected")
        yield p

def create(db,media,output):
    if not db.is_file() or db.is_symlink(): raise ValueError("Database missing")
    if output.exists(): raise FileExistsError(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.resolve().is_relative_to(media.resolve()): raise ValueError("Backup must be outside media")
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        root=Path(tmp)
        snapshot=root/"store.sqlite3"
        with sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True) as source, sqlite3.connect(snapshot) as dest:
            source.backup(dest)
        integrity(snapshot)
        entries={"store.sqlite3":digest(snapshot)}
        for path in safe_media(media):
            relative="media/"+path.relative_to(media).as_posix()
            target=root/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
            entries[relative]=digest(target)
        (root/"manifest.json").write_text(json.dumps(entries,sort_keys=True),encoding="utf-8")
        archive=root/"backup.tar.gz"
        with tarfile.open(archive,"w:gz") as tf:
            for name in sorted([*entries,"manifest.json"]):
                tf.add(root/name,arcname=name,recursive=False)
        os.chmod(archive,0o600)
        # Atomic exclusive publish: cannot overwrite previous backup.
        os.link(archive,output)
    print("Backup created; keep private and copy encrypted off-site.")

def restore(archive,destination):
    if destination.exists(): raise FileExistsError("Restore destination must not exist")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        root=Path(tmp)/"restored"
        root.mkdir(mode=0o700)
        with tarfile.open(archive,"r:gz") as tf:
            seen=set()
            for item in tf:
                name=item.name
                p=PurePosixPath(name)
                if (not item.isfile() or p.is_absolute() or ".." in p.parts or str(p)!=name or name in seen
                        or not (name in {"store.sqlite3","manifest.json"} or name.startswith("media/"))):
                    raise ValueError("Unsafe archive entry")
                seen.add(name)
                target=root/name
                target.parent.mkdir(parents=True,exist_ok=True)
                with tf.extractfile(item) as src,target.open("xb") as dst:
                    shutil.copyfileobj(src,dst)
                os.chmod(target,0o600)
        manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest,dict) or set(manifest)!=seen-{"manifest.json"} or "store.sqlite3" not in manifest:
            raise ValueError("Manifest mismatch")
        if any(digest(root/name)!=value for name,value in manifest.items()):
            raise ValueError("Checksum mismatch")
        integrity(root/"store.sqlite3")
        (root/"media").mkdir(exist_ok=True)
        if destination.exists(): raise FileExistsError(destination)
        root.rename(destination)
    print("Restore verified in a new directory; live data was not overwritten.")

if __name__=="__main__":
    os.umask(0o077)
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="command",required=True)
    c=sub.add_parser("create")
    c.add_argument("--db",type=Path,required=True)
    c.add_argument("--media",type=Path,required=True)
    c.add_argument("--output",type=Path,required=True)
    r=sub.add_parser("restore")
    r.add_argument("--archive",type=Path,required=True)
    r.add_argument("--destination",type=Path,required=True)
    args=parser.parse_args()
    if args.command=="create": create(args.db,args.media,args.output)
    else: restore(args.archive,args.destination)
