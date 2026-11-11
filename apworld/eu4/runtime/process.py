"""Detect a running EU4 process from the OS process list (no memory access)."""
from __future__ import annotations

import os
import subprocess

CREATE_NO_WINDOW = 0x08000000


def eu4_running() -> bool:
    """True if eu4.exe (Windows) or eu4 (Linux/macOS) is running.

    On failure to list processes, report "running": the inbox is then never
    rewritten under a live game, which is the safe direction.
    """
    try:
        if os.name == "nt":
            result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq eu4.exe", "/NH", "/FO", "CSV"],
                                    capture_output=True, text=True, timeout=10, check=False,
                                    creationflags=CREATE_NO_WINDOW)
            return result.returncode != 0 or '"eu4.exe"' in result.stdout.lower()
        result = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True,
                                timeout=10, check=False)
        return result.returncode != 0 or any(
            os.path.basename(line.strip()) in ("eu4", "eu4.exe") for line in result.stdout.splitlines())
    except (OSError, subprocess.SubprocessError):
        return True
