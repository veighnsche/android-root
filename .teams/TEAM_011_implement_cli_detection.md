# TEAM_011: Implement CLI Detection & Usage Guidance

**Date:** 2024-12-28
**Task:** Implement feedback from TEAM_011 addendum about MCP usage patterns

## Analytics Summary

From `~/.android-shell-mcp/analytics.jsonl` (31 events):
- Mostly `run_commands` usage (batch commands working well)
- High retry rate (suggests debugging workflows)
- Some truncation (output filtering is being used)
- No `file_transfer` events visible (confirms avoidance)

## Changes to Implement

1. **CLI Detection** - Detect project CLIs and suggest them in `list_devices` output
2. **File Transfer Warnings** - Add clear size limits and suggest alternatives
3. **Usage Guidance** - Update tool descriptions

## Implementation Log

### Changes Made

1. **CLI Detection** (`tools/handlers.py`)
   - Added `KNOWN_PROJECT_CLIS` list for registering project CLIs
   - Added `_detect_project_cli()` helper function
   - Updated `list_devices()` to append CLI suggestions when detected

2. **File Transfer Warnings** (`tools/handlers.py`)
   - Added size limit warning in docstring (⚠️ LIMITATION)
   - Added runtime check for content > 1MB
   - Returns helpful error with alternatives (CLI, adb push)

### Files Modified
- `tools/handlers.py` - Added CLI detection and file size warnings

### Verification
- Server starts successfully
- MCP initialization responds correctly

## Handoff Notes

- The `KNOWN_PROJECT_CLIS` list can be extended for other projects
- CLI detection checks hardcoded paths - consider making configurable
- File transfer limit is 1MB - matches MCP content size constraints
