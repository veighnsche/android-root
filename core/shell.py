"""
Shell class for managing individual interactive shell sessions.
Enhanced with comprehensive hang detection and prevention.
"""
import pexpect
import re
import time
import uuid
import threading
import select
from typing import Optional, Tuple, List

from .models import ShellType
from .config import (
    ADB_BINARY, MARKER_PREFIX, SHELL_PROMPT_PATTERNS,
    INTERACTIVE_PROMPT_PATTERNS, DANGEROUS_COMMANDS,
    PROGRESS_CHECK_INTERVAL, STUCK_THRESHOLD_INTERVALS,
    SLOW_SILENT_COMMANDS, SLOW_COMMAND_PATTERNS,
    SLOW_COMMAND_TIMEOUT_MULTIPLIER, MIN_TIME_BEFORE_STUCK_CHECK
)


class Shell:
    """
    A single interactive shell session on an Android device.
    Can be root or non-root.
    """
    
    def __init__(self, shell_id: str, device_serial: str, shell_type: ShellType):
        self.shell_id = shell_id
        self.device_serial = device_serial
        self.shell_type = shell_type
        self._process: Optional[pexpect.spawn] = None
        self._is_connected: bool = False
        self._last_activity: float = 0
        self._cwd: str = "/"
        self._lock = threading.Lock()
    
    def connect(self) -> str:
        """Establish the shell connection."""
        with self._lock:
            if self._is_connected and self._process and self._process.isalive():
                return f"STATUS: ALREADY_CONNECTED\nShell: {self.shell_id}\nDevice: {self.device_serial}\nType: {self.shell_type.value}"
            
            try:
                # Spawn adb shell for specific device
                self._process = pexpect.spawn(
                    f"{ADB_BINARY} -s {self.device_serial} shell",
                    encoding="utf-8",
                    codec_errors="replace",
                    timeout=30,
                    maxread=65536,
                    searchwindowsize=4096
                )
                
                # Wait for prompt
                try:
                    self._process.expect(SHELL_PROMPT_PATTERNS, timeout=10)
                except pexpect.TIMEOUT:
                    self._process.sendline("")
                    try:
                        self._process.expect(SHELL_PROMPT_PATTERNS, timeout=5)
                    except:
                        self._force_close()
                        return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Could not detect shell prompt.\nAction: Check device {self.device_serial} manually."
                
                # If root shell requested, escalate
                if self.shell_type == ShellType.ROOT:
                    self._process.sendline("su")
                    try:
                        index = self._process.expect([
                            r'#\s*$',
                            r'denied|not allowed',
                            r'not found|No such file',
                            r'waiting|confirm|allow',
                            pexpect.TIMEOUT
                        ], timeout=15)
                        
                        if index == 0:
                            # Verify root
                            self._process.sendline("id")
                            try:
                                self._process.expect(r'uid=0', timeout=5)
                                self._process.expect(SHELL_PROMPT_PATTERNS, timeout=5)
                            except:
                                self._force_close()
                                return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: su succeeded but uid != 0.\nAction: Root may be broken on device."
                        elif index == 1:
                            self._force_close()
                            return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Root access denied.\nAction: Grant root in Magisk/SuperSU on device {self.device_serial}."
                        elif index == 2:
                            self._force_close()
                            return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: su not found.\nAction: Device {self.device_serial} is not rooted."
                        elif index == 3:
                            self._force_close()
                            return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Waiting for root permission.\nAction: Tap ALLOW on device {self.device_serial} screen."
                        else:
                            self._force_close()
                            return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Timeout during su.\nAction: Check device screen for prompts."
                    except pexpect.EOF:
                        self._force_close()
                        return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Shell died during su.\nAction: Device may have disconnected."
                
                self._is_connected = True
                self._last_activity = time.time()
                
                return f"STATUS: CONNECTED\nShell: {self.shell_id}\nDevice: {self.device_serial}\nType: {self.shell_type.value}\nReady for commands."
                
            except pexpect.exceptions.EOF:
                self._force_close()
                return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: ADB connection failed.\nAction: Check device {self.device_serial} is connected."
            except Exception as e:
                self._force_close()
                return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: {str(e)}"
    
    def _force_close(self):
        """Force close without graceful exit."""
        if self._process:
            try:
                self._process.close(force=True)
            except:
                pass
        self._process = None
        self._is_connected = False
    
    def disconnect(self) -> str:
        """Gracefully close the shell."""
        with self._lock:
            if self._process:
                try:
                    if self.shell_type == ShellType.ROOT:
                        self._process.sendline("exit")  # Exit su
                        time.sleep(0.1)
                    self._process.sendline("exit")  # Exit shell
                    time.sleep(0.1)
                    self._process.close()
                except:
                    self._force_close()
            self._process = None
            self._is_connected = False
            return f"STATUS: DISCONNECTED\nShell: {self.shell_id}"
    
    def is_alive(self) -> bool:
        """Check if shell is alive."""
        if not self._is_connected or not self._process:
            return False
        return self._process.isalive()
    
    def verify_responsive(self) -> bool:
        """Verify shell responds to commands."""
        if not self.is_alive():
            return False
        try:
            marker = f"__PING_{uuid.uuid4().hex[:6]}__"
            self._process.sendline(f"echo {marker}")
            index = self._process.expect([marker, pexpect.TIMEOUT, pexpect.EOF], timeout=3)
            return index == 0
        except:
            return False
    
    def _check_dangerous_command(self, command: str) -> Optional[str]:
        """
        Check if command is known to be dangerous (interactive/blocking).
        Returns warning message if dangerous, None if safe.
        """
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return None
        
        base_cmd = cmd_parts[0]
        
        # Check for exact matches of dangerous commands
        for dangerous in DANGEROUS_COMMANDS:
            if base_cmd == dangerous:
                # Some commands are safe with certain args
                if base_cmd in ['cat', 'python', 'python3', 'node'] and len(cmd_parts) > 1:
                    continue  # Has arguments, probably safe
                if base_cmd in ['sh', 'bash', 'zsh'] and '-c' in cmd_parts:
                    continue  # Running with -c, safe
                if base_cmd == 'su' and '-c' in cmd_parts:
                    continue  # su -c is safe
                
                return f"WARNING: '{base_cmd}' is an interactive command that may hang. Consider using alternatives or adding appropriate flags."
        
        return None
    
    def _is_slow_silent_command(self, command: str) -> Tuple[bool, str]:
        """
        Check if command is known to be slow/silent but legitimate.
        These commands should NOT trigger false positive "stuck" detection.
        
        Returns (is_slow, reason) tuple.
        """
        cmd_lower = command.lower().strip()
        cmd_parts = command.strip().split()
        base_cmd = cmd_parts[0] if cmd_parts else ""
        
        # Check if base command is in slow/silent list
        for slow_cmd in SLOW_SILENT_COMMANDS:
            if base_cmd == slow_cmd:
                return True, f"'{slow_cmd}' is a known slow/silent command"
        
        # Check for slow command patterns in the full command
        for pattern in SLOW_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True, f"Command matches slow pattern: {pattern}"
        
        # Check for file size indicators that suggest large operations
        # e.g., paths to large directories, wildcards, recursive flags
        if any(flag in cmd_parts for flag in ['-r', '-R', '--recursive', '-rf', '-Rf']):
            return True, "Recursive operation detected"
        
        # Check for common large file paths
        large_paths = ['/data', '/system', '/sdcard', '/storage', '/mnt']
        for path in large_paths:
            if path in command:
                return True, f"Operation on potentially large path: {path}"
        
        return False, ""
    
    def _detect_interactive_prompt(self, output: str) -> Optional[str]:
        """
        Check if output ends with an interactive prompt waiting for input.
        Returns the detected prompt pattern if found, None otherwise.
        """
        # Get last few lines to check for prompts
        lines = output.strip().split('\n')
        if not lines:
            return None
        
        last_content = '\n'.join(lines[-3:])  # Check last 3 lines
        
        for pattern in INTERACTIVE_PROMPT_PATTERNS:
            if re.search(pattern, last_content, re.IGNORECASE | re.MULTILINE):
                return pattern
        
        return None
    
    def _read_available_output(self, timeout: float = 0.1) -> str:
        """
        Non-blocking read of any available output.
        Returns empty string if nothing available.
        """
        if not self._process or not self._process.isalive():
            return ""
        
        try:
            # Use read_nonblocking with small timeout
            return self._process.read_nonblocking(size=65536, timeout=timeout)
        except pexpect.TIMEOUT:
            return ""
        except pexpect.EOF:
            return ""
        except Exception:
            return ""
    
    def peek_output(self) -> str:
        """
        Non-destructively peek at any pending output in the shell.
        Used by AI to inspect what's happening without blocking.
        Returns current buffer contents.
        """
        if not self.is_alive():
            return "Shell is not connected."
        
        try:
            # Read whatever is available without blocking
            output = self._read_available_output(timeout=0.5)
            if output:
                # Clean it up
                output = output.replace('\r\n', '\n').replace('\r', '\n')
                return output
            return "(no new output available)"
        except Exception as e:
            return f"Error peeking: {str(e)}"
    
    def send_input(self, text: str, press_enter: bool = True) -> str:
        """
        Send input text to the shell. Used by AI to respond to prompts.
        
        Args:
            text: Text to send
            press_enter: Whether to press enter after text (default True)
        
        Returns status message.
        """
        if not self.is_alive():
            return "STATUS: ERROR\nShell is not connected."
        
        try:
            if press_enter:
                self._process.sendline(text)
            else:
                self._process.send(text)
            return f"STATUS: SENT\nSent: {repr(text)}\nPress enter: {press_enter}"
        except Exception as e:
            return f"STATUS: ERROR\nFailed to send input: {str(e)}"
    
    def send_control(self, char: str) -> str:
        """
        Send a control character to the shell (e.g., 'c' for Ctrl+C).
        
        Args:
            char: Single character (e.g., 'c', 'd', 'z')
        
        Returns status message.
        """
        if not self.is_alive():
            return "STATUS: ERROR\nShell is not connected."
        
        try:
            self._process.sendcontrol(char.lower())
            return f"STATUS: SENT\nSent: Ctrl+{char.upper()}"
        except Exception as e:
            return f"STATUS: ERROR\nFailed to send control: {str(e)}"
    
    def _multi_stage_interrupt(self) -> str:
        """
        Multi-stage interrupt to recover from stuck commands.
        Tries Ctrl+C, then Ctrl+D, then Ctrl+Z + kill.
        Returns status message.
        """
        stages = []
        
        # Stage 1: Ctrl+C (SIGINT)
        try:
            self._process.sendcontrol('c')
            time.sleep(0.3)
            stages.append("Sent Ctrl+C")
            
            # Check if shell recovered
            if self.verify_responsive():
                return f"Recovery: {', '.join(stages)} - Shell recovered."
        except:
            pass
        
        # Stage 2: Ctrl+D (EOF)
        try:
            self._process.sendcontrol('d')
            time.sleep(0.3)
            stages.append("Sent Ctrl+D")
            
            if self.verify_responsive():
                return f"Recovery: {', '.join(stages)} - Shell recovered."
        except:
            pass
        
        # Stage 3: Ctrl+Z (SIGTSTP) to background, then try to kill
        try:
            self._process.sendcontrol('z')
            time.sleep(0.2)
            self._process.sendline('kill %1 2>/dev/null; fg 2>/dev/null || true')
            time.sleep(0.3)
            stages.append("Sent Ctrl+Z + kill")
            
            if self.verify_responsive():
                return f"Recovery: {', '.join(stages)} - Shell recovered."
        except:
            pass
        
        # Stage 4: Send newline and check
        try:
            self._process.sendline('')
            time.sleep(0.2)
            if self.verify_responsive():
                return f"Recovery: {', '.join(stages)} - Shell recovered."
        except:
            pass
        
        return f"Recovery FAILED: {', '.join(stages)} - Shell may be unusable. Recommend stop_shell + start_shell."
    
    def run_command(self, command: str, timeout_seconds: int = 30) -> str:
        """
        Execute a command with comprehensive hang detection and prevention.
        
        Features:
        - Dangerous command warnings
        - Progress monitoring (detects stuck commands)
        - Interactive prompt detection
        - Multi-stage interrupt recovery
        - Detailed status reporting
        - Smart handling of slow/silent commands (no false positives)
        """
        with self._lock:
            if not command or not command.strip():
                return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Empty command."
            
            # Check for dangerous commands
            warning = self._check_dangerous_command(command)
            warning_msg = f"\n{warning}" if warning else ""
            
            # Check if this is a known slow/silent command
            is_slow_cmd, slow_reason = self._is_slow_silent_command(command)
            
            if not self.is_alive():
                return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Shell not connected.\nAction: Use start_shell to connect first."
            
            if not self.verify_responsive():
                return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Shell not responding.\nAction: Use stop_shell then start_shell to reconnect."
            
            try:
                marker = f"{MARKER_PREFIX}{uuid.uuid4().hex[:8]}"
                exit_marker = f"__EXIT_{uuid.uuid4().hex[:8]}__"
                
                # Wrap command to capture exit code
                wrapped = f'{command}; echo "{exit_marker}$?{exit_marker}"; echo "{marker}"'
                self._process.sendline(wrapped)
                
                # Progress-monitoring loop instead of blocking expect
                start_time = time.time()
                accumulated_output = ""
                last_output_time = start_time
                intervals_without_progress = 0
                detected_prompt = None
                last_progress_report = start_time
                
                # Adaptive thresholds based on command type
                stuck_threshold = STUCK_THRESHOLD_INTERVALS
                min_time_for_stuck = MIN_TIME_BEFORE_STUCK_CHECK
                
                if is_slow_cmd:
                    # Much more patient with slow/silent commands
                    stuck_threshold *= SLOW_COMMAND_TIMEOUT_MULTIPLIER
                    min_time_for_stuck *= 3  # Wait longer before even checking
                
                while True:
                    elapsed = time.time() - start_time
                    
                    # Hard timeout check
                    if elapsed >= timeout_seconds:
                        # Attempt recovery
                        recovery_msg = self._multi_stage_interrupt()
                        slow_note = f"\nNote: This was identified as a slow command ({slow_reason})" if is_slow_cmd else ""
                        return (f"STATUS: TIMEOUT\nShell: {self.shell_id}\n"
                                f"Command: {command[:100]}\nTimeout: {timeout_seconds}s\n"
                                f"Partial output ({len(accumulated_output)} chars captured)\n"
                                f"{recovery_msg}{slow_note}\n"
                                f"OUTPUT:\n{accumulated_output[-2000:] if accumulated_output else '(none)'}"
                                f"{warning_msg}")
                    
                    # Read any available output (non-blocking)
                    new_output = self._read_available_output(timeout=PROGRESS_CHECK_INTERVAL)
                    
                    if new_output:
                        accumulated_output += new_output
                        last_output_time = time.time()
                        intervals_without_progress = 0
                        
                        # Check if we found our end marker
                        if marker in accumulated_output:
                            break
                        
                        # Check for interactive prompts (but be careful with slow commands)
                        # Only check prompts if we're NOT in a known slow command, or if
                        # the prompt pattern is very specific (not just ":" or "?")
                        if not is_slow_cmd:
                            detected_prompt = self._detect_interactive_prompt(accumulated_output)
                            if detected_prompt:
                                # Command is waiting for input - this will hang!
                                recovery_msg = self._multi_stage_interrupt()
                                return (f"STATUS: WAITING_FOR_INPUT\nShell: {self.shell_id}\n"
                                        f"Command: {command[:100]}\n"
                                        f"Detected interactive prompt matching: {detected_prompt}\n"
                                        f"The command is waiting for user input and would hang.\n"
                                        f"{recovery_msg}\n"
                                        f"OUTPUT:\n{accumulated_output[-2000:]}"
                                        f"{warning_msg}")
                        else:
                            # For slow commands, only check for very specific prompts
                            # (password, y/n) not generic ones like ":" which could be progress
                            specific_prompts = [
                                r'\[y/n\]', r'\[Y/n\]', r'\(y/n\)',
                                r'[Pp]assword\s*:', r'[Pp]assphrase\s*:',
                                r'Are you sure', r'Overwrite\?'
                            ]
                            last_lines = '\n'.join(accumulated_output.strip().split('\n')[-3:])
                            for prompt_pattern in specific_prompts:
                                if re.search(prompt_pattern, last_lines, re.IGNORECASE):
                                    recovery_msg = self._multi_stage_interrupt()
                                    return (f"STATUS: WAITING_FOR_INPUT\nShell: {self.shell_id}\n"
                                            f"Command: {command[:100]}\n"
                                            f"Detected specific prompt: {prompt_pattern}\n"
                                            f"{recovery_msg}\n"
                                            f"OUTPUT:\n{accumulated_output[-2000:]}"
                                            f"{warning_msg}")
                    else:
                        intervals_without_progress += 1
                        
                        # Check if stuck (no output for too long while command running)
                        # Instead of auto-recovering, return UNCERTAIN and let AI decide
                        if intervals_without_progress >= stuck_threshold:
                            time_since_output = time.time() - last_output_time
                            
                            # Only consider uncertain if we're past minimum wait time
                            if elapsed > min_time_for_stuck and time_since_output > min_time_for_stuck:
                                # For slow commands, just keep waiting patiently
                                if is_slow_cmd:
                                    intervals_without_progress = 0
                                    continue
                                
                                # For normal commands, return UNCERTAIN - let AI decide
                                # Don't auto-interrupt - the AI might know better
                                return (f"STATUS: UNCERTAIN\n"
                                        f"Shell: {self.shell_id}\n"
                                        f"Command: {command[:100]}\n"
                                        f"Elapsed: {elapsed:.1f}s\n"
                                        f"No output for: {time_since_output:.1f}s\n"
                                        f"\n"
                                        f"The command has produced no output recently. This could mean:\n"
                                        f"1. It's working on something slow (downloading, processing)\n"
                                        f"2. It's waiting for input that wasn't detected\n"
                                        f"3. It's genuinely stuck\n"
                                        f"\n"
                                        f"WHAT YOU (the AI) SHOULD DO:\n"
                                        f"• Use peek_output('{self.shell_id}') to check for new output\n"
                                        f"• Use diagnose_shell('{self.shell_id}') for detailed analysis\n"
                                        f"• If you think it's stuck: send_control_char('{self.shell_id}', 'c')\n"
                                        f"• If it needs input: send_input('{self.shell_id}', 'your_response')\n"
                                        f"• If you want to wait longer: just call run_command again with longer timeout\n"
                                        f"\n"
                                        f"PARTIAL OUTPUT SO FAR ({len(accumulated_output)} chars):\n"
                                        f"{accumulated_output[-1500:] if accumulated_output else '(none)'}"
                                        f"{warning_msg}")
                
                # Successfully got output with marker
                output = accumulated_output.replace('\r\n', '\n').replace('\r', '\n')
                
                # Extract everything before the marker
                marker_pos = output.find(marker)
                if marker_pos != -1:
                    output = output[:marker_pos]
                
                # Extract exit code
                exit_code = None
                exit_match = re.search(rf'{exit_marker}(\d+){exit_marker}', output)
                if exit_match:
                    exit_code = int(exit_match.group(1))
                    output = re.sub(rf'{exit_marker}\d+{exit_marker}\n?', '', output)
                
                # TEAM_008: Aggressive marker and noise cleanup
                # Remove any remaining marker patterns
                output = re.sub(rf'{MARKER_PREFIX}[a-f0-9]+', '', output)
                output = re.sub(r'__EXIT_[a-f0-9]+__\d*__EXIT_[a-f0-9]+__', '', output)
                output = re.sub(r'__EXIT_[a-f0-9]+__', '', output)
                
                # Remove the wrapped command echo (the command we sent)
                # Pattern: command; echo "..."; echo "..."
                wrapped_pattern = re.escape(command) + r';\s*echo\s+"[^"]*";\s*echo\s+"[^"]*"'
                output = re.sub(wrapped_pattern, '', output)
                
                # Also remove partial command echoes (terminal may wrap/truncate)
                if len(command) > 20:
                    # Remove lines containing significant parts of the command
                    cmd_fragment = command[:40]
                    output = re.sub(rf'^.*{re.escape(cmd_fragment[:20])}.*$', '', output, flags=re.MULTILINE)
                
                # Remove echo commands themselves if visible
                output = re.sub(r'echo\s+"___MCP_MARKER___[^"]*"', '', output)
                output = re.sub(r'echo\s+"__EXIT_[^"]*"', '', output)
                
                # Clean output - remove empty lines and prompts
                lines = output.strip().split('\n')
                clean_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    # Skip empty lines at start
                    if not clean_lines and not line_stripped:
                        continue
                    # Skip lines that are just shell prompts
                    if re.match(r'^[\w@\-\.]+:[/\w]*\s*[#$]\s*$', line_stripped):
                        continue
                    # Skip lines containing our marker patterns
                    if MARKER_PREFIX in line_stripped or '__EXIT_' in line_stripped:
                        continue
                    # Skip command echo lines
                    if command[:30] in line_stripped and 'echo' in line_stripped:
                        continue
                    clean_lines.append(line_stripped)
                
                # Remove trailing empty lines
                while clean_lines and not clean_lines[-1]:
                    clean_lines.pop()
                
                final_output = '\n'.join(clean_lines)
                self._last_activity = time.time()
                
                # Build response
                parts = [f"SHELL: {self.shell_id}"]
                if exit_code is not None:
                    parts.append(f"STATUS: {'SUCCESS' if exit_code == 0 else 'COMMAND_FAILED'}")
                    parts.append(f"EXIT_CODE: {exit_code}")
                else:
                    parts.append("STATUS: COMPLETED")
                    parts.append("EXIT_CODE: unknown")
                
                if warning:
                    parts.append(warning)
                
                parts.append("OUTPUT:")
                parts.append(final_output if final_output else "(no output)")
                
                return '\n'.join(parts)
                
            except pexpect.exceptions.EOF:
                self._is_connected = False
                return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: Shell connection lost.\nAction: Use start_shell to reconnect."
            except Exception as e:
                return f"STATUS: ERROR\nShell: {self.shell_id}\nReason: {str(e)}"
    
    def get_status(self) -> dict:
        """Get shell status as dict."""
        return {
            "shell_id": self.shell_id,
            "device": self.device_serial,
            "type": self.shell_type.value,
            "connected": self._is_connected and self.is_alive(),
            "responsive": self.verify_responsive() if self._is_connected else False,
            "idle_seconds": time.time() - self._last_activity if self._last_activity else None
        }
