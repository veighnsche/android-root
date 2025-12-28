"""
Configuration and constants for Android Shell Manager.
"""
import shutil

ADB_BINARY = shutil.which("adb") or "adb"
FASTBOOT_BINARY = shutil.which("fastboot") or "fastboot"

# Unique marker for output boundary detection
MARKER_PREFIX = "___MCP_MARKER___"

# Robust prompt patterns for various Android shells/ROMs
SHELL_PROMPT_PATTERNS = [
    r'[\$#]\s*$',           # Simple $ or # at end
    r':\S*\s*[\$#]\s*$',    # path:dir $ or #
    r'@\S+:\S*\s*[\$#]\s*$' # user@host:dir $ or #
]

# Patterns that indicate a command is waiting for user input (HANG RISK!)
INTERACTIVE_PROMPT_PATTERNS = [
    r'\[y/n\]\s*:?\s*$',           # [y/n] or [y/n]: prompts
    r'\[Y/n\]\s*:?\s*$',           # [Y/n] prompts
    r'\[yes/no\]\s*:?\s*$',        # [yes/no] prompts
    r'\(y/n\)\s*:?\s*$',           # (y/n) prompts
    r'y/n\)?\s*:?\s*$',            # Simple y/n
    r'[Pp]assword\s*:?\s*$',       # Password: prompts
    r'[Pp]assphrase\s*:?\s*$',     # Passphrase prompts
    r'Enter\s+.*:\s*$',            # Enter <something>: prompts
    r'Press\s+.*to\s+continue',    # Press any key prompts
    r'--More--',                   # Pager prompts (less/more)
    r':\s*$',                      # Generic colon prompt (vim, etc.)
    r'\?\s*$',                     # Question mark prompts
    r'Continue\?\s*',              # Continue? prompts
    r'Overwrite\?\s*',             # Overwrite? prompts
    r'confirm\s*[\(\[]',           # confirm (y/n) style
    r'Are you sure',               # Are you sure prompts
    r'\(END\)',                    # less/man pager at end
    r'~\s*$',                      # vim empty line indicator
]

# Commands known to be dangerous (interactive/blocking by nature)
DANGEROUS_COMMANDS = [
    'vi', 'vim', 'nano', 'emacs',   # Editors
    'top', 'htop',                   # Interactive monitors
    'less', 'more',                  # Pagers
    'ssh', 'telnet',                 # Remote shells
    'python', 'python3', 'node',     # REPLs (without args)
    'sh', 'bash', 'zsh',             # Sub-shells (without -c)
    'adb shell',                     # Nested adb
    'su',                            # Without -c
    'passwd',                        # Password change
    'read',                          # Bash read command
    'cat',                           # cat without file (reads stdin)
]

# How long to wait between progress checks (seconds)
PROGRESS_CHECK_INTERVAL = 0.5

# How many intervals without new output before considering "stuck"
STUCK_THRESHOLD_INTERVALS = 4  # 2 seconds of no output

# Commands known to be SLOW/SILENT but legitimate (don't trigger false positives)
# These commands may produce no output for extended periods while working
SLOW_SILENT_COMMANDS = [
    # Downloads/network
    'wget', 'curl', 'aria2c', 'axel',
    'scp', 'rsync', 'sftp', 'ftp',
    
    # File operations (large files)
    'cp', 'mv', 'dd', 'tar', 'gzip', 'gunzip', 'bzip2', 'xz',
    'zip', 'unzip', '7z', '7za',
    
    # Package managers
    'apt', 'apt-get', 'dpkg', 'yum', 'dnf', 'pacman',
    'pip', 'pip3', 'npm', 'yarn', 'gem',
    'pm',  # Android package manager
    
    # Android specific
    'am', 'cmd',  # Activity manager, command service
    'dex2oat',    # DEX compilation
    'installd',   # Package installation
    
    # Disk operations
    'mkfs', 'fsck', 'e2fsck', 'resize2fs',
    'fdisk', 'parted', 'gdisk',
    
    # Build/compile
    'make', 'cmake', 'ninja', 'gradle', 'gradlew',
    'gcc', 'g++', 'clang', 'javac',
    
    # Database operations
    'sqlite3', 'mysql', 'pg_dump', 'mongodump',
    
    # Crypto/hashing (CPU intensive, silent)
    'sha256sum', 'sha512sum', 'md5sum', 'openssl',
    'gpg', 'age',
    
    # Search (can be slow on large filesystems)
    'find', 'locate', 'grep', 'rg', 'ag',
    
    # System operations
    'sync', 'reboot', 'shutdown',
    'mount', 'umount',
    
    # ADB operations (when nested or for files)
    'adb',
    
    # Sleep/wait (intentionally slow)
    'sleep', 'wait',
]

# Patterns in command that suggest it's a long-running operation
SLOW_COMMAND_PATTERNS = [
    r'>\s*/dev/null',        # Redirecting to null (hiding output)
    r'2>&1\s*>\s*/dev/null', # Full silence redirect
    r'--quiet', r'-q',       # Quiet flags
    r'--silent', r'-s',      # Silent flags
    r'--no-progress',        # No progress flag
    r'\|\s*tail',            # Piping to tail (may buffer)
    r'\|\s*head',            # Piping to head
    r'\|\s*grep',            # Piping to grep (may buffer)
    r'\|\s*awk',             # Piping to awk
    r'\|\s*sed',             # Piping to sed
    r'install',              # Any install command
    r'download',             # Any download operation
    r'backup',               # Backup operations
    r'restore',              # Restore operations
    r'flash',                # Flashing operations
    r'update',               # Update operations
    r'upgrade',              # Upgrade operations
    r'pull', r'push',        # ADB pull/push style
    r'copy', r'clone',       # Copy operations
]

# Multiplier for stuck threshold when running slow commands
SLOW_COMMAND_TIMEOUT_MULTIPLIER = 10  # 10x longer tolerance

# Minimum time before we even consider a command "stuck"
MIN_TIME_BEFORE_STUCK_CHECK = 5.0  # seconds
