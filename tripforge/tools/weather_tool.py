# File: tripforge/tools/weather_tool.py
# Purpose: Client wrapper for weather tool to query Open-Meteo via MCP.
# Competition Concept: Agent Skills & Tool Execution

import json
from tripforge.utils.security import guard_external_call, sign_tool_call

async def get_weather_tool(city: str, date: str) -> dict:
    """
    Retrieves weather forecast or seasonal climate estimate for a given city and date.

    Parameters:
    - city: Target city name (e.g. Paris).
    - date: Target date in YYYY-MM-DD format.

    Returns:
    A dictionary containing weather forecast details.
    """
    from tripforge import orchestrator
    session = orchestrator._ACTIVE_MCP_SESSION
    if not session:
        raise RuntimeError("MCP Client Session is not active.")
        
    # Security cloud-sync guard
    if not guard_external_call("Open-Meteo Weather API", f"City: {city}, Date: {date}"):
        raise PermissionError("Access to external Open-Meteo API blocked by security guard.")
        
    params = {"city": city, "date": date}
    # Sign call with HMAC signature
    params["signature"] = sign_tool_call("get_weather", params)
    
    res = await session.call_tool("get_weather", params)
    if res.content and len(res.content) > 0:
        return json.loads(res.content[0].text)
    return {}
