# File: tripforge/tools/activities_tool.py
# Purpose: Client wrapper for activities search tool to query the local database via MCP.
# Competition Concept: Agent Skills & Tool Execution

import json
from tripforge.utils.security import sign_tool_call

async def search_activities_tool(
    city: str, 
    accessibility_required: bool = False, 
    dietary_preference: str = None, 
    category: str = None
) -> list:
    """
    Search and filter local activities from the database via MCP.

    Parameters:
    - city: Target city name.
    - accessibility_required: True if wheelchair accessibility is required.
    - dietary_preference: Optional dietary restriction.
    - category: Optional category filter.

    Returns:
    A list of matching activities.
    """
    from tripforge import orchestrator
    session = orchestrator._ACTIVE_MCP_SESSION
    if not session:
        raise RuntimeError("MCP Client Session is not active.")
        
    params = {
        "city": city, 
        "accessibility_required": accessibility_required, 
        "dietary_preference": dietary_preference, 
        "category": category
    }
    # Sign call with HMAC signature
    params["signature"] = sign_tool_call("search_activities", params)
    
    res = await session.call_tool("search_activities", params)
    if res.content and len(res.content) > 0:
        return json.loads(res.content[0].text)
    return []
