"""
MCP Tool definitions for Android Shell Manager.
CONSOLIDATED VERSION: 9 tools

Based on MCP best practices:
- "More tools don't always lead to better outcomes"
- "Tools can consolidate functionality, handling multiple discrete operations in a single tool call"

Analytics: Data collected to ~/.android-shell-mcp/analytics.jsonl
           Read via separate NoSQL MCP server (internal dev use only)

TEAM_011: Added CLI detection to suggest project-specific tools over raw commands.
"""
import os
from mcp.server.fastmcp import FastMCP
from core.manager import ShellManager
from utils import analytics

# Global shell manager instance
_manager = ShellManager()

# TEAM_011: Known project CLIs to detect and suggest
# Format: (marker_file, cli_path_pattern, suggested_commands)
KNOWN_PROJECT_CLIS = [
    # Sovereign VM project
    ("cmd/sovereign/main.go", "go run ./cmd/sovereign", [
        "build --sql    # Build VM (Docker + rootfs)",
        "deploy --sql   # Push files to device", 
        "start --sql    # Start VM with gvproxy",
        "test --sql     # Verify connectivity",
    ]),
    # Add more project CLIs here as needed
]


def _detect_project_cli() -> str:
    """
    TEAM_011: Detect if current working context has a known project CLI.
    Returns suggestion string if found, empty string otherwise.
    """
    # Check common project locations
    project_paths = [
        os.path.expanduser("~/Projects/android/kernel/sovereign"),
        os.path.expanduser("~/sovereign"),
        "/home/vince/Projects/android/kernel/sovereign",
    ]
    
    for project_path in project_paths:
        for marker_file, cli_cmd, commands in KNOWN_PROJECT_CLIS:
            marker_path = os.path.join(project_path, marker_file)
            if os.path.exists(marker_path):
                suggestion = [
                    "",
                    "=" * 60,
                    "PROJECT CLI DETECTED: sovereign",
                    f"Location: {project_path}",
                    "",
                    "Consider using the CLI instead of raw adb commands:",
                    f"  cd {project_path}",
                ]
                for cmd in commands:
                    suggestion.append(f"  {cli_cmd} {cmd}")
                suggestion.append("")
                suggestion.append("Use MCP tools for: debugging, logs, interactive troubleshooting")
                suggestion.append("=" * 60)
                return "\n".join(suggestion)
    
    return ""


def _filter_output(result: str, max_lines: int = None, output_mode: str = "tail", grep: str = None) -> str:
    """Filter and limit output to protect LLM context window."""
    if not max_lines and not grep:
        return result
    
    lines = result.split('\n')
    header_lines = []
    output_lines = []
    in_output = False
    
    for line in lines:
        if line.startswith("OUTPUT:"):
            in_output = True
            header_lines.append(line)
        elif in_output:
            output_lines.append(line)
        else:
            header_lines.append(line)
    
    original_count = len(output_lines)
    
    if grep:
        output_lines = [l for l in output_lines if grep in l]
    
    truncated = False
    if max_lines and len(output_lines) > max_lines:
        truncated = True
        if output_mode == "head":
            output_lines = output_lines[:max_lines]
        else:
            output_lines = output_lines[-max_lines:]
    
    if truncated or grep:
        truncate_info = []
        if grep:
            truncate_info.append(f"GREP: '{grep}' ({len(output_lines)} matches)")
        if truncated:
            truncate_info.append(f"TRUNCATED: {len(output_lines)}/{original_count} lines ({output_mode})")
        header_lines.insert(-1, '\n'.join(truncate_info))
    
    return '\n'.join(header_lines + output_lines)


