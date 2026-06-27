# File: tripforge/tools/country_info_tool.py
# Purpose: Client wrapper for country info tool to query RestCountries via MCP.
# Competition Concept: Agent Skills & Tool Execution

import json
from tripforge.utils.security import guard_external_call, sign_tool_call

async def get_country_info_tool(country_name: str) -> dict:
    """
    Retrieves travel essentials and essentials for a country using RestCountries API.

    Parameters:
    - country_name: Name of the country.

    Returns:
    A dictionary containing country details.
    """
    from tripforge import orchestrator
    session = orchestrator._ACTIVE_MCP_SESSION
    if not session:
        raise RuntimeError("MCP Client Session is not active.")
        
    # Security cloud-sync guard
    if not guard_external_call("RestCountries API", f"Country: {country_name}"):
        raise PermissionError("Access to external RestCountries API blocked by security guard.")
        
    params = {"country_name": country_name}
    # Sign call with HMAC signature
    params["signature"] = sign_tool_call("get_country_info", params)
    
    res = await session.call_tool("get_country_info", params)
    if res.content and len(res.content) > 0:
        return json.loads(res.content[0].text)
    return {}
