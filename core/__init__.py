"""
Core module for Android Shell Manager.
Contains models, configuration, shell, and manager classes.
"""
from .models import ShellType, DeviceMode, DeviceInfo, BackgroundJob
from .config import (
    ADB_BINARY, FASTBOOT_BINARY, MARKER_PREFIX,
    SHELL_PROMPT_PATTERNS, INTERACTIVE_PROMPT_PATTERNS,
    DANGEROUS_COMMANDS, SLOW_SILENT_COMMANDS, SLOW_COMMAND_PATTERNS,
    PROGRESS_CHECK_INTERVAL, STUCK_THRESHOLD_INTERVALS,
    SLOW_COMMAND_TIMEOUT_MULTIPLIER, MIN_TIME_BEFORE_STUCK_CHECK
)
from .shell import Shell
from .manager import ShellManager

__all__ = [
    # Models
    "ShellType",
    "DeviceMode",
    "DeviceInfo",
    "BackgroundJob",
    # Config
    "ADB_BINARY",
    "FASTBOOT_BINARY",
    "MARKER_PREFIX",
    "SHELL_PROMPT_PATTERNS",
    "INTERACTIVE_PROMPT_PATTERNS",
    "DANGEROUS_COMMANDS",
    "SLOW_SILENT_COMMANDS",
    "SLOW_COMMAND_PATTERNS",
    "PROGRESS_CHECK_INTERVAL",
    "STUCK_THRESHOLD_INTERVALS",
    "SLOW_COMMAND_TIMEOUT_MULTIPLIER",
    "MIN_TIME_BEFORE_STUCK_CHECK",
    # Classes
    "Shell",
    "ShellManager",
]
