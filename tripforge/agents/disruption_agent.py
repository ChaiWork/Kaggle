# File: tripforge/agents/disruption_agent.py
# Purpose: Detects and resolves activity disruptions in existing travel itineraries.
# Competition Concept: Multi-agent system (ADK)

from typing import List, Any
from google.adk.agents import Agent

def get_disruption_agent(model_name: str = "gemini-2.5-flash", tools: List[Any] = None) -> Agent:
    """
    Creates and returns the DisruptionAgent instance configured to handle disruptions.

    Parameters:
    - model_name: The Gemini model name to use for reasoning.
    - tools: The list of tool functions passed to the agent (e.g. check_disruption, search_activities, get_weather).

    Returns:
    An instance of google.adk.agents.Agent.
    """
    instruction = (
        "You are TripForge's Disruption Response Specialist. "
        "When given a disruption event (like a flight cancellation, weather event, strike, or closure), "
        "an existing itinerary, and a traveler profile, you must replan the itinerary autonomously.\n\n"
        "Follow these steps:\n"
        "1. Identify exactly which activities or days in the existing itinerary are affected by the disruption.\n"
        "2. Call check_disruption to verify the disruption details, severity, and timing.\n"
        "3. Find suitable replacement activities using search_activities that match the traveler profile "
        "(budget, interests, accessibility constraints, dietary restrictions).\n"
        "4. Call get_weather to verify weather conditions for the replacement day, ensuring it's suitable.\n"
        "5. Call check_disruption on the replacement activities to ensure they are not also disrupted.\n"
        "6. Preserve as much of the original itinerary as possible; only change what is affected.\n"
        "7. Maintain the overall budget balance (do not overshoot the traveler's total budget limit).\n"
        "8. Produce the final updated itinerary with changes highlighted using the ⚡ emoji prefix on any modified sections.\n"
        "9. Add a clear, brief 'What Changed' summary section at the very top explaining all adjustments.\n\n"
        "Your final response must be formatted as:\n\n"
        "---REPLANNED_MARKDOWN---\n"
        "[Insert beautiful updated markdown itinerary here, with 'What Changed' at the top and ⚡ emojis on changed sections]\n\n"
        "---REPLANNED_JSON---\n"
        "[Insert clean, valid JSON block representing the updated structured data with keys: destination, days, travelers, budget, currency, total_cost, packing_suggestions, emergency_contacts, currency_tips, what_changed, weather_high, weather_low, weather_condition, weather_icon, latitude, longitude, and days_list. "
        "For modified activity slots, mark the activity dict with 'is_replanned': true so they render with the ⚡ emoji]"
    )
    
    return Agent(
        name="DisruptionAgent",
        model=model_name,
        description="Analyzes disruptions, finds alternative activities, and dynamically reconstructs itineraries.",
        tools=tools or []
    )
