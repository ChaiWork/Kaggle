# File: tripforge/agents/profile_agent.py
# Purpose: Manages traveler profile creation, validation, and enrichment.
# Competition Concept: Multi-agent system (ADK)

from google.adk.agents import Agent

def get_profile_agent(model_name: str = "gemini-2.5-flash") -> Agent:
    """
    Creates and returns the ProfileAgent instance configured with system prompt.

    Parameters:
    - model_name: The Gemini model name to use for reasoning.

    Returns:
    An instance of google.adk.agents.Agent.
    """
    instruction = (
        "You are TripForge's Profile Manager. Your job is to take raw traveler preferences "
        "and create a structured, validated traveler profile. "
        "You must analyze the inputs and produce a structured JSON object representing the "
        "traveler profile, followed by a human-readable confirmation summary. "
        "Specifically, verify the following fields and handle them as follows:\n"
        "- destination: Validate that it is one of the supported destinations (Paris, Tokyo, Barcelona, New York, Bali). "
        "Raise an error message if not.\n"
        "- days: Must be between 1 and 30. If missing, default to 7.\n"
        "- travelers: Must be at least 1. If missing, default to 2.\n"
        "- budget: Must be a positive number. If missing, default to 1500.0.\n"
        "- currency: Validate currency string (e.g. USD, EUR, JPY). Default to USD.\n"
        "- start_date: Check format YYYY-MM-DD. If missing, default to a sensible upcoming date (e.g. 2026-08-15).\n"
        "- accessibility_needs: Explicitly check and record accessibility constraints. If not specified, set to None.\n"
        "- dietary_restrictions: Explicitly check and record dietary requirements (e.g. gluten-free, vegan). If not specified, set to None.\n"
        "- travel_style: If not specified, infer it based on budget per person (e.g. budget/days/travelers). "
        "If budget per person per day is > $300, set to 'luxury'; between $100-$300, set to 'mid-range'; < $100, set to 'budget'.\n"
        "- interests: List of travel interests. If missing, default to ['general-sightseeing'].\n\n"
        "Safety Check: You must highlight accessibility and dietary needs explicitly, confirming them as safety-critical.\n\n"
        "Your final response must be formatted as:\n"
        "---PROFILE_JSON---\n"
        "[Insert clean, valid JSON block containing all keys: destination, days, travelers, budget, currency, start_date, accessibility_needs, dietary_restrictions, travel_style, interests]\n"
        "---SUMMARY---\n"
        "[Insert a concise, friendly summary of the travelers, their style, budget, safety needs, and interests that they can confirm]"
    )
    
    return Agent(
        name="ProfileAgent",
        model=model_name,
        description="Validates and enriches traveler preferences into a structured, safety-checked traveler profile.",
        instruction=instruction,
        tools=[]
    )
