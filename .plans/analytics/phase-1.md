# Phase 1: Discovery — Analytics for MCP Server Optimization

**Team**: TEAM_009
**Feature**: Analytics Database for Android Shell Manager
**Status**: In Progress

---

## 1. Feature Summary

### Problem Statement
We have no visibility into how the MCP server is being used by AI agents. We can't answer:
- Which tools are used most/least?
- What commands fail most often?
- How long do commands take?
- Are agents hitting timeouts? Why?
- What patterns lead to UNCERTAIN status?
- Are there commands that always need retry?

### Who Benefits
- **MCP Developers**: Optimize tool design, reduce friction
- **AI Agents**: Better tool selection, fewer retries
- **Users**: Faster, more reliable automation

### Success Criteria
- [ ] Can answer: "What are the top 10 slowest commands?"
- [ ] Can answer: "What % of commands timeout?"
- [ ] Can answer: "Which tool has the highest failure rate?"
- [ ] Can identify patterns that lead to hangs
- [ ] Data persists across server restarts

---

## 2. What to Analyze

### 2.1 Tool Usage Metrics

| Metric | Why It Matters |
|--------|----------------|
| **Tool call count** | Which tools are popular vs unused |
| **Tool call frequency over time** | Usage patterns, peak times |
| **Tool success/failure rate** | Reliability per tool |
| **Tool latency (p50, p95, p99)** | Performance bottlenecks |
| **Tool parameters used** | Common usage patterns |

### 2.2 Command Execution Metrics

| Metric | Why It Matters |
|--------|----------------|
| **Command duration** | Identify slow commands |
| **Command exit codes** | Failure patterns |
| **Command timeout rate** | Hang detection effectiveness |
| **Output size (bytes/lines)** | Context window pressure |
| **Truncation rate** | Are limits working? |
| **UNCERTAIN status rate** | AI decision points |

### 2.3 Shell Session Metrics

| Metric | Why It Matters |
|--------|----------------|
| **Session duration** | How long shells stay open |
| **Commands per session** | Batch efficiency |
| **Session failure rate** | Connection stability |
| **Root vs non-root usage** | Permission patterns |
| **Device distribution** | Multi-device usage |

### 2.4 Error & Recovery Metrics

| Metric | Why It Matters |
|--------|----------------|
| **Error types** | Categorize failures |
| **Recovery success rate** | Is multi-stage interrupt working? |
| **Prompt detection accuracy** | False positive/negative rate |
| **Retry patterns** | Agent behavior after failures |

### 2.5 AI Agent Behavior Metrics

| Metric | Why It Matters |
|--------|----------------|
| **Tool call sequences** | Common workflows |
| **Time between tool calls** | Agent thinking time |
| **Batch vs single command ratio** | Is run_commands being used? |
| **grep/filter usage** | Output limiting adoption |

---

## 3. Data Collection Points

### 3.1 Entry Points (where to instrument)

```
tools.py
├── Each @mcp.tool() function
│   ├── START: timestamp, tool_name, parameters
│   └── END: duration, status, output_size, error

manager.py
├── run_in_shell()
│   ├── Command start/end
│   └── Exit code, output stats
├── run_commands_batch()
│   ├── Batch size, per-command stats
│   └── Stop-on-error triggers
└── Shell lifecycle
    ├── connect/disconnect events
    └── Session duration

shell.py
├── run_command()
│   ├── Timeout events
│   ├── UNCERTAIN triggers
│   ├── Prompt detection events
│   └── Recovery attempts
└── Hang detection
    ├── Slow command classification
    └── False positive indicators
```

### 3.2 Data Schema (Draft)

```json
{
  "event_type": "tool_call | command | session | error",
  "timestamp": "2025-12-28T13:35:00Z",
  "tool_name": "run_commands",
  "shell_id": "xxx",
  "device_serial": "yyy",
  
  "duration_ms": 1234,
  "status": "success | failed | timeout | uncertain",
  "exit_code": 0,
  
  "input": {
    "command_count": 3,
    "total_chars": 150
  },
  "output": {
    "lines": 50,
    "chars": 2000,
    "truncated": true
  },
  
  "metadata": {
    "is_root": true,
    "slow_command_detected": false,
    "prompt_detected": null,
    "recovery_attempted": false
  }
}
```

---

## 4. Storage Options

### Option A: SQLite (Simple, Local)
- **Pros**: Zero setup, file-based, SQL queries
- **Cons**: Not designed for time-series, no built-in aggregations

### Option B: TinyDB (Python NoSQL)
- **Pros**: Pure Python, document-based, simple
- **Cons**: Not optimized for analytics queries

### Option C: InfluxDB (Time-Series)
- **Pros**: Built for metrics, excellent queries, retention policies
- **Cons**: External dependency, more complex setup

### Option D: Local JSON + Periodic Aggregation
- **Pros**: Simplest, no dependencies
- **Cons**: Manual aggregation, no real-time queries

### Recommendation
Start with **SQLite** for simplicity. Can migrate to InfluxDB later if needed.

---

## 5. Questions for User

Before proceeding to Phase 2 (Design), we need answers to:

### Q1: Storage Priority
What's more important?
- (A) Zero external dependencies (SQLite/TinyDB)
- (B) Best analytics capabilities (InfluxDB)
- (C) Simplest possible (JSON files)

### Q2: Retention Policy
How long should we keep detailed data?
- (A) Forever (disk space permitting)
- (B) 7 days detailed, then aggregate
- (C) 30 days detailed, then aggregate
- (D) Only keep aggregates, not raw events

### Q3: Real-time vs Batch
Do we need real-time dashboards?
- (A) Yes, need live metrics
- (B) No, periodic reports are fine
- (C) Just need queryable data for debugging

### Q4: Privacy Concerns
Should we store actual command strings?
- (A) Yes, full commands (may contain sensitive data)
- (B) Only command patterns (e.g., "ls *", "cat <file>")
- (C) No commands, only metrics

### Q5: Priority Metrics
Rank these by importance (1=highest):
- [ ] Tool usage frequency
- [ ] Command latency
- [ ] Error/failure rates
- [ ] Agent behavior patterns
- [ ] Output size/truncation

---

## 6. Next Steps

1. **Get answers to Q1-Q5** from user
2. **Create Phase 2** with detailed design based on answers
3. **Design analytics schema** for chosen storage
4. **Plan instrumentation** without breaking existing code
5. **Design aggregation/query layer**

---

*Phase 1 created by TEAM_009 on 2025-12-28*
