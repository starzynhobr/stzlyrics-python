from __future__ import annotations

import subprocess
import sys
import time
import uuid

import pytest

from app.single_instance import acquire_single_instance


@pytest.mark.skipif(sys.platform != "win32", reason="Windows named mutex")
def test_only_one_process_can_hold_instance(tmp_path) -> None:
    name = f"Local\\STZLabs.STZLyricsOverlay.Test.{uuid.uuid4()}"
    ready = tmp_path / "ready"
    holder_code = (
        "import sys, time; "
        "from pathlib import Path; "
        "from app.single_instance import acquire_single_instance; "
        "guard = acquire_single_instance(sys.argv[1]); "
        "assert guard is not None; "
        "Path(sys.argv[2]).write_text('ready'); "
        "time.sleep(30)"
    )
    holder = subprocess.Popen([sys.executable, "-c", holder_code, name, str(ready)])
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and holder.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists() and holder.poll() is None

        assert acquire_single_instance(name) is None
    finally:
        holder.terminate()
        holder.wait(timeout=5)

    deadline = time.monotonic() + 5
    guard = acquire_single_instance(name)
    while guard is None and time.monotonic() < deadline:
        time.sleep(0.05)
        guard = acquire_single_instance(name)
    assert guard is not None
    guard.close()
