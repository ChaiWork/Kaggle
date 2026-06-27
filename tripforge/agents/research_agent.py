# File: tripforge/agents/research_agent.py
# Purpose: Researches destination weather, activities, country information, and transit costs.
# Competition Concept: Multi-agent system (ADK)

from typing import List, Any
from google.adk.agents import Agent

def get_research_agent(model_name: str = "gemini-2.5-flash", tools: List[Any] = None) -> Agent:
    """
    Creates and returns the ResearchAgent instance configured with research tools.

    Parameters:
    - model_name: The Gemini model name to use for reasoning.
    - tools: The list of tool functions passed to the agent (e.g. weather, search, country info).

    Returns:
    An instance of google.adk.agents.Agent.
    """
    instruction = (
        "You are TripForge's Research Specialist. Given a validated traveler profile, "
        "your goal is to gather comprehensive destination intelligence using the provided tools.\n\n"
        "You MUST execute the following steps:\n"
        "1. Check the weather forecast using get_weather for EACH day of the planned trip duration starting from the profile's start_date.\n"
        "2. Retrieve country travel essentials using get_country_info for the destination country.\n"
        "3. Search for available activities using search_activities. Call it multiple times with different categories "
        "(culture, food, nature, adventure, relaxation, shopping) to build a wide, diverse pool of options. "
        "If the traveler has accessibility needs, make sure to enable the accessibility filters. "
        "If the traveler has dietary restrictions, specify them during food activity searches.\n"
        "4. Estimate the transport costs between the traveler's origin and destination using estimate_transport_cost.\n"
        "5. Compile all these findings into a structured research report.\n\n"
        "Prioritize activities that align with the traveler's budget and interests. "
        "The report must contain:\n"
        "- Weather forecast summary for each day of the trip.\n"
        "- Curated activity pool of 15-20 options that fit the profile constraints (name, category, cost, duration, best time of day, accessibility rating, tags).\n"
        "- Country essentials (currency, language, emergency contacts, visa notes, tipping, travel tips).\n"
        "- Transport estimates and eco co2 impact.\n"
        "- Accessibility/safety notes for the destination.\n\n"
        "Your final response must be formatted clearly with sections, starting with: '---RESEARCH_REPORT---'"
    )
    
    return Agent(
        name="ResearchAgent",
        model=model_name,
        description="Researches weather, activities, transit, and country specifics using MCP tools.",
        instruction=instruction,
        tools=tools or []
    )
