"""
Minimal analytics for MCP server ergonomics optimization.
TEAM_009: Simple JSON logging to understand agent experience.

⚠️ PRE-PUBLISH: Add privacy controls before making this public!
"""
import json
import os
from datetime import datetime
from pathlib import Path

# Storage location
ANALYTICS_DIR = Path.home() / ".android-shell-mcp"
ANALYTICS_FILE = ANALYTICS_DIR / "analytics.jsonl"

# Track last tool for retry detection
_last_tool = None


def _ensure_dir():
    """Create analytics directory if needed."""
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)


def log_event(tool: str, ok: bool, uncertain: bool = False, batch_size: int = 1, truncated: int = 0):
    """
    Log a tool usage event.
    
    Args:
        tool: Tool name (e.g., "run_command", "run_commands")
        ok: Whether the tool succeeded
        uncertain: Whether UNCERTAIN status was returned
        batch_size: Number of commands (for batch tools)
        truncated: Number of outputs that were truncated
    """
    global _last_tool
    
    try:
        _ensure_dir()
        
        event = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "ok": ok,
            "uncertain": uncertain,
            "retry": tool == _last_tool,
            "batch_size": batch_size,
            "truncated": truncated
        }
        
        with open(ANALYTICS_FILE, "a") as f:
            f.write(json.dumps(event) + "\n")
        
        _last_tool = tool
    except Exception:
        pass  # Never fail the tool call due to analytics


def get_summary() -> dict:
    """
    Get usage summary for optimization insights.
    
    Returns dict with:
    - tool_counts: {tool_name: count}
    - success_rate: float
    - uncertain_rate: float
    - retry_rate: float
    - batch_adoption: float (% of command tools that used batch)
    - truncation_rate: float
    """
    if not ANALYTICS_FILE.exists():
        return {"error": "No analytics data yet"}
    
    try:
        events = []
        with open(ANALYTICS_FILE) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        if not events:
            return {"error": "No events recorded"}
        
        total = len(events)
        tool_counts = {}
        successes = 0
        uncertains = 0
        retries = 0
        batch_commands = 0
        single_commands = 0
        truncations = 0
        
        for e in events:
            tool = e.get("tool", "unknown")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
            
            if e.get("ok"):
                successes += 1
            if e.get("uncertain"):
                uncertains += 1
            if e.get("retry"):
                retries += 1
            if e.get("truncated", 0) > 0:
                truncations += 1
            
            # Track batch adoption
            if tool == "run_commands":
                batch_commands += 1
            elif tool == "run_command":
                single_commands += 1
        
        command_total = batch_commands + single_commands
        
        return {
            "total_events": total,
            "tool_counts": tool_counts,
            "success_rate": round(successes / total * 100, 1),
            "uncertain_rate": round(uncertains / total * 100, 1),
            "retry_rate": round(retries / total * 100, 1),
            "batch_adoption": round(batch_commands / command_total * 100, 1) if command_total > 0 else 0,
            "truncation_rate": round(truncations / total * 100, 1),
            "insights": _generate_insights(tool_counts, successes/total, uncertains/total, retries/total, batch_commands, single_commands)
        }
    except Exception as e:
        return {"error": str(e)}


def _generate_insights(tool_counts: dict, success_rate: float, uncertain_rate: float, retry_rate: float, batch: int, single: int) -> list:
    """Generate actionable insights from metrics."""
    insights = []
    
    # Batch adoption
    if single > batch * 2:
        insights.append("⚠️ Low batch adoption: Agents using run_command more than run_commands. Make batch more ergonomic?")
    
    # Retry rate
    if retry_rate > 0.15:
        insights.append(f"⚠️ High retry rate ({retry_rate*100:.0f}%): Agents retrying tools. Check error messages and recovery.")
    
    # Uncertain rate
    if uncertain_rate > 0.1:
        insights.append(f"⚠️ High uncertain rate ({uncertain_rate*100:.0f}%): Consider tuning hang detection thresholds.")
    
    # Unused tools
    all_tools = {"list_devices", "start_shell", "stop_shell", "shell_status", "run_command", "run_commands", "background_job", "file_transfer", "shell_interact"}
    unused = all_tools - set(tool_counts.keys())
    if unused:
        insights.append(f"📊 Unused tools: {', '.join(unused)}. Remove or improve discoverability?")
    
    if not insights:
        insights.append("✅ No obvious ergonomic issues detected.")
    
    return insights


def clear_analytics():
    """Clear all analytics data."""
    if ANALYTICS_FILE.exists():
        ANALYTICS_FILE.unlink()
    return "Analytics cleared."
