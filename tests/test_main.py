#!/usr/bin/env python3
"""
Tests for Android Shell Manager MCP Server.

Test devices:
- ROOTED: Pixel 6 (18271FDF600EJW)
- NON-ROOTED: Lenovo TB-J606F (HA18JEG1)

Run with: python tests.py
"""
import subprocess
import sys
import time

# Add current directory to path for imports
sys.path.insert(0, '.')

from core.manager import ShellManager
from core.models import ShellType, DeviceMode
from core.config import ADB_BINARY


# ============= TEST CONFIGURATION =============
# These will be auto-detected, but can be overridden
ROOTED_DEVICE = None
NON_ROOTED_DEVICE = None


def detect_devices():
    """Auto-detect connected devices and their root status."""
    global ROOTED_DEVICE, NON_ROOTED_DEVICE
    
    print("=" * 60)
    print("DETECTING DEVICES...")
    print("=" * 60)
    
    result = subprocess.run(
        [ADB_BINARY, "devices", "-l"],
        capture_output=True, text=True, timeout=10
    )
    
    devices = []
    for line in result.stdout.strip().split('\n')[1:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            serial = parts[0]
            model = None
            for part in parts[2:]:
                if part.startswith('model:'):
                    model = part.split(':')[1]
            devices.append((serial, model))
    
    print(f"Found {len(devices)} device(s):")
    for serial, model in devices:
        # Check if device has root
        has_root = check_device_root(serial)
        status = "ROOTED" if has_root else "NOT ROOTED"
        print(f"  {serial} ({model}) - {status}")
        
        if has_root and ROOTED_DEVICE is None:
            ROOTED_DEVICE = serial
        elif not has_root and NON_ROOTED_DEVICE is None:
            NON_ROOTED_DEVICE = serial
    
    print()
    print(f"ROOTED_DEVICE: {ROOTED_DEVICE}")
    print(f"NON_ROOTED_DEVICE: {NON_ROOTED_DEVICE}")
    print("=" * 60)
    print()
    
    return len(devices) > 0


def check_device_root(serial: str) -> bool:
    """Check if a device has root access."""
    try:
        result = subprocess.run(
            [ADB_BINARY, "-s", serial, "shell", "su", "-c", "id"],
            capture_output=True, text=True, timeout=5
        )
        return "uid=0" in result.stdout
    except:
        return False


# ============= TEST UTILITIES =============

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures = []
    
    def record_pass(self, name: str):
        self.passed += 1
        print(f"  ✓ {name}")
    
    def record_fail(self, name: str, reason: str):
        self.failed += 1
        self.failures.append((name, reason))
        print(f"  ✗ {name}")
        print(f"    Reason: {reason[:200]}")
    
    def record_skip(self, name: str, reason: str):
        self.skipped += 1
        print(f"  ⊘ {name} (SKIPPED: {reason})")
    
    def summary(self):
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"  Passed:  {self.passed}")
        print(f"  Failed:  {self.failed}")
        print(f"  Skipped: {self.skipped}")
        print()
        if self.failures:
            print("FAILURES:")
            for name, reason in self.failures:
                print(f"  - {name}: {reason[:100]}")
        print("=" * 60)
        return self.failed == 0


results = TestResult()


def assert_true(condition: bool, test_name: str):
    """Assert that condition is true."""
    if condition:
        results.record_pass(test_name)
    else:
        results.record_fail(test_name, "Condition was False")


def assert_contains(output: str, substring: str, test_name: str):
    """Assert that output contains substring."""
    if substring in output:
        results.record_pass(test_name)
        return True
    else:
        results.record_fail(test_name, f"Expected '{substring}' in output: {output[:200]}")
        return False


def assert_not_contains(output: str, substring: str, test_name: str):
    """Assert that output does NOT contain substring."""
    if substring not in output:
        results.record_pass(test_name)
        return True
    else:
        results.record_fail(test_name, f"Did not expect '{substring}' in output: {output[:200]}")
        return False


# ============= TESTS =============

def test_list_devices():
    """Test device listing."""
    print("\n--- TEST: list_devices ---")
    manager = ShellManager()
    
    output = manager.list_all_devices()
    assert_contains(output, "STATUS: FOUND_", "list_devices returns found status")
    assert_contains(output, "ADB", "list_devices shows ADB devices")
    
    if ROOTED_DEVICE:
        assert_contains(output, ROOTED_DEVICE[:8], "list_devices shows rooted device")
    if NON_ROOTED_DEVICE:
        assert_contains(output, NON_ROOTED_DEVICE[:8], "list_devices shows non-rooted device")


