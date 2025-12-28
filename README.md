# Android Shell Manager - MCP Server

A Model Context Protocol (MCP) server for managing multiple interactive Android shells across multiple devices. Designed specifically for **AI agent interaction** with robust hang detection and AI-driven decision making.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Key Features

- **Multi-device support** - Manage shells on multiple ADB/fastboot devices simultaneously
- **Root & non-root shells** - Persistent interactive sessions with `su` escalation
- **AI-centric design** - Returns `STATUS: UNCERTAIN` for ambiguous situations, letting the AI decide
- **Hang prevention** - Smart detection with false-positive protection for slow commands
- **Background jobs** - Run long commands without blocking
- **9 consolidated tools** - Optimized for LLM context efficiency
- **Batch command execution** - Run multiple commands in a single call

---

## Installation

### Prerequisites

1. **Install `uv`** (recommended Python package manager):
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Install Python 3.10+**:
   ```bash
   uv python install 3.10
   ```

3. **Android SDK Platform Tools** (`adb` and `fastboot` in PATH):
   ```bash
   # Verify installation
   adb --version
   fastboot --version
   ```

### Quick Install

```bash
cd android-root
uv sync  # or: pip install -r requirements.txt
```

---

## MCP Client Configuration

Add this server to your MCP client configuration. The JSON format is the same across all clients.

### Claude Desktop

**Config file location:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "android-shell": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/android-root",
        "python",
        "server.py"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

### Windsurf

**Config file:** `~/.codeium/windsurf/mcp_config.json`

Or navigate to: **Windsurf Settings → Advanced Settings → MCP Servers → Add custom server**

