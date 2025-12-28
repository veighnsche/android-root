"""
Data models and enums for Android Shell Manager.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import threading


class ShellType(Enum):
    NON_ROOT = "non_root"
    ROOT = "root"


class DeviceMode(Enum):
    ADB = "adb"
    FASTBOOT = "fastboot"
    RECOVERY = "recovery"
    SIDELOAD = "sideload"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


@dataclass
class DeviceInfo:
    """Information about a connected Android device."""
    serial: str
    mode: DeviceMode
    product: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None
    transport_id: Optional[str] = None


@dataclass
class BackgroundJob:
    """Tracks a background job running on a device."""
    job_id: str
    command: str
    shell_id: str
    start_time: float
    output_buffer: List[str] = field(default_factory=list)
    is_running: bool = True
    exit_code: Optional[int] = None
    thread: Optional[threading.Thread] = None
