"""Paths shared by the offline launcher and the packaged application."""
import os
import sys
from pathlib import Path
from functools import lru_cache
from threading import RLock

APP_NAME = "USECTA Document Generator"
VERSION = "1.0.0"


def asset_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def workspace_root():
    if os.environ.get("USECTA_DATA_DIR"):
        return Path(os.environ["USECTA_DATA_DIR"]).resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / APP_NAME


def offline_mode():
    return (bool(getattr(sys, "frozen", False)) or os.environ.get("USECTA_OFFLINE") == "1"
            or os.environ.get("USECTA_LOCAL_MODE") == "1")


@lru_cache(maxsize=8)
def workspace_lock(root):
    return RLock()
