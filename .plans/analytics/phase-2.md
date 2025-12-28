# Phase 2: Design — Minimal Ergonomics Analytics

**Team**: TEAM_009
**Focus**: Agent ergonomics only (not performance/stability)
**Status**: In Progress

---

## Design Decisions

Based on user input:
- **SIMPLE** - bare minimum to know what to improve
- **ERGONOMICS FOCUS** - is the AI agent having a good experience?
- **INTERNAL ONLY** - no privacy concerns for now
- **JSON FILE** - simplest possible storage

---

## ⚠️ PRE-PUBLISH CHECKLIST

**Before publishing this MCP server, address:**
- [ ] Anonymize/remove command content from logs
- [ ] Add opt-out for analytics
- [ ] Review all stored data for PII
- [ ] Add data retention/deletion policy
- [ ] Document what's collected in README

---

## What to Track (Ergonomics Only)

### The Core Question
> "Is the agent struggling to use this tool?"

### Minimal Metrics

| Metric | Question It Answers |
|--------|---------------------|
| **Tool used** | Which tools do agents actually use? |
| **Success/Fail** | Did it work? |
| **UNCERTAIN count** | How often does agent need to investigate? |
| **Retry patterns** | Same tool called twice in a row = friction |
| **Batch adoption** | Is run_commands being used? (it should be) |
| **Output truncated** | Are limits being hit? |

### What We DON'T Track (for now)
- Latency/performance
- Detailed error messages
- Command contents (privacy)
- Session duration
- Device information

---

## Implementation: Single JSON Log

### File Location
```
~/.android-shell-mcp/analytics.jsonl
```

### Event Format (one JSON per line)
```json
{"ts": "2025-12-28T13:40:00", "tool": "run_commands", "ok": true, "uncertain": false, "retry": false, "batch_size": 3, "truncated": 1}
```

### Fields
| Field | Type | Description |
|-------|------|-------------|
| `ts` | string | ISO timestamp |
| `tool` | string | Tool name |
| `ok` | bool | Success (true) or failure (false) |
| `uncertain` | bool | Returned UNCERTAIN status |
| `retry` | bool | Same tool as previous call |
| `batch_size` | int | Number of commands (for run_commands) |
| `truncated` | int | Number of outputs truncated |

---

## Implementation Plan

### Step 1: Create analytics.py (minimal)
```python
# Simple append-only JSON logger
def log_event(tool, ok, uncertain=False, batch_size=1, truncated=0): ...
def get_summary(): ...  # Basic counts
```

### Step 2: Instrument tools.py
Add one line at end of each tool function:
```python
analytics.log_event("run_command", ok="SUCCESS" in result)
```

### Step 3: Add summary tool (optional)
```python
def analytics_summary() -> str:
    """Get usage summary for optimization insights."""
```

---

## Expected Insights

After collecting data, we can answer:
1. "Which tools are never used?" → Remove or document better
2. "Which tools fail often?" → Improve error handling
3. "How often is UNCERTAIN returned?" → Tune hang detection
4. "Are agents using batch commands?" → If not, make more ergonomic
5. "Are outputs being truncated?" → Adjust defaults

---

## Next: Implementation

Create `analytics.py` with ~30 lines of code.

---

*Phase 2 created by TEAM_009 on 2025-12-28*