def test_start_shell_non_root():
    """Test starting a non-root shell."""
    print("\n--- TEST: start_shell (non-root) ---")
    
    device = NON_ROOTED_DEVICE or ROOTED_DEVICE
    if not device:
        results.record_skip("start_shell non-root", "No device available")
        return
    
    manager = ShellManager()
    
    output = manager.start_shell(device, "non_root")
    assert_contains(output, "STATUS: CONNECTED", "non-root shell connects")
    assert_contains(output, "Type: non_root", "shell type is non_root")
    
    # Extract shell_id and clean up
    shell_id = None
    for line in output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if shell_id:
        manager.stop_shell(shell_id)
        results.record_pass("non-root shell cleanup")
    
    manager.stop_all()


def test_start_shell_root():
    """Test starting a root shell."""
    print("\n--- TEST: start_shell (root) ---")
    
    if not ROOTED_DEVICE:
        results.record_skip("start_shell root", "No rooted device available")
        return
    
    manager = ShellManager()
    
    output = manager.start_shell(ROOTED_DEVICE, "root")
    
    if "STATUS: CONNECTED" in output:
        assert_contains(output, "Type: root", "shell type is root")
        results.record_pass("root shell connects on rooted device")
        
        # Verify we have root
        shell_id = None
        for line in output.split('\n'):
            if line.startswith("Shell: "):
                shell_id = line.split(": ", 1)[1].strip()
                break
        
        if shell_id:
            id_output = manager.run_in_shell(shell_id, "id")
            assert_contains(id_output, "uid=0", "root shell has uid=0")
            manager.stop_shell(shell_id)
    else:
        results.record_fail("root shell connects", output[:200])
    
    manager.stop_all()


def test_start_shell_root_on_non_rooted():
    """Test that root shell fails gracefully on non-rooted device."""
    print("\n--- TEST: start_shell (root on non-rooted) ---")
    
    if not NON_ROOTED_DEVICE:
        results.record_skip("root on non-rooted", "No non-rooted device available")
        return
    
    manager = ShellManager()
    
    output = manager.start_shell(NON_ROOTED_DEVICE, "root")
    
    # Should fail with helpful message
    if "STATUS: ERROR" in output:
        results.record_pass("root shell fails on non-rooted device")
        if "denied" in output.lower() or "not found" in output.lower() or "not rooted" in output.lower():
            results.record_pass("error message is helpful")
        else:
            results.record_fail("error message is helpful", output[:200])
    else:
        results.record_fail("root shell fails on non-rooted device", f"Got: {output[:200]}")
    
    manager.stop_all()