```json
{
  "mcpServers": {
    "android-shell": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/android-root",
        "python",
        "server.py"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

### Cursor

**Config file locations:**
- **Global** (all projects): `~/.cursor/mcp.json`
- **Project-specific**: `.cursor/mcp.json` in your project root

```json
{
  "mcpServers": {
    "android-shell": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/android-root",
        "python",
        "server.py"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

### VS Code (with GitHub Copilot)

**Config file:** `.vscode/mcp.json` in your workspace

```json
{
  "mcpServers": {
    "android-shell": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/android-root",
        "python",
        "server.py"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

### Alternative: Using `uvx` (if published to PyPI)

If you publish this package to PyPI, users can use `uvx` for automatic installation:

```json
{
  "mcpServers": {
    "android-shell": {
      "command": "uvx",
      "args": ["android-shell-mcp@latest"],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

### Alternative: Using `pip` + `python`

```json
{
  "mcpServers": {
    "android-shell": {
      "command": "python",
      "args": ["/path/to/android-root/server.py"],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    }
  }
}
```

> **Note:** After adding the configuration, restart your MCP client (Claude Desktop, Windsurf, Cursor, etc.) for changes to take effect.

---

## Verify Installation

After configuration, test that the server is working:

1. **In Claude/Cursor/Windsurf**: Ask the AI to run `list_devices()`
2. **Manual test**:
   ```bash
   cd android-root
   uv run python server.py
   # Server should start without errors
   ```

## Quick Start

```python
# 1. List connected devices
list_devices()

# 2. Start a root shell on a device
start_shell("DEVICE_SERIAL", "root")  # Returns shell_id

# 3. Run a single command
run_command(shell_id, "ls /data")

# 4. Run multiple commands efficiently (RECOMMENDED)
run_commands(shell_id, ["ls /data", "whoami", "cat /proc/version"])

# 5. Clean up
stop_shell()  # Stop all shells
```

---

## MCP Tools Reference (9 Tools)

This server provides **9 consolidated tools** optimized for LLM context efficiency.

### Tool 1: `list_devices`

List all connected Android devices in ADB and fastboot modes.

```python
list_devices()
# Returns: Device serials, modes (adb/fastboot/recovery), model names
```

### Tool 2: `start_shell`

Start a new interactive shell on a specific device.

```python
start_shell(device_serial, shell_type="root")
# shell_type: "root" or "non_root"
# Returns: shell_id for use in other commands
```

### Tool 3: `stop_shell`

Stop shell(s). Pass `shell_id` to stop one, or omit to stop ALL shells.

```python
stop_shell(shell_id)      # Stop specific shell
stop_shell()              # Stop ALL shells (cleanup)
```

### Tool 4: `shell_status`

Get shell status. Pass `shell_id` for one shell, or omit to list all.

```python
shell_status(shell_id)    # Detailed status for one shell
shell_status()            # List all active shells
```

### Tool 5: `run_command`

Execute a single command in a shell.

```python
run_command(
    shell_id,
    command,
    timeout_seconds=30,
    working_directory=None,
    max_lines=None,          # Limit output (protects context window!)
    grep=None                # Filter output to matching lines
)
```

### Tool 6: `run_commands` ⭐ MOST EFFICIENT

Run multiple commands in ONE call. **Use this for batch operations!**

```python
run_commands(
    shell_id,
    commands=["ls /data", "cat file.txt", "ps aux"],
    stop_on_error=False,
    max_lines_per_command=50,
    grep=None
)
# Returns: Summary (X/Y succeeded) + results for each command
```

### Tool 7: `background_job`

Manage background jobs: start, check, or list.

```python
background_job("start", shell_id=id, command="long_task.sh")  # Returns job_id
background_job("check", job_id=job_id)                         # Check status
background_job("list")                                         # List all jobs
```

### Tool 8: `file_transfer`

Transfer files to/from device.

```python
file_transfer("pull", device_serial, "/data/local/tmp/log.txt")
file_transfer("push", device_serial, "/data/local/tmp/config.txt", content="key=value")
```

### Tool 9: `shell_interact`

Interact with a shell: peek at output, send input, or send control characters.

```python
shell_interact("peek", shell_id)                    # See current output
shell_interact("input", shell_id, text="y")         # Answer prompt
shell_interact("control", shell_id, char="c")       # Send Ctrl+C
shell_interact("diagnose", shell_id)                # Full diagnosis
```

---

## Status Types

The server returns structured status messages:

| Status | Meaning | AI Action |
|--------|---------|-----------|
| `SUCCESS` | Command completed successfully | Continue |
| `COMMAND_FAILED` | Command ran but returned non-zero | Check output |
| `TIMEOUT` | Hard timeout reached | Increase timeout or investigate |
| `WAITING_FOR_INPUT` | Detected interactive prompt | Use `send_input()` to respond |
| `UNCERTAIN` | **Ambiguous situation** | Use inspection tools to decide |
| `ERROR` | Something went wrong | Read error message |

### The UNCERTAIN Status

This is the **AI-centric** approach. When the server can't deterministically decide if a command is stuck, it returns:

```
STATUS: UNCERTAIN
Shell: abc123_root_xxxx
Command: some_command
Elapsed: 8.5s
No output for: 6.2s

The command has produced no output recently. This could mean:
1. It's working on something slow (downloading, processing)
2. It's waiting for input that wasn't detected
3. It's genuinely stuck

WHAT YOU (the AI) SHOULD DO:
• Use peek_output('abc123_root_xxxx') to check for new output
• Use diagnose_shell('abc123_root_xxxx') for detailed analysis
• If you think it's stuck: send_control_char('abc123_root_xxxx', 'c')
• If it needs input: send_input('abc123_root_xxxx', 'your_response')
```

The AI then uses its reasoning to decide the appropriate action.

---

## Hang Prevention

### Automatic Detection

The server automatically detects:
- Interactive prompts (`[y/n]`, `Password:`, etc.)
- Dangerous commands (`vim`, `top`, `cat` without args)
- Stuck processes (no output for extended period)

### False-Positive Protection

Commands known to be slow/silent get special treatment:
- `wget`, `curl`, `rsync` - Network operations
- `cp`, `dd`, `tar` - File operations  
- `find`, `grep` - Search operations
- `make`, `gradle` - Build operations
- Any command with `--quiet`, `-s`, `>/dev/null`

These get **10x longer** tolerance before being flagged.

### Multi-Stage Recovery

When recovery is needed:
1. Ctrl+C (SIGINT)
2. Ctrl+D (EOF)
3. Ctrl+Z + kill (background and terminate)

---

## Architecture

```
android-root/
├── server.py              # MCP entry point
├── __init__.py            # Package exports
├── core/                  # Core business logic
│   ├── __init__.py
│   ├── models.py          # Data classes and enums
│   ├── config.py          # Constants and patterns
│   ├── shell.py           # Shell class - single session management
│   └── manager.py         # ShellManager - multi-device orchestration
├── tools/                 # MCP tools
│   ├── __init__.py
│   └── handlers.py        # MCP tool definitions (9 tools)
├── utils/                 # Utilities
│   ├── __init__.py
│   └── analytics.py       # Usage analytics
├── tests/                 # Tests
│   ├── __init__.py
│   └── test_main.py
├── pyproject.toml
├── requirements.txt
└── uv.lock
```

### Key Classes

- **`Shell`** (`core/shell.py`) - Single interactive pexpect session with hang detection
- **`ShellManager`** (`core/manager.py`) - Manages multiple shells across multiple devices
- **`BackgroundJob`** (`core/models.py`) - Tracks background command execution

---

## Configuration

In `core/config.py`:

```python
# Timing
PROGRESS_CHECK_INTERVAL = 0.5        # How often to check for output
STUCK_THRESHOLD_INTERVALS = 4        # Intervals before considering stuck (2s)
MIN_TIME_BEFORE_STUCK_CHECK = 5.0    # Min elapsed time before stuck check
SLOW_COMMAND_TIMEOUT_MULTIPLIER = 10 # 10x tolerance for slow commands

# Patterns
INTERACTIVE_PROMPT_PATTERNS = [...]  # 18 patterns for detecting prompts
DANGEROUS_COMMANDS = [...]           # Commands that may hang
SLOW_SILENT_COMMANDS = [...]         # Commands that are legitimately slow
```

---

## Example Workflows

### Basic Command Execution

```python
# 1. Check devices
list_devices()
# → STATUS: FOUND_2_DEVICE(S)
#   RFXXXX1234: ADB (SM-G990U)
#   RFXXXX5678: ADB (Pixel_6)

# 2. Start shell
start_shell("RFXXXX1234", "root")
# → STATUS: CONNECTED
#   Shell: RFXXXX12_root_a1b2

# 3. Run single command
run_command("RFXXXX12_root_a1b2", "ls /data/data | head -5")
# → STATUS: SUCCESS
#   EXIT_CODE: 0
#   OUTPUT: ...

# 4. Run multiple commands efficiently
run_commands("RFXXXX12_root_a1b2", [
    "whoami",
    "cat /proc/version",
    "ls /data/app | wc -l"
])
# → 3/3 succeeded, 0 failed
#   [1] SUCCESS: whoami
#   root
#   [2] SUCCESS: cat /proc/version
#   Linux version 5.10...
#   [3] SUCCESS: ls /data/app | wc -l
#   42
```

### Handling Interactive Prompts

```python
# Command asks for confirmation
run_command(shell_id, "rm -i /sdcard/test.txt")
# → STATUS: WAITING_FOR_INPUT
#   Detected: [y/n] prompt

# AI responds using shell_interact
shell_interact("input", shell_id, text="y")
# → STATUS: SENT

# Check result
shell_interact("peek", shell_id)
# → removed '/sdcard/test.txt'
```

### Investigating Uncertain Status

```python
# Long-running command returns uncertain
run_command(shell_id, "find / -name '*.apk'", timeout_seconds=60)
# → STATUS: UNCERTAIN
#   No output for 6.2s

# AI investigates
shell_interact("peek", shell_id)
# → (shows recent find output - still working!)

# Full diagnosis
shell_interact("diagnose", shell_id)
# → SHELL DIAGNOSIS
#   Responsive: True
#   SUGGESTED ACTIONS: ...
```

### File Transfer

```python
# Pull a file from device
file_transfer("pull", "RFXXXX1234", "/data/local/tmp/log.txt")
# → STATUS: SUCCESS
#   CONTENT: <file contents>

# Push content to device
file_transfer("push", "RFXXXX1234", "/data/local/tmp/config.ini", 
              content="[settings]\ndebug=true")
# → STATUS: SUCCESS
```

### Background Jobs

```python
# Start long-running task
background_job("start", shell_id="RFXXXX12_root_a1b2", 
               command="find / -name '*.log' > /tmp/logs.txt")
# → JOB_ID: job_abc123

# Check status later
background_job("check", job_id="job_abc123")
# → STATUS: RUNNING (or COMPLETED)
#   OUTPUT: ...

# List all jobs
background_job("list")
# → 2 background jobs...
```

---

## Gotchas & Notes

### TEAM_001: Root Shell Persistence
- The server maintains **persistent** `su` sessions
- Commands are sent directly to the root shell, NOT wrapped with `adb shell su -c`
- This allows interactive root sessions

### TEAM_001: Prompt Detection
- Android shells have various prompt formats depending on ROM
- Multiple regex patterns are used: `$`, `#`, `user@host:path$`
- If prompt detection fails, try `stop_shell` + `start_shell`

### TEAM_001: Binary Output
- `codec_errors="replace"` is used to handle binary output
- Commands producing binary data won't corrupt the shell

### TEAM_001: Background Jobs
- Output is written to `/data/local/tmp/{job_id}.out`
- Jobs persist even if shell is closed
- Clean up with `rm /data/local/tmp/job_*.out`

---

## Troubleshooting

### Shell Not Responsive

```python
shell_interact("diagnose", shell_id)  # Get full diagnosis
shell_interact("control", shell_id, char="c")  # Try Ctrl+C
# If still stuck:
stop_shell(shell_id)
start_shell(device_serial, "root")
```

### Root Access Denied

Check on the device:
1. Is Magisk/SuperSU installed?
2. Is the app granted root access?
3. Is there a pending "Allow" dialog on screen?

### Device Not Found

```bash
# Check ADB connection
adb devices -l

# Restart ADB if needed
adb kill-server
adb start-server
```

---

## Contributing

1. Follow the existing code style
2. Add team comments: `# TEAM_XXX: description`
3. Update `core/config.py` for new patterns
4. Test with real devices when possible
5. Create team files in `.teams/` for documentation

---

## License

MIT

---

## Links

- **MCP Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io/)
- **uv Package Manager**: [astral.sh/uv](https://astral.sh/uv/)
- **Android Platform Tools**: [developer.android.com](https://developer.android.com/studio/releases/platform-tools)
