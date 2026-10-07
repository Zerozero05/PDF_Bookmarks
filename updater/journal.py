"""Durable journal and operation log, written before changing installed files."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time


def replace_file(source, destination, timeout=3):
    """Windows readers/scanners may momentarily deny rename/delete sharing.

    Retry only the OS sharing/access errors for a bounded interval. The old
    destination remains intact until the atomic replacement succeeds; a real
    permission problem still propagates and enters rollback.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(source, destination)
            return
        except OSError as error:
            if (os.name != "nt" or getattr(error, "winerror", None) not in (5, 32, 33)
                    or time.monotonic() >= deadline):
                raise
            time.sleep(0.05)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".journal-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        replace_file(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save(directory, value, state=None):
    persisted = dict(value)
    if state is not None:
        persisted["state"] = state
    persisted["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(Path(directory) / "journal.json", persisted)
    value.update(persisted)
    return value


def log(directory, message):
    with (Path(directory) / "update.log").open("a", encoding="utf-8") as output:
        output.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
        output.flush()
