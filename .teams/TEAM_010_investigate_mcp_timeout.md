# TEAM_010: Investigate MCP Server Initialization Timeout

**Date:** 2024-12-28
**Bug:** MCP server initialization timed out after 60 seconds

## Bug Report

- **Symptom:** MCP server initialization timed out after 60 seconds
- **Expected:** Server should start and respond within a few seconds
- **Actual:** Server hangs and times out after 60 seconds
- **Context:** This occurred after reorganizing Python files into folders (core/, tools/, utils/, tests/)

## Phase 1: Understanding the Symptom

### Symptom Description
- MCP client (Windsurf/Cursor/Claude) tried to start the server
- Server did not respond within 60 seconds
- Client gave up and reported timeout

### Likely Cause Areas
1. Import errors after file reorganization
2. Server startup blocking on something
3. Module path issues

## Investigation Log

### Test 1: Direct server startup
```
timeout 5 uv run python server.py
```
Result: Times out waiting for stdin (EXPECTED - MCP servers wait for client)

### Test 2: Server with MCP initialization message
```
echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | uv run python server.py
```
Result: **SUCCESS** - Server responds correctly with capabilities

### Test 3: Exact command from Windsurf config
```
uv run --directory /var/home/vince/mcp-servers/android-root python server.py
```
Result: **SUCCESS** - Server responds correctly

## Root Cause Analysis

**The server code is NOT the problem.**

The MCP server works correctly when tested manually. Possible causes:
1. Windsurf needs restart after config change
2. Windsurf environment differs from shell environment
3. Path to `uv` not found by Windsurf

## TEAM_010 BREADCRUMB: RULED_OUT - Server code is working
// Server responds correctly to MCP protocol messages
// Issue is environmental, not code-related

## Recommended Actions

1. **Restart Windsurf** completely (not just reload)
2. If still failing, try using absolute path to uv:
   ```json
   "command": "/home/vince/.local/bin/uv"
   ```
3. Check Windsurf logs for more details