def _filter_batch_output(result: str, max_lines: int = 50, grep: str = None) -> str:
    """Filter each command's output in a batch result."""
    if not max_lines and not grep:
        return result
    
    lines = result.split('\n')
    filtered_lines = []
    current_section = []
    in_section = False
    
    for line in lines:
        if line.startswith('[') and ('] SUCCESS' in line or '] FAILED' in line or '] SKIPPED' in line):
            if current_section:
                filtered_lines.extend(_truncate_section(current_section, max_lines, grep))
            current_section = [line]
            in_section = True
        elif in_section:
            current_section.append(line)
        else:
            filtered_lines.append(line)
    
    if current_section:
        filtered_lines.extend(_truncate_section(current_section, max_lines, grep))
    
    return '\n'.join(filtered_lines)


def _truncate_section(lines: list, max_lines: int, grep: str) -> list:
    """Truncate a single command's output section."""
    if len(lines) <= 1:
        return lines
    
    header = lines[0]
    content = lines[1:]
    
    if grep:
        content = [l for l in content if grep in l]
    
    if max_lines and len(content) > max_lines:
        truncated_count = len(content) - max_lines
        content = content[-max_lines:]
        content.insert(0, f"  ... ({truncated_count} lines truncated)")
    
    return [header] + content


def register_tools(mcp: FastMCP):
    """Register all MCP tools with the server. CONSOLIDATED: 9 tools."""
    
    # ==================== TOOL 1: list_devices ====================
    @mcp.tool()
    def list_devices() -> str:
        """
        List all connected Android devices in ADB and fastboot modes.
        
        Returns:
        - Device serial numbers
        - Mode (adb/fastboot/recovery/sideload/unauthorized/offline)
        - Model name if available
        - Actionable guidance for each state
        - Project CLI suggestions if detected (TEAM_011)
        """
        result = _manager.list_all_devices()
        # TEAM_011: Append CLI suggestions if a known project is detected
        cli_suggestion = _detect_project_cli()
        if cli_suggestion:
            result += cli_suggestion
        return result

    # ==================== TOOL 2: start_shell ====================
    @mcp.tool()
    def start_shell(device_serial: str, shell_type: str = "root") -> str:
        """
        Start a new interactive shell on a specific device.
        
        Args:
            device_serial: Device serial number (from list_devices)
            shell_type: "root" for root shell (su), "non_root" for regular shell
        
        Returns:
        - shell_id: Unique ID to reference this shell in other commands
        - Connection status
        - Device and shell type info
        
        Example:
            start_shell("RFXXXXXX", "root")  -> Creates root shell
            start_shell("RFXXXXXX", "non_root")  -> Creates non-root shell
        """
        return _manager.start_shell(device_serial, shell_type)

    # ==================== TOOL 3: stop_shell ====================
    @mcp.tool()
    def stop_shell(shell_id: str = None) -> str:
        """
        Stop shell(s). Pass shell_id to stop one, or omit to stop ALL shells.
        
        Args:
            shell_id: Specific shell to stop, or None/empty to stop ALL shells
        
        Use for cleanup or when switching tasks.
        """
        if not shell_id or shell_id.lower() == "all":
            return _manager.stop_all()
        return _manager.stop_shell(shell_id)

    # ==================== TOOL 4: shell_status ====================
    @mcp.tool()
    def shell_status(shell_id: str = None) -> str:
        """
        Get shell status. Pass shell_id for one shell, or omit to list ALL shells.
        
        Args:
            shell_id: Specific shell to check, or None to list all shells
        
        Returns:
        - For specific shell: connection status, responsiveness, idle time
        - For all: list of shells with state (ACTIVE/STALE/DISCONNECTED)
        
        If a shell seems stuck, use shell_interact() to diagnose/recover.
        """
        if not shell_id:
            return _manager.list_shells()
        return _manager.get_shell_status(shell_id)

    # ==================== TOOL 5: run_command ====================
    @mcp.tool()
    def run_command(
        shell_id: str, 
        command: str, 
        timeout_seconds: int = 30, 
        working_directory: str = None,
        max_lines: int = None,
        grep: str = None
    ) -> str:
        """
        Execute a command in a shell.
        
        Args:
            shell_id: The shell to run in
            command: Shell command to execute
            timeout_seconds: Max wait time (default: 30s)
            working_directory: Optional directory to cd into first
            max_lines: Limit output to N lines (tail). RECOMMENDED for large outputs!
            grep: Filter output to lines containing this string
        
        Returns:
        - STATUS: SUCCESS/COMMAND_FAILED/ERROR/TIMEOUT/UNCERTAIN
        - EXIT_CODE: The command's exit code
        - OUTPUT: Command output (possibly truncated/filtered)
        
        For multiple commands, use run_commands() instead - much more efficient!
        """
        result = _manager.run_in_shell(shell_id, command, timeout_seconds, working_directory)
        filtered = _filter_output(result, max_lines, "tail", grep)
        
        # Analytics: track ergonomics
        analytics.log_event(
            "run_command",
            ok="SUCCESS" in result or "EXIT_CODE: 0" in result,
            uncertain="UNCERTAIN" in result,
            truncated=1 if "TRUNCATED" in filtered else 0
        )
        return filtered

    # ==================== TOOL 6: run_commands ====================
    @mcp.tool()
    def run_commands(
        shell_id: str, 
        commands: list,
        stop_on_error: bool = False,
        max_lines_per_command: int = 50,
        grep: str = None
    ) -> str:
        """
        Run multiple commands in ONE call. THE MOST EFFICIENT WAY!
        
        Args:
            shell_id: The shell to run in
            commands: Array of command strings: ["ls /data", "cat file.txt", "ps aux"]
            stop_on_error: Stop on first failure (default: False)
            max_lines_per_command: Limit output per command (default: 50)
            grep: Filter all outputs to lines containing this string
        
        Returns:
        - Summary: X/Y succeeded, Z failed
        - Results for each command
        
        Example:
            run_commands(shell_id, ["ls /data", "cat /data/file", "echo done"])
        """
        result = _manager.run_commands_batch(shell_id, commands, stop_on_error)
        if max_lines_per_command or grep:
            result = _filter_batch_output(result, max_lines_per_command, grep)
        
        # Analytics: track batch adoption
        analytics.log_event(
            "run_commands",
            ok="succeeded" in result and "0 failed" in result,
            batch_size=len(commands) if isinstance(commands, list) else 1,
            truncated=result.count("truncated")
        )
        return result

    # ==================== TOOL 7: background_job ====================
    @mcp.tool()
    def background_job(action: str, shell_id: str = None, command: str = None, job_id: str = None) -> str:
        """
        Manage background jobs: start, check, or list.
        
        Args:
            action: "start", "check", or "list"
            shell_id: Required for "start" - which shell to run in
            command: Required for "start" - command to run in background
            job_id: Required for "check" - which job to check
        
        Examples:
            background_job("start", shell_id="xxx", command="long_task.sh")
            background_job("check", job_id="job_abc123")
            background_job("list")
        
        Returns job_id on start, status on check, all jobs on list.
        """
        action = action.lower()
        if action == "start":
            if not shell_id or not command:
                return "STATUS: ERROR\nReason: 'start' requires shell_id and command"
            return _manager.run_background(shell_id, command)
        elif action == "check":
            if not job_id:
                return "STATUS: ERROR\nReason: 'check' requires job_id"
            return _manager.check_background_job(job_id)
        elif action == "list":
            return _manager.list_background_jobs()
        else:
            return f"STATUS: ERROR\nReason: Unknown action '{action}'. Use: start, check, list"

    # ==================== TOOL 8: file_transfer ====================
    @mcp.tool()
    def file_transfer(action: str, device_serial: str, remote_path: str, content: str = None, max_size_kb: int = 1024) -> str:
        """
        Transfer files to/from device: pull or push.
        
        ⚠️  LIMITATION: Max ~1MB files. For larger files, use project CLI or adb directly.
        
        Args:
            action: "pull" (read from device) or "push" (write to device)
            device_serial: Device serial number
            remote_path: Full path on device (e.g., "/data/local/tmp/file.txt")
            content: Required for "push" - content to write (text only, ~1MB max)
            max_size_kb: Max file size for pull (default 1MB)
        
        Examples:
            file_transfer("pull", "SERIAL", "/data/local/tmp/log.txt")
            file_transfer("push", "SERIAL", "/data/local/tmp/config.txt", content="key=value")
        
        For large files (rootfs, images, etc.):
            - Use project CLI if available (e.g., `sovereign deploy`)
            - Or use: adb push <local> <remote>
        """
        action = action.lower()
        if action == "pull":
            return _manager.pull_file(device_serial, remote_path, max_size_kb)
        elif action == "push":
            if content is None:
                return "STATUS: ERROR\nReason: 'push' requires content"
            # TEAM_011: Warn about size limits
            content_size_kb = len(content.encode('utf-8')) / 1024
            if content_size_kb > 1024:
                return (
                    f"STATUS: ERROR\n"
                    f"Reason: Content too large ({content_size_kb:.1f}KB > 1MB limit)\n"
                    f"\n"
                    f"For large files, use:\n"
                    f"  - Project CLI: sovereign deploy (if available)\n"
                    f"  - Direct ADB: adb push <local_file> {remote_path}\n"
                )
            return _manager.push_file(device_serial, remote_path, content)
        else:
            return f"STATUS: ERROR\nReason: Unknown action '{action}'. Use: pull, push"

    # ==================== TOOL 9: shell_interact ====================
    @mcp.tool()
    def shell_interact(action: str, shell_id: str, text: str = None, char: str = None) -> str:
        """
        Interact with a shell: peek at output, send input, or send control chars.
        
        Use this when a command returns UNCERTAIN or you need to respond to prompts.
        
        Args:
            action: "peek", "input", "control", or "diagnose"
            shell_id: The shell to interact with
            text: For "input" - text to send (press Enter after)
            char: For "control" - character to send ('c'=Ctrl+C, 'd'=Ctrl+D, 'z'=Ctrl+Z)
        
        Examples:
            shell_interact("peek", shell_id)              # See what's happening
            shell_interact("input", shell_id, text="y")   # Answer y/n prompt
            shell_interact("control", shell_id, char="c") # Send Ctrl+C to cancel
            shell_interact("diagnose", shell_id)          # Full diagnosis
        
        Returns current output for peek, confirmation for input/control, full diagnosis for diagnose.
        """
        action = action.lower()
        
        if action == "peek":
            return _manager.peek_shell_output(shell_id)
        
        elif action == "input":
            if text is None:
                return "STATUS: ERROR\nReason: 'input' requires text"
            return _manager.send_to_shell(shell_id, text, press_enter=True)
        
        elif action == "control":
            if not char:
                return "STATUS: ERROR\nReason: 'control' requires char ('c', 'd', or 'z')"
            return _manager.send_control_to_shell(shell_id, char)
        
        elif action == "diagnose":
            # Combined diagnosis
            status = _manager.get_shell_status(shell_id)
            if "STATUS: ERROR" in status:
                return status
            
            peek = _manager.peek_shell_output(shell_id)
            
            diagnosis = [
                "=== SHELL DIAGNOSIS ===",
                "",
                status,
                "",
                "CURRENT OUTPUT:",
                peek,
                "",
                "SUGGESTED ACTIONS:",
            ]
            
            if "Responsive: False" in status:
                diagnosis.append("• Shell not responsive. Try: shell_interact('control', shell_id, char='c')")
            elif "(no new output" in peek:
                diagnosis.append("• No pending output. Shell may be idle or waiting.")
            elif any(p in peek.lower() for p in ['[y/n]', 'password', 'continue?']):
                diagnosis.append("• PROMPT DETECTED! Use: shell_interact('input', shell_id, text='your_answer')")
            
            return '\n'.join(diagnosis)
        
        else:
            return f"STATUS: ERROR\nReason: Unknown action '{action}'. Use: peek, input, control, diagnose"

    # NOTE: Analytics data is collected but NOT exposed here.
    # Read analytics via separate NoSQL MCP server (internal dev use only)
    # Data location: ~/.android-shell-mcp/analytics.jsonl
