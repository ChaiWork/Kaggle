# TripForge Project Rules

All developer agents working on this project must adhere to the following rules:

1. **Subprocess Environment Propagation**:
   - When launching Python subprocesses (e.g. MCP servers via `StdioServerParameters`), always copy `sys.path` to the subprocess's `PYTHONPATH` using `os.pathsep.join` to prevent `ModuleNotFoundError` inside serverless/container environments.

2. **Read-only Filesystem Workarounds**:
   - Serverless hosts (like Vercel) have a read-only filesystem except for `/tmp`.
   - Never let log file write failures crash the app or output error warnings. Catch `OSError` (specifically `errno == 30` for read-only filesystem) and silently ignore it (since stderr is already captured as standard cloud logs).
   - If creating or writing to local workspace directories (like `/scratch` for downloads) fails due to write limits, fall back to the system's temporary directory (`tempfile.gettempdir()`).

3. **Content Security Policy (CSP) for Maps**:
   - When configuring CSP headers in `app.py`, always permit Leaflet map assets to render. Include `unpkg.com` in `style-src` and `script-src`, and permit tile images from CartoDB (`https://*.basemaps.cartocdn.com`) and OpenStreetMap (`https://*.tile.openstreetmap.org`) in `img-src`.

4. **Python 3.12 Regex Constraints**:
   - Do not use double dollar signs `$$` inside Python regex search strings to represent end-of-string boundaries (causes matches at every character position in Python 3.12). Use a single `$` for end-of-string anchors.
