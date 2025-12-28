"""
ShellManager class for managing multiple shells across multiple devices.
"""
import subprocess
import time
import uuid
import threading
from typing import Dict, List

from .models import ShellType, DeviceMode, DeviceInfo, BackgroundJob
from .shell import Shell
from .config import ADB_BINARY, FASTBOOT_BINARY


class ShellManager:
    """
    Manages multiple shells across multiple devices.
    """
    
    def __init__(self):
        self._shells: Dict[str, Shell] = {}
        self._background_jobs: Dict[str, BackgroundJob] = {}
        self._lock = threading.Lock()
    
    def _generate_shell_id(self, device_serial: str, shell_type: ShellType) -> str:
        """Generate unique shell ID."""
        short_serial = device_serial[:8] if len(device_serial) > 8 else device_serial
        type_suffix = "root" if shell_type == ShellType.ROOT else "user"
        return f"{short_serial}_{type_suffix}_{uuid.uuid4().hex[:4]}"
    
    def list_all_devices(self) -> str:
        """List all devices in ADB and fastboot modes."""
        devices: List[DeviceInfo] = []
        
        # Get ADB devices
        try:
            result = subprocess.run(
                [ADB_BINARY, "devices", "-l"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.strip().split('\n')[1:]:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    serial = parts[0]
                    state = parts[1]
                    
                    mode = DeviceMode.UNKNOWN
                    if state == "device":
                        mode = DeviceMode.ADB
                    elif state == "unauthorized":
                        mode = DeviceMode.UNAUTHORIZED
                    elif state == "offline":
                        mode = DeviceMode.OFFLINE
                    elif state == "recovery":
                        mode = DeviceMode.RECOVERY
                    elif state == "sideload":
                        mode = DeviceMode.SIDELOAD
                    
                    info = DeviceInfo(serial=serial, mode=mode)
                    
                    # Parse additional info
                    for part in parts[2:]:
                        if ':' in part:
                            key, val = part.split(':', 1)
                            if key == "product":
                                info.product = val
                            elif key == "model":
                                info.model = val
                            elif key == "device":
                                info.device = val
                            elif key == "transport_id":
                                info.transport_id = val
                    
                    devices.append(info)
        except Exception:
            pass
        
        # Get fastboot devices
        try:
            result = subprocess.run(
                [FASTBOOT_BINARY, "devices", "-l"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "fastboot":
                    serial = parts[0]
                    if not any(d.serial == serial for d in devices):
                        info = DeviceInfo(serial=serial, mode=DeviceMode.FASTBOOT)
                        devices.append(info)
        except Exception:
            pass
        
        if not devices:
            return "STATUS: NO_DEVICES\nNo devices found in ADB or fastboot mode.\nAction: Connect device and enable USB debugging, or boot to bootloader for fastboot."
        
        lines = [f"STATUS: FOUND_{len(devices)}_DEVICE(S)", ""]
        for d in devices:
            status_str = f"  {d.serial}: {d.mode.value.upper()}"
            if d.model:
                status_str += f" ({d.model})"
            if d.mode == DeviceMode.UNAUTHORIZED:
                status_str += " - Accept USB debugging prompt on device"
            elif d.mode == DeviceMode.OFFLINE:
                status_str += " - Reconnect device"
            lines.append(status_str)
        
        return '\n'.join(lines)
    
    def start_shell(self, device_serial: str, shell_type: str = "root") -> str:
        """Start a new shell on specified device. Returns shell_id on success."""
        # Validate shell type
        try:
            stype = ShellType.ROOT if shell_type.lower() == "root" else ShellType.NON_ROOT
        except:
            stype = ShellType.ROOT
        
        # Verify device exists
        try:
            result = subprocess.run(
                [ADB_BINARY, "-s", device_serial, "get-state"],
                capture_output=True, text=True, timeout=5
            )
            state = result.stdout.strip()
            if state != "device":
                return f"STATUS: ERROR\nDevice: {device_serial}\nReason: Device state is '{state}', not 'device'.\nAction: Ensure device is connected and authorized."
        except subprocess.TimeoutExpired:
            return f"STATUS: ERROR\nDevice: {device_serial}\nReason: Timeout checking device state.\nAction: Check USB connection."
        except Exception as e:
            return f"STATUS: ERROR\nDevice: {device_serial}\nReason: {str(e)}"
        
        # Create and connect shell
        shell_id = self._generate_shell_id(device_serial, stype)
        shell = Shell(shell_id, device_serial, stype)
        
        connect_result = shell.connect()
        
        if "STATUS: CONNECTED" in connect_result or "STATUS: ALREADY_CONNECTED" in connect_result:
            with self._lock:
                self._shells[shell_id] = shell
            return connect_result
        else:
            return connect_result
    
    def stop_shell(self, shell_id: str) -> str:
        """Stop and remove a shell."""
        with self._lock:
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not found.\nAction: Use list_shells to see active shells."
            
            shell = self._shells.pop(shell_id)
            return shell.disconnect()
    
    def run_in_shell(self, shell_id: str, command: str, timeout_seconds: int = 30, working_directory: str = None) -> str:
        """Run command in specific shell, optionally in a specific directory."""
        with self._lock:
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not found.\nAction: Use list_shells to see active shells, or start_shell to create one."
            shell = self._shells[shell_id]
        
        # TEAM_008: Support working directory
        if working_directory:
            command = f"cd {working_directory} && {command}"
        
        return shell.run_command(command, timeout_seconds)
    
    def run_commands_batch(self, shell_id: str, commands: list, stop_on_error: bool = False) -> str:
        """
        TEAM_008: Run multiple commands in sequence, returning all results.
        
        Args:
            shell_id: Shell to run commands in
            commands: List of command dicts with keys:
                - command: str (required)
                - id: str (optional, for identifying results)
                - timeout_seconds: int (optional, default 30)
                - working_directory: str (optional)
            stop_on_error: If True, stop on first command failure
        
        Returns structured results for all commands.
        """
        with self._lock:
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not found."
            shell = self._shells[shell_id]
        
        if not shell.is_alive():
            return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not connected."
        
        results = []
        total = len(commands)
        succeeded = 0
        failed = 0
        
        for i, cmd_spec in enumerate(commands):
            # Parse command spec
            if isinstance(cmd_spec, str):
                cmd = cmd_spec
                cmd_id = f"cmd_{i}"
                timeout = 30
                cwd = None
            else:
                cmd = cmd_spec.get("command", "")
                cmd_id = cmd_spec.get("id", f"cmd_{i}")
                timeout = cmd_spec.get("timeout_seconds", 30)
                cwd = cmd_spec.get("working_directory")
            
            if not cmd:
                results.append(f"[{cmd_id}] SKIPPED: Empty command")
                continue
            
            # Run the command
            actual_cmd = f"cd {cwd} && {cmd}" if cwd else cmd
            result = shell.run_command(actual_cmd, timeout)
            
            # Parse result
            is_success = "STATUS: SUCCESS" in result or "EXIT_CODE: 0" in result
            if is_success:
                succeeded += 1
            else:
                failed += 1
            
            # Extract just the output part for cleaner results
            output_lines = []
            in_output = False
            for line in result.split('\n'):
                if line.startswith("OUTPUT:"):
                    in_output = True
                    continue
                if in_output:
                    output_lines.append(line)
            
            clean_output = '\n'.join(output_lines).strip() if output_lines else "(no output)"
            
            # Build result entry
            status = "SUCCESS" if is_success else "FAILED"
            results.append(f"[{cmd_id}] {status}\n{clean_output}")
            
            # Stop on error if requested
            if stop_on_error and not is_success:
                results.append(f"\n--- STOPPED: Command '{cmd_id}' failed and stop_on_error=True ---")
                break
        
        # Build final response
        header = f"BATCH RESULTS: {succeeded}/{total} succeeded, {failed} failed\n"
        header += "=" * 50
        
        return header + "\n\n" + "\n\n".join(results)
    
    def pull_file(self, device_serial: str, remote_path: str, max_size_kb: int = 1024) -> str:
        """
        TEAM_008: Pull file contents from device.
        
        Args:
            device_serial: Device to pull from
            remote_path: Path on device
            max_size_kb: Max file size to pull (default 1MB)
        
        Returns file contents or error.
        """
        try:
            # Check file size first
            size_result = subprocess.run(
                [ADB_BINARY, "-s", device_serial, "shell", f"stat -c%s '{remote_path}' 2>/dev/null || echo 'NOT_FOUND'"],
                capture_output=True, text=True, timeout=10
            )
            size_str = size_result.stdout.strip()
            
            if size_str == "NOT_FOUND" or not size_str:
                return f"STATUS: ERROR\nFile: {remote_path}\nReason: File not found on device."
            
            try:
                size_bytes = int(size_str)
                if size_bytes > max_size_kb * 1024:
                    return f"STATUS: ERROR\nFile: {remote_path}\nSize: {size_bytes} bytes\nReason: File exceeds max size ({max_size_kb}KB). Use adb pull directly for large files."
            except ValueError:
                pass  # Continue anyway
            
            # Pull the file content
            result = subprocess.run(
                [ADB_BINARY, "-s", device_serial, "shell", f"cat '{remote_path}'"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                return f"STATUS: ERROR\nFile: {remote_path}\nReason: {result.stderr.strip() or 'Failed to read file'}"
            
            content = result.stdout
            return f"STATUS: SUCCESS\nFile: {remote_path}\nSize: {len(content)} bytes\nCONTENT:\n{content}"
            
        except subprocess.TimeoutExpired:
            return f"STATUS: ERROR\nFile: {remote_path}\nReason: Timeout reading file."
        except Exception as e:
            return f"STATUS: ERROR\nFile: {remote_path}\nReason: {str(e)}"
    
    def push_file(self, device_serial: str, remote_path: str, content: str) -> str:
        """
        TEAM_008: Push file contents to device.
        
        Args:
            device_serial: Device to push to
            remote_path: Path on device
            content: File contents to write
        
        Returns success/error status.
        """
        try:
            # Use echo with base64 for reliable transfer
            import base64
            encoded = base64.b64encode(content.encode()).decode()
            
            # Write via base64 decode on device
            result = subprocess.run(
                [ADB_BINARY, "-s", device_serial, "shell", 
                 f"echo '{encoded}' | base64 -d > '{remote_path}'"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                return f"STATUS: ERROR\nFile: {remote_path}\nReason: {result.stderr.strip() or 'Failed to write file'}"
            
            # Verify write
            verify = subprocess.run(
                [ADB_BINARY, "-s", device_serial, "shell", f"stat -c%s '{remote_path}'"],
                capture_output=True, text=True, timeout=10
            )
            
            return f"STATUS: SUCCESS\nFile: {remote_path}\nWritten: {len(content)} bytes"
            
        except subprocess.TimeoutExpired:
            return f"STATUS: ERROR\nFile: {remote_path}\nReason: Timeout writing file."
        except Exception as e:
            return f"STATUS: ERROR\nFile: {remote_path}\nReason: {str(e)}"
    
    def run_background(self, shell_id: str, command: str) -> str:
        """Start a command in background, return job_id."""
        with self._lock:
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not found."
            shell = self._shells[shell_id]
        
        if not shell.is_alive():
            return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not connected."
        
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        
        # Run command with nohup and redirect to temp file
        bg_command = f"nohup {command} > /data/local/tmp/{job_id}.out 2>&1 & echo $!"
        result = shell.run_command(bg_command, timeout_seconds=10)
        
        if "STATUS: SUCCESS" in result or "STATUS: COMPLETED" in result:
            # Extract PID from output
            lines = result.split('\n')
            pid = None
            for line in lines:
                if line.strip().isdigit():
                    pid = line.strip()
                    break
            
            job = BackgroundJob(
                job_id=job_id,
                command=command,
                shell_id=shell_id,
                start_time=time.time()
            )
            
            with self._lock:
                self._background_jobs[job_id] = job
            
            return f"STATUS: STARTED\nJob: {job_id}\nShell: {shell_id}\nPID: {pid or 'unknown'}\nCommand: {command[:100]}\nOutput file: /data/local/tmp/{job_id}.out"
        else:
            return f"STATUS: ERROR\nReason: Failed to start background job.\nDetails: {result}"
    
    def check_background_job(self, job_id: str) -> str:
        """Check status of background job."""
        with self._lock:
            if job_id not in self._background_jobs:
                return f"STATUS: ERROR\nJob: {job_id}\nReason: Job not found."
            job = self._background_jobs[job_id]
            shell_id = job.shell_id
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nJob: {job_id}\nReason: Shell {shell_id} no longer exists."
            shell = self._shells[shell_id]
        
        # Check if output file exists and get contents
        result = shell.run_command(f"cat /data/local/tmp/{job_id}.out 2>/dev/null || echo '(no output yet)'", timeout_seconds=10)
        
        # Check if process is still running
        check_result = shell.run_command(f"ps | grep -v grep | grep {job_id} || echo 'COMPLETED'", timeout_seconds=5)
        
        is_running = "COMPLETED" not in check_result
        
        return f"STATUS: {'RUNNING' if is_running else 'COMPLETED'}\nJob: {job_id}\nCommand: {job.command[:100]}\nStarted: {time.time() - job.start_time:.1f}s ago\n{result}"
    
    def get_shell_status(self, shell_id: str) -> str:
        """Get detailed status of a specific shell."""
        with self._lock:
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not found."
            shell = self._shells[shell_id]
        
        status = shell.get_status()
        idle_str = f"\nIdle: {status['idle_seconds']:.1f}s" if status['idle_seconds'] else ""
        return f"STATUS: INFO\nShell: {shell_id}\nDevice: {status['device']}\nType: {status['type']}\nConnected: {status['connected']}\nResponsive: {status['responsive']}{idle_str}"
    
    def peek_shell_output(self, shell_id: str) -> str:
        """Peek at current output in a shell without blocking."""
        with self._lock:
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not found."
            shell = self._shells[shell_id]
        
        output = shell.peek_output()
        return f"SHELL: {shell_id}\nPEEKED_OUTPUT:\n{output}"
    
    def send_to_shell(self, shell_id: str, text: str, press_enter: bool = True) -> str:
        """Send input text to a shell."""
        with self._lock:
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not found."
            shell = self._shells[shell_id]
        
        return shell.send_input(text, press_enter)
    
    def send_control_to_shell(self, shell_id: str, char: str) -> str:
        """Send control character to a shell (e.g., 'c' for Ctrl+C)."""
        with self._lock:
            if shell_id not in self._shells:
                return f"STATUS: ERROR\nShell: {shell_id}\nReason: Shell not found."
            shell = self._shells[shell_id]
        
        return shell.send_control(char)
    
    def list_shells(self) -> str:
        """List all active shells."""
        with self._lock:
            if not self._shells:
                return "STATUS: NO_SHELLS\nNo active shells.\nAction: Use start_shell to create a shell."
            
            lines = [f"STATUS: FOUND_{len(self._shells)}_SHELL(S)", ""]
            for shell_id, shell in self._shells.items():
                status = shell.get_status()
                state = "ACTIVE" if status['connected'] and status['responsive'] else "DISCONNECTED" if not status['connected'] else "STALE"
                lines.append(f"  {shell_id}: {status['device']} ({status['type']}) - {state}")
            
            return '\n'.join(lines)
    
    def list_background_jobs(self) -> str:
        """List all background jobs."""
        with self._lock:
            if not self._background_jobs:
                return "STATUS: NO_JOBS\nNo background jobs."
            
            lines = [f"STATUS: FOUND_{len(self._background_jobs)}_JOB(S)", ""]
            for job_id, job in self._background_jobs.items():
                age = time.time() - job.start_time
                lines.append(f"  {job_id}: {job.command[:50]}... ({age:.1f}s ago)")
            
            return '\n'.join(lines)
    
    def stop_all(self) -> str:
        """Stop all shells and clean up."""
        with self._lock:
            count = len(self._shells)
            for shell in self._shells.values():
                shell.disconnect()
            self._shells.clear()
            self._background_jobs.clear()
        return f"STATUS: STOPPED\nClosed {count} shell(s)."
