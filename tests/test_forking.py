import os
import threading

import pytest

import sdk_reforge
from sdk_reforge import Options


def _read_exact(fd: int, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = os.read(fd, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork")
def test_child_process_replaces_inherited_singleton_lock() -> None:
    sdk_reforge.reset_instance()

    lock = getattr(sdk_reforge, "__lock")
    ready = threading.Event()
    release = threading.Event()

    def hold_lock() -> None:
        with lock.write_locked():
            ready.set()
            release.wait(timeout=5)

    holder = threading.Thread(target=hold_lock)
    holder.start()
    ready.wait(timeout=2)

    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(read_fd)
            sdk_reforge.set_options(
                Options(
                    reforge_datasources="LOCAL_ONLY",
                    collect_sync_interval=None,
                )
            )
            os.write(write_fd, b"ok")
        finally:
            os.close(write_fd)
            os._exit(0)

    os.close(write_fd)
    try:
        os.waitpid(pid, 0)
        assert _read_exact(read_fd, 2) == b"ok"
    finally:
        os.close(read_fd)
        release.set()
        holder.join(timeout=2)
        sdk_reforge.reset_instance()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork")
def test_child_process_creates_fresh_singleton_sdk_instance() -> None:
    sdk_reforge.reset_instance()
    sdk_reforge.set_options(
        Options(
            reforge_datasources="LOCAL_ONLY",
            collect_sync_interval=None,
        )
    )
    parent_sdk = sdk_reforge.get_sdk()
    parent_hash = parent_sdk.instance_hash

    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(read_fd)
            child_sdk = sdk_reforge.get_sdk()
            payload = child_sdk.instance_hash.encode("utf-8")
            os.write(write_fd, payload)
        finally:
            os.close(write_fd)
            os._exit(0)

    os.close(write_fd)
    try:
        os.waitpid(pid, 0)
        child_hash = _read_exact(read_fd, len(parent_hash)).decode("utf-8")
        assert child_hash
        assert child_hash != parent_hash
    finally:
        os.close(read_fd)
        sdk_reforge.reset_instance()
