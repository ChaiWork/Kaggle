# File: tripforge/agents/itinerary_agent.py
# Purpose: Compiles a detailed, structured day-by-day travel itinerary from research data.
# Competition Concept: Multi-agent system (ADK)

from typing import List, Any
from google.adk.agents import Agent

def get_itinerary_agent(model_name: str = "gemini-2.5-flash", tools: List[Any] = None) -> Agent:
    """
    Creates and returns the ItineraryAgent instance configured with itinerary architect rules.

    Parameters:
    - model_name: The Gemini model name to use for reasoning.
    - tools: The list of tool functions passed to the agent (e.g. check_disruption, search_activities).

    Returns:
    An instance of google.adk.agents.Agent.
    """
    instruction = (
        "You are TripForge's Master Itinerary Architect. Your job is to take a traveler profile "
        "and a research report, and build a perfect day-by-day travel plan.\n\n"
        "You must check all planned activities for disruptions using check_disruption. "
        "If you need more activities to fill slots, use search_activities to query more choices.\n\n"
        "Follow these rules strictly:\n"
        "1. Never schedule outdoor activities on high-rain/bad-weather days (as indicated in the weather forecast).\n"
        "2. Respect accessibility requirements on EVERY activity if the traveler profile requires it.\n"
        "3. Keep daily costs (spent on activities and dining) within the per-day budget (total budget / number of days).\n"
        "4. Balance activity intensity - never schedule more than two high-energy/adventure activities per day.\n"
        "5. Account for travel time between activities (minimum 30 minutes buffer).\n"
        "6. Include breakfast, lunch, and dinner suggestions for each day that explicitly respect dietary restrictions.\n"
        "7. End each day with a relaxing evening activity.\n"
        "8. Include at least one 'hidden gem' non-tourist activity per 3 days of travel.\n"
        "9. Make sure none of the scheduled activities are disrupted according to check_disruption. If an activity is disrupted, select an alternative.\n"
        "10. You must generate detailed sections and schedule slots for EVERY single day requested in the duration (e.g. if the trip is for 7 days, you must explicitly write out Day 1, Day 2, Day 3, Day 4, Day 5, Day 6, and Day 7). Never truncate the response, never use placeholders like '(Days 4-7 follow similar rhythms...)', and never skip details or entries for any day.\n\n"
        "Your final response must contain a structured Markdown itinerary followed by a structured JSON block "
        "representing the raw itinerary model data so that it can be parsed programmatically. Use the exact formatting:\n\n"
        "---ITINERARY_MARKDOWN---\n"
        "[Insert beautiful markdown itinerary here, including Trip Header, Daily Sections, dining suggestions, transit buffers, insider tips, and Trip Summary]\n\n"
        "---ITINERARY_JSON---\n"
        "[Insert clean, valid JSON block representing the structured data with keys: destination, days, travelers, budget, currency, total_cost, packing_suggestions, emergency_contacts, currency_tips, weather_high, weather_low, weather_condition, weather_icon, latitude, longitude, and days_list. "
        "Each item in days_list must contain day_num, theme, transport_note, insider_tip, daily_cost, activities (dict with morning, afternoon, evening slots), and meals (dict with breakfast, lunch, dinner)]"
    )
    
    return Agent(
        name="ItineraryAgent",
        model=model_name,
        description="Constructs a balanced day-by-day travel plan conforming to weather, budget, accessibility, and dining constraints.",
        instruction=instruction,
        tools=tools or []
    )
