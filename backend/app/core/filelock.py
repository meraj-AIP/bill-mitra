"""Whole-file advisory locks that work on Linux, macOS and Windows. fcntl does not exist on Windows, so local
development there uses msvcrt on the first byte of the file instead."""

import os
import time
from typing import IO

if os.name == "nt":
    import msvcrt

    def lock(handle: IO, blocking: bool = True) -> None:
        """Raises OSError when blocking is False and another process holds the lock."""
        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if not blocking:
                    raise
                time.sleep(0.05)

    def unlock(handle: IO) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def lock(handle: IO, blocking: bool = True) -> None:
        """Raises OSError when blocking is False and another process holds the lock."""
        fcntl.flock(handle, fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)

    def unlock(handle: IO) -> None:
        fcntl.flock(handle, fcntl.LOCK_UN)
