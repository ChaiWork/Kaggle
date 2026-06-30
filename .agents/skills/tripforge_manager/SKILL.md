---
name: "tripforge_manager"
description: "Triggers when editing, testing, debugging, or managing the TripForge travel concierge system."
---

# TripForge Manager Skill

This skill provides context and guidelines for managing, testing, and developing the TripForge travel planner.

## Architectural Core
TripForge links Google's Agent Development Kit (ADK) with a Model Context Protocol (MCP) server:
- **Flask Server**: App entrypoint at [app.py](file:///d:/codingProject/GITHUB/Kaggle/app.py).
- **Multi-Agent Orchestrator**: Async pipeline at [orchestrator.py](file:///d:/codingProject/GITHUB/Kaggle/tripforge/orchestrator.py).
- **MCP Travel Server**: Standalone subprocess at [travel_tools_server.py](file:///d:/codingProject/GITHUB/Kaggle/tripforge/mcp_server/travel_tools_server.py).
- **Security & Encryption**: Utilities at [security.py](file:///d:/codingProject/GITHUB/Kaggle/tripforge/utils/security.py).

---

## Development & Debugging Rules

### 1. Compile Check
Before completing any changes, always run a compilation verification check to ensure no syntax errors are present:
```bash
python -m py_compile app.py tripforge/orchestrator.py
```

### 2. Subprocess PYTHONPATH Propagation
When launching the MCP subprocess via `StdioServerParameters`, the child process must inherit all parent process import search paths to resolve third-party packages (like `httpx`). Always combine `base_dir` and the parent's `sys.path` and set it as `PYTHONPATH` using the platform-specific separator:
```python
python_path_dirs = [base_dir] + [p for p in sys.path if p]
```

### 3. Read-only Filesystem Compatibility (e.g. Vercel)
Vercel/Lambda filesystems are read-only except for `/tmp`.
- **Logs**: If writing to `tripforge.log` raises an `OSError` with `errno == 30` (read-only filesystem), silently ignore the write failure. Logs are already outputted to `sys.stderr` and captured automatically by the hosting platform console.
- **Downloads**: If creating or writing to the local `/scratch` directory fails, fall back to the system's temporary directory (`tempfile.gettempdir()`).

### 4. Regex Parsing Boundaries
Never use `$$` for end-of-string matching inside Python regexes. Python 3.12 evaluates `$$` as a zero-width match at every position in the string, which causes non-greedy searches to match empty strings. Use a single `$` for end-of-string matching, and employ lenient patterns (case-insensitive, optional dashes) to match structured outputs reliably.