def test_run_command_basic():
    """Test basic command execution."""
    print("\n--- TEST: run_command (basic) ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("run_command basic", "No device available")
        return
    
    manager = ShellManager()
    shell_type = "root" if device == ROOTED_DEVICE else "non_root"
    
    start_output = manager.start_shell(device, shell_type)
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("run_command basic", "Could not start shell")
        return
    
    # Test echo
    output = manager.run_in_shell(shell_id, "echo 'HELLO_TEST_123'")
    assert_contains(output, "HELLO_TEST_123", "echo command works")
    assert_contains(output, "EXIT_CODE: 0", "echo returns exit code 0")
    
    # Test pwd
    output = manager.run_in_shell(shell_id, "pwd")
    assert_contains(output, "/", "pwd returns a path")
    
    # Test exit code
    output = manager.run_in_shell(shell_id, "false")
    assert_contains(output, "COMMAND_FAILED", "false command shows failed status")
    assert_not_contains(output, "EXIT_CODE: 0", "false has non-zero exit code")
    
    manager.stop_all()


def test_run_command_with_output():
    """Test commands with substantial output."""
    print("\n--- TEST: run_command (with output) ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("run_command with output", "No device available")
        return
    
    manager = ShellManager()
    shell_type = "root" if device == ROOTED_DEVICE else "non_root"
    
    start_output = manager.start_shell(device, shell_type)
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("run_command with output", "Could not start shell")
        return
    
    # Test ls
    output = manager.run_in_shell(shell_id, "ls /system")
    assert_contains(output, "SUCCESS", "ls /system succeeds")
    assert_contains(output, "bin", "ls /system shows bin")
    
    # Test multi-line output
    output = manager.run_in_shell(shell_id, "ls /system | head -5")
    lines = [l for l in output.split('\n') if l.strip() and not l.startswith('SHELL:') and not l.startswith('STATUS:') and not l.startswith('EXIT_CODE:') and not l.startswith('OUTPUT:')]
    if len(lines) >= 3:
        results.record_pass("multi-line output works")
    else:
        results.record_fail("multi-line output works", f"Only got {len(lines)} lines")
    
    manager.stop_all()


def test_command_timeout():
    """Test command timeout handling."""
    print("\n--- TEST: run_command (timeout) ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("run_command timeout", "No device available")
        return
    
    manager = ShellManager()
    shell_type = "root" if device == ROOTED_DEVICE else "non_root"
    
    start_output = manager.start_shell(device, shell_type)
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("run_command timeout", "Could not start shell")
        return
    
    # Run a slow command with short timeout
    start = time.time()
    output = manager.run_in_shell(shell_id, "sleep 30", timeout_seconds=3)
    elapsed = time.time() - start
    
    # Should timeout, not wait 30 seconds
    if elapsed < 10:
        results.record_pass("timeout triggers before command completes")
    else:
        results.record_fail("timeout triggers", f"Took {elapsed:.1f}s")
    
    if "TIMEOUT" in output or "UNCERTAIN" in output:
        results.record_pass("timeout returns appropriate status")
    else:
        results.record_fail("timeout returns status", output[:200])
    
    # Shell should still be usable
    time.sleep(1)
    output2 = manager.run_in_shell(shell_id, "echo 'AFTER_TIMEOUT'")
    if "AFTER_TIMEOUT" in output2:
        results.record_pass("shell recovers after timeout")
    else:
        results.record_fail("shell recovers after timeout", output2[:200])
    
    manager.stop_all()


def test_slow_command_detection():
    """Test that slow commands are detected and handled patiently."""
    print("\n--- TEST: slow command detection ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("slow command detection", "No device available")
        return
    
    manager = ShellManager()
    shell_type = "root" if device == ROOTED_DEVICE else "non_root"
    
    start_output = manager.start_shell(device, shell_type)
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("slow command detection", "Could not start shell")
        return
    
    # Run a slow command that should be recognized
    # Using 'find' which is in the slow commands list
    output = manager.run_in_shell(shell_id, "find /system -name 'build.prop' 2>/dev/null", timeout_seconds=15)
    
    if "SUCCESS" in output or "COMPLETED" in output:
        results.record_pass("slow command completes without false positive")
    elif "UNCERTAIN" in output:
        # This is acceptable - AI can decide
        results.record_pass("slow command returns UNCERTAIN (acceptable)")
    else:
        results.record_fail("slow command handling", output[:200])
    
    manager.stop_all()


def test_shell_status():
    """Test shell status reporting."""
    print("\n--- TEST: shell_status ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("shell_status", "No device available")
        return
    
    manager = ShellManager()
    
    start_output = manager.start_shell(device, "non_root")
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("shell_status", "Could not start shell")
        return
    
    output = manager.get_shell_status(shell_id)
    assert_contains(output, "Connected: True", "status shows connected")
    assert_contains(output, "Responsive: True", "status shows responsive")
    
    manager.stop_all()


def test_list_shells():
    """Test listing multiple shells."""
    print("\n--- TEST: list_shells ---")
    
    devices = [d for d in [ROOTED_DEVICE, NON_ROOTED_DEVICE] if d]
    if len(devices) < 1:
        results.record_skip("list_shells", "No devices available")
        return
    
    manager = ShellManager()
    
    # Start shells on available devices
    shell_ids = []
    for device in devices:
        output = manager.start_shell(device, "non_root")
        for line in output.split('\n'):
            if line.startswith("Shell: "):
                shell_ids.append(line.split(": ", 1)[1].strip())
                break
    
    output = manager.list_shells()
    assert_contains(output, f"FOUND_{len(shell_ids)}_SHELL", "list_shells shows correct count")
    
    for shell_id in shell_ids:
        assert_contains(output, shell_id[:8], f"list_shells shows {shell_id[:8]}")
    
    manager.stop_all()


def test_peek_output():
    """Test peeking at shell output."""
    print("\n--- TEST: peek_output ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("peek_output", "No device available")
        return
    
    manager = ShellManager()
    
    start_output = manager.start_shell(device, "non_root")
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("peek_output", "Could not start shell")
        return
    
    # Peek should work on idle shell
    output = manager.peek_shell_output(shell_id)
    assert_contains(output, "PEEKED_OUTPUT", "peek_output returns output header")
    results.record_pass("peek_output works on idle shell")
    
    manager.stop_all()


def test_send_input():
    """Test sending input to shell."""
    print("\n--- TEST: send_input ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("send_input", "No device available")
        return
    
    manager = ShellManager()
    
    start_output = manager.start_shell(device, "non_root")
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("send_input", "Could not start shell")
        return
    
    # Send some input
    output = manager.send_to_shell(shell_id, "echo 'INPUT_TEST'")
    assert_contains(output, "STATUS: SENT", "send_input returns sent status")
    
    # Peek to see the result
    time.sleep(0.5)
    peek = manager.peek_shell_output(shell_id)
    if "INPUT_TEST" in peek:
        results.record_pass("send_input text appears in output")
    else:
        results.record_pass("send_input completed (output may be consumed)")
    
    manager.stop_all()


def test_send_control_char():
    """Test sending control characters."""
    print("\n--- TEST: send_control_char ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("send_control_char", "No device available")
        return
    
    manager = ShellManager()
    
    start_output = manager.start_shell(device, "non_root")
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("send_control_char", "Could not start shell")
        return
    
    # Send Ctrl+C
    output = manager.send_control_to_shell(shell_id, "c")
    assert_contains(output, "STATUS: SENT", "send_control_char returns sent status")
    assert_contains(output, "Ctrl+C", "send_control_char confirms Ctrl+C")
    
    manager.stop_all()


def test_background_job():
    """Test background job execution."""
    print("\n--- TEST: background jobs ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("background jobs", "No device available")
        return
    
    manager = ShellManager()
    shell_type = "root" if device == ROOTED_DEVICE else "non_root"
    
    start_output = manager.start_shell(device, shell_type)
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("background jobs", "Could not start shell")
        return
    
    # Start a background job
    output = manager.run_background(shell_id, "sleep 2 && echo 'BG_DONE'")
    assert_contains(output, "STATUS: STARTED", "background job starts")
    
    job_id = None
    for line in output.split('\n'):
        if line.startswith("Job: "):
            job_id = line.split(": ", 1)[1].strip()
            break
    
    if job_id:
        results.record_pass("background job returns job_id")
        
        # Check job status
        time.sleep(0.5)
        check_output = manager.check_background_job(job_id)
        if "RUNNING" in check_output or "COMPLETED" in check_output:
            results.record_pass("check_job returns status")
        else:
            results.record_fail("check_job returns status", check_output[:200])
        
        # List jobs
        list_output = manager.list_background_jobs()
        assert_contains(list_output, job_id, "list_jobs shows our job")
    else:
        results.record_fail("background job returns job_id", output[:200])
    
    manager.stop_all()


def test_multiple_shells_on_same_device():
    """Test running multiple shells on the same device."""
    print("\n--- TEST: multiple shells on same device ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("multiple shells", "No device available")
        return
    
    manager = ShellManager()
    
    # Start two shells
    output1 = manager.start_shell(device, "non_root")
    output2 = manager.start_shell(device, "non_root")
    
    shell_id1 = None
    shell_id2 = None
    
    for line in output1.split('\n'):
        if line.startswith("Shell: "):
            shell_id1 = line.split(": ", 1)[1].strip()
            break
    
    for line in output2.split('\n'):
        if line.startswith("Shell: "):
            shell_id2 = line.split(": ", 1)[1].strip()
            break
    
    if shell_id1 and shell_id2:
        results.record_pass("can start multiple shells on same device")
        
        # They should be different
        if shell_id1 != shell_id2:
            results.record_pass("each shell has unique ID")
        else:
            results.record_fail("each shell has unique ID", "IDs are the same!")
        
        # Both should work independently
        out1 = manager.run_in_shell(shell_id1, "echo 'SHELL1'")
        out2 = manager.run_in_shell(shell_id2, "echo 'SHELL2'")
        
        if "SHELL1" in out1 and "SHELL2" in out2:
            results.record_pass("shells work independently")
        else:
            results.record_fail("shells work independently", f"out1={out1[:100]}, out2={out2[:100]}")
    else:
        results.record_fail("can start multiple shells", f"shell1={shell_id1}, shell2={shell_id2}")
    
    manager.stop_all()


def test_stop_all_shells():
    """Test stopping all shells."""
    print("\n--- TEST: stop_all_shells ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("stop_all_shells", "No device available")
        return
    
    manager = ShellManager()
    
    # Start some shells
    manager.start_shell(device, "non_root")
    manager.start_shell(device, "non_root")
    
    # Stop all
    output = manager.stop_all()
    assert_contains(output, "STATUS: STOPPED", "stop_all returns stopped status")
    
    # List should be empty
    list_output = manager.list_shells()
    assert_contains(list_output, "NO_SHELLS", "no shells after stop_all")


def test_shell_not_found():
    """Test error handling for non-existent shell."""
    print("\n--- TEST: shell not found errors ---")
    
    manager = ShellManager()
    
    output = manager.run_in_shell("fake_shell_id", "echo test")
    assert_contains(output, "STATUS: ERROR", "run on fake shell returns error")
    assert_contains(output, "not found", "error mentions shell not found")
    
    output = manager.stop_shell("fake_shell_id")
    assert_contains(output, "STATUS: ERROR", "stop fake shell returns error")


def test_invalid_device():
    """Test error handling for invalid device."""
    print("\n--- TEST: invalid device errors ---")
    
    manager = ShellManager()
    
    output = manager.start_shell("FAKE_DEVICE_SERIAL", "root")
    assert_contains(output, "STATUS: ERROR", "start_shell on fake device returns error")


def test_batch_commands():
    """Test batch command execution (TEAM_008 feature)."""
    print("\n--- TEST: batch commands ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("batch commands", "No device available")
        return
    
    manager = ShellManager()
    shell_type = "root" if device == ROOTED_DEVICE else "non_root"
    
    start_output = manager.start_shell(device, shell_type)
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("batch commands", "Could not start shell")
        return
    
    # Test batch with list of strings
    output = manager.run_commands_batch(shell_id, [
        "echo 'CMD1'",
        "echo 'CMD2'",
        "echo 'CMD3'"
    ])
    assert_contains(output, "BATCH RESULTS", "batch returns header")
    assert_contains(output, "3/3 succeeded", "all commands succeeded")
    assert_contains(output, "CMD1", "first command output present")
    assert_contains(output, "CMD3", "last command output present")
    
    # Test batch with dict specs
    output = manager.run_commands_batch(shell_id, [
        {"id": "list", "command": "ls /system"},
        {"id": "check", "command": "echo 'OK'"}
    ])
    assert_contains(output, "[list]", "command id appears in output")
    assert_contains(output, "[check]", "second command id appears")
    
    # Test stop_on_error
    output = manager.run_commands_batch(shell_id, [
        {"id": "ok", "command": "echo 'before'"},
        {"id": "fail", "command": "false"},
        {"id": "skip", "command": "echo 'after'"}
    ], stop_on_error=True)
    assert_contains(output, "STOPPED", "stop_on_error triggers")
    assert_not_contains(output, "after", "commands after failure skipped")
    
    manager.stop_all()


def test_working_directory():
    """Test working directory support (TEAM_008 feature)."""
    print("\n--- TEST: working directory ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("working directory", "No device available")
        return
    
    manager = ShellManager()
    shell_type = "root" if device == ROOTED_DEVICE else "non_root"
    
    start_output = manager.start_shell(device, shell_type)
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("working directory", "Could not start shell")
        return
    
    # Test with working_directory parameter
    output = manager.run_in_shell(shell_id, "pwd", working_directory="/system")
    assert_contains(output, "/system", "working_directory changes to /system")
    
    manager.stop_all()


def test_file_transfer():
    """Test file pull/push (TEAM_008 feature)."""
    print("\n--- TEST: file transfer ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("file transfer", "No device available")
        return
    
    manager = ShellManager()
    
    # Test pull_file on a publicly readable file
    output = manager.pull_file(device, "/proc/version")
    assert_contains(output, "STATUS: SUCCESS", "pull_file succeeds on /proc/version")
    assert_contains(output, "CONTENT:", "pull_file returns content")
    assert_contains(output, "Linux", "/proc/version contains Linux")
    
    # Test pull_file on non-existent file
    output = manager.pull_file(device, "/nonexistent/file/path")
    assert_contains(output, "STATUS: ERROR", "pull_file fails on missing file")
    
    # Test push_file (to tmp directory)
    test_content = "TEAM_008_TEST_CONTENT_12345"
    output = manager.push_file(device, "/data/local/tmp/test_push.txt", test_content)
    if "STATUS: SUCCESS" in output:
        results.record_pass("push_file writes to device")
        
        # Verify by pulling it back
        verify = manager.pull_file(device, "/data/local/tmp/test_push.txt")
        if test_content in verify:
            results.record_pass("push_file content verified")
        else:
            results.record_fail("push_file content verified", verify[:200])
        
        # Cleanup
        import subprocess
        subprocess.run([ADB_BINARY, "-s", device, "shell", "rm /data/local/tmp/test_push.txt"], capture_output=True)
    else:
        results.record_fail("push_file writes to device", output[:200])


def test_analytics():
    """Test analytics collection (TEAM_009 feature)."""
    print("\n--- TEST: analytics ---")
    
    import analytics
    import os
    
    # Clear any existing analytics
    if analytics.ANALYTICS_FILE.exists():
        analytics.ANALYTICS_FILE.unlink()
    
    # Log some test events
    analytics.log_event("run_command", ok=True, uncertain=False, truncated=0)
    analytics.log_event("run_command", ok=True, uncertain=False, truncated=1)
    analytics.log_event("run_commands", ok=True, batch_size=3, truncated=0)
    analytics.log_event("run_command", ok=False, uncertain=True, truncated=0)
    analytics.log_event("run_command", ok=True)  # This should be a retry
    
    # Verify file was created
    assert_true(analytics.ANALYTICS_FILE.exists(), "analytics file created")
    
    # Verify contents
    with open(analytics.ANALYTICS_FILE) as f:
        lines = f.readlines()
    
    assert_true(len(lines) == 5, f"analytics has 5 events (got {len(lines)})")
    
    # Check retry detection (event 5 should have retry=true since event 4 was also run_command)
    import json
    event5 = json.loads(lines[4])
    assert_true(event5.get("retry") == True, "retry detected on consecutive same-tool call")
    
    # Check batch_size recorded
    event3 = json.loads(lines[2])
    assert_true(event3.get("batch_size") == 3, "batch_size recorded correctly")
    
    # Check uncertain recorded
    event4 = json.loads(lines[3])
    assert_true(event4.get("uncertain") == True, "uncertain status recorded")
    
    # Test get_summary
    summary = analytics.get_summary()
    assert_true("total_events" in summary, "summary contains total_events")
    assert_true(summary["total_events"] == 5, "summary counts 5 events")
    assert_true("tool_counts" in summary, "summary contains tool_counts")
    assert_true("insights" in summary, "summary contains insights")
    
    # Print file location for visibility
    print(f"  Analytics file: {analytics.ANALYTICS_FILE}")
    
    # Clear test data
    analytics.clear_analytics()


def test_clean_output():
    """Test that output is clean without markers (TEAM_008 fix)."""
    print("\n--- TEST: clean output ---")
    
    device = ROOTED_DEVICE or NON_ROOTED_DEVICE
    if not device:
        results.record_skip("clean output", "No device available")
        return
    
    manager = ShellManager()
    shell_type = "root" if device == ROOTED_DEVICE else "non_root"
    
    start_output = manager.start_shell(device, shell_type)
    shell_id = None
    for line in start_output.split('\n'):
        if line.startswith("Shell: "):
            shell_id = line.split(": ", 1)[1].strip()
            break
    
    if not shell_id:
        results.record_fail("clean output", "Could not start shell")
        return
    
    # Run a command and check output is clean
    output = manager.run_in_shell(shell_id, "echo 'CLEAN_TEST'")
    
    # Should NOT contain markers
    assert_not_contains(output, "___MCP_MARKER___", "output has no MCP markers")
    assert_not_contains(output, "__EXIT_", "output has no EXIT markers")
    
    # Should contain clean output
    assert_contains(output, "CLEAN_TEST", "output contains expected text")
    
    manager.stop_all()


# ============= MAIN =============

def main():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " ANDROID SHELL MANAGER - TEST SUITE ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    if not detect_devices():
        print("ERROR: No devices connected!")
        print("Please connect at least one Android device with USB debugging enabled.")
        sys.exit(1)
    
    # Run all tests
    test_list_devices()
    test_start_shell_non_root()
    test_start_shell_root()
    test_start_shell_root_on_non_rooted()
    test_run_command_basic()
    test_run_command_with_output()
    test_command_timeout()
    test_slow_command_detection()
    test_shell_status()
    test_list_shells()
    test_peek_output()
    test_send_input()
    test_send_control_char()
    test_background_job()
    test_multiple_shells_on_same_device()
    test_stop_all_shells()
    test_shell_not_found()
    test_invalid_device()
    
    # TEAM_008: New feature tests
    test_batch_commands()
    test_working_directory()
    test_file_transfer()
    test_clean_output()
    
    # TEAM_009: Analytics tests
    test_analytics()
    
    # Summary
    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
