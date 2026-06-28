# File: tripforge/mcp_server/travel_tools_server.py
# Competition Concept: MCP Server
# Purpose: Expose travel research tools to the ADK Agents via Model Context Protocol

import os
import sys
import json
import asyncio
from datetime import datetime, date as date_type
import httpx
import logging
from mcp.server.fastmcp import FastMCP

# Force all logging to stderr to prevent stdio transport corruption
logging.basicConfig(level=logging.INFO, stream=sys.stderr, force=True)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Initialize FastMCP Server
mcp = FastMCP("TripForge-Travel-Tools")

# Helpers for logging
def log_event(action: str, message: str):
    """Logs tool calls with timestamps and parameters to stderr to avoid corrupting stdio transport."""
    timestamp = datetime.now().isoformat()
    sys.stderr.write(f"[{timestamp}] [MCP_SERVER] [{action}] {message}\n")
    sys.stderr.flush()

# Hardcoded coordinates for the 5 primary cities
PRIMARY_COORDINATES = {
    "paris": {"lat": 48.8566, "lon": 2.3522, "country": "France"},
    "tokyo": {"lat": 35.6762, "lon": 139.6503, "country": "Japan"},
    "barcelona": {"lat": 41.3851, "lon": 2.1734, "country": "Spain"},
    "new york": {"lat": 40.7128, "lon": -74.0060, "country": "USA"},
    "bali": {"lat": -8.4095, "lon": 115.1889, "country": "Indonesia"}
}

# Seasonal climates for fallback weather
SEASONAL_CLIMATE = {
    "paris": {
        "spring": {"high": 15, "low": 7, "precip": 30, "cond": "Partly Cloudy", "suitable": True},
        "summer": {"high": 25, "low": 15, "precip": 20, "cond": "Sunny", "suitable": True},
        "autumn": {"high": 16, "low": 9, "precip": 45, "cond": "Rainy", "suitable": False},
        "winter": {"high": 8, "low": 3, "precip": 40, "cond": "Cloudy", "suitable": False}
    },
    "tokyo": {
        "spring": {"high": 18, "low": 10, "precip": 25, "cond": "Sunny", "suitable": True},
        "summer": {"high": 28, "low": 22, "precip": 35, "cond": "Humid/Rainy", "suitable": True},
        "autumn": {"high": 20, "low": 13, "precip": 30, "cond": "Clear", "suitable": True},
        "winter": {"high": 10, "low": 3, "precip": 15, "cond": "Cold/Sunny", "suitable": True}
    },
    "barcelona": {
        "spring": {"high": 19, "low": 12, "precip": 20, "cond": "Sunny", "suitable": True},
        "summer": {"high": 28, "low": 21, "precip": 10, "cond": "Sunny", "suitable": True},
        "autumn": {"high": 21, "low": 14, "precip": 30, "cond": "Partly Cloudy", "suitable": True},
        "winter": {"high": 14, "low": 8, "precip": 25, "cond": "Cool/Sunny", "suitable": True}
    },
    "new york": {
        "spring": {"high": 16, "low": 8, "precip": 35, "cond": "Showers", "suitable": True},
        "summer": {"high": 28, "low": 20, "precip": 25, "cond": "Sunny", "suitable": True},
        "autumn": {"high": 17, "low": 10, "precip": 30, "cond": "Clear", "suitable": True},
        "winter": {"high": 4, "low": -2, "precip": 35, "cond": "Snowy", "suitable": False}
    },
    "bali": {
        "spring": {"high": 31, "low": 25, "precip": 40, "cond": "Humid/Showers", "suitable": True},
        "summer": {"high": 30, "low": 24, "precip": 15, "cond": "Sunny", "suitable": True},
        "autumn": {"high": 31, "low": 25, "precip": 30, "cond": "Sunny", "suitable": True},
        "winter": {"high": 31, "low": 25, "precip": 60, "cond": "Tropical Showers", "suitable": False}
    }
}

# Country info local fallback database
COUNTRY_INFO_FALLBACK = {
    "france": {
        "currency": "EUR",
        "language": "French",
        "timezone": "UTC+1",
        "emergency_numbers": {"police": "17", "ambulance": "15", "general": "112"},
        "visa_requirements_note": "Schengen Area rules apply. 90-day tourist visa-free for US, Canada, Australia, etc.",
        "tipping_culture": "Service is included in the bill. Rounding up 5-10% for good service is appreciated.",
        "useful_travel_tips": "Validate your metro tickets before boarding. Speak softly in restaurants. Say 'Bonjour' when entering shops."
    },
    "japan": {
        "currency": "JPY",
        "language": "Japanese",
        "timezone": "UTC+9",
        "emergency_numbers": {"police": "110", "ambulance": "119", "general": "110"},
        "visa_requirements_note": "90-day visa exemption for most tourists. Passports must be valid for the duration of stay.",
        "tipping_culture": "No tipping. Tipping is considered insulting or awkward. Excellent service is standard.",
        "useful_travel_tips": "Carry cash as smaller shops don't accept cards. Take your trash home. Stand on the left of escalators in Tokyo."
    },
    "spain": {
        "currency": "EUR",
        "language": "Spanish, Catalan",
        "timezone": "UTC+1",
        "emergency_numbers": {"police": "091", "ambulance": "061", "general": "112"},
        "visa_requirements_note": "Schengen Area rules apply. Passports must have at least 3 months validity beyond stay.",
        "tipping_culture": "5-10% is customary in sit-down restaurants if service is good. Not expected for cafes or bars.",
        "useful_travel_tips": "Lunch is typically at 2:00 PM and dinner at 9:30 PM. Siesta runs 2:00 PM to 5:00 PM for smaller shops."
    },
    "usa": {
        "currency": "USD",
        "language": "English",
        "timezone": "UTC-5 to UTC-8",
        "emergency_numbers": {"police": "911", "ambulance": "911", "general": "911"},
        "visa_requirements_note": "ESTA electronic travel authorization is required for Visa Waiver Program countries.",
        "tipping_culture": "15-20% is standard and expected for restaurant service, taxis, and bars.",
        "useful_travel_tips": "Prices in shops exclude sales tax, which is added at the register. Jaywalking can result in fines."
    },
    "indonesia": {
        "currency": "IDR",
        "language": "Indonesian, Balinese",
        "timezone": "UTC+8",
        "emergency_numbers": {"police": "110", "ambulance": "118", "general": "112"},
        "visa_requirements_note": "Visa on Arrival (VoA) required for most passports ($35 USD for 30 days).",
        "tipping_culture": "Not mandatory, but 5-10% is highly appreciated by drivers and restaurant staff.",
        "useful_travel_tips": "Drink bottled water only. Dress modestly when visiting temples (wear a sarong). Carry insect repellent."
    },
    "malaysia": {
        "currency": "MYR",
        "language": "Malay, English",
        "timezone": "UTC+8",
        "emergency_numbers": {"police": "999", "ambulance": "999", "general": "999"},
        "visa_requirements_note": "Most nationalities enjoy 30 to 90 days visa-free entry. Must fill in MDAC (Malaysia Digital Arrival Card) 3 days before arrival.",
        "tipping_culture": "Tipping is not customary. A 10% service charge is usually added to bills in restaurants.",
        "useful_travel_tips": "Remove your shoes before entering homes and places of worship. Dress modestly when visiting mosques. Use your right hand to shake hands or eat."
    }
}

# Transport cost lookup table
TRANSPORT_TABLE = {
    ("new york", "paris"): {
        "flight": {"cost": 650, "duration": 7.5, "tip": "Book 3 months in advance. Choose overnight flight to adapt to timezone.", "co2": 620},
        "train": {"cost": None, "duration": None, "tip": "No land route available between USA and Europe.", "co2": None},
        "bus": {"cost": None, "duration": None, "tip": "No land route available between USA and Europe.", "co2": None}
    },
    ("paris", "barcelona"): {
        "flight": {"cost": 60, "duration": 1.7, "tip": "Budget carriers are cheap but strict on baggage limits. Check airport distance.", "co2": 140},
        "train": {"cost": 85, "duration": 6.5, "tip": "Direct TGV/Renfe train is highly scenic, comfortable, and environmentally friendly.", "co2": 11},
        "bus": {"cost": 35, "duration": 14.0, "tip": "Overnight bus is cheap but tiring. Good for strict budgets.", "co2": 28}
    },
    ("tokyo", "bali"): {
        "flight": {"cost": 500, "duration": 7.5, "tip": "Garuda Indonesia offers direct flights. Book mid-week for cheaper fares.", "co2": 580},
        "train": {"cost": None, "duration": None, "tip": "No rail connection available between Japan and Indonesia.", "co2": None},
        "bus": {"cost": None, "duration": None, "tip": "No road connection available between Japan and Indonesia.", "co2": None}
    }
}

# Disruption simulator lookup
DISRUPTION_LOOKUP = {
    "louvre": {
        "reason": "Closed due to national museum staff labor strike.",
        "severity": "high",
        "dates": ["2025-08-17", "2026-08-17", "2026-06-27", "2026-06-28"]
    },
    "eiffel": {
        "reason": "Elevator maintenance on upper levels. Only stairs to second floor open.",
        "severity": "medium",
        "dates": ["2025-08-16", "2026-08-16"]
    },
    "tablao de carmen": {
        "reason": "Temporary evening electrical maintenance in the theater district.",
        "severity": "high",
        "dates": ["2025-08-20"]
    },
    "sacred monkey": {
        "reason": "Routine wildlife veterinary check. Some pathways restricted.",
        "severity": "low",
        "dates": ["2026-06-30"]
    }
}

@mcp.tool()
async def get_weather(city: str, date: str) -> dict:
    """
    Fetches weather forecast or seasonal estimate for a given city and date.

    Parameters:
    - city: The name of the city (e.g., Paris, Tokyo).
    - date: Target date in YYYY-MM-DD format.

    Returns:
    A dictionary containing temperature_high, temperature_low, precipitation_chance,
    condition, and suitable_for_outdoor.
    """
    log_event("CALL", f"get_weather(city={city}, date={date})")
    
    city_clean = city.strip().lower()
    
    # Check if we are in mock mode
    is_mock = os.getenv("TRIPFORGE_MODE", "live").lower() == "mock"
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        today = date_type.today()
        days_diff = (target_date - today).days
    except ValueError as e:
        log_event("ERROR", f"Invalid date format: {date}")
        return {"error": f"Invalid date format. Use YYYY-MM-DD. Error: {str(e)}"}

    # Fallback to seasonal climate if requested is more than 16 days out (or in mock mode)
    if is_mock or days_diff < 0 or days_diff > 16:
        log_event("INFO", f"Date {date} out of forecast range (0-16 days). Using seasonal climate estimates.")
        
        # Determine season based on month
        month = target_date.month
        if month in [12, 1, 2]:
            season = "winter"
        elif month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        else:
            season = "autumn"
            
        city_key = next((k for k in SEASONAL_CLIMATE if k in city_clean), "paris")
        climate = SEASONAL_CLIMATE[city_key][season]
        
        result = {
            "temperature_high": climate["high"],
            "temperature_low": climate["low"],
            "precipitation_chance": climate["precip"],
            "condition": climate["cond"],
            "suitable_for_outdoor": climate["suitable"],
            "source": "historical_seasonal_climate"
        }
        log_event("RESPONSE", json.dumps(result))
        return result

    # Live Mode - Call Open-Meteo
    try:
        # Get coordinates
        lat, lon = 48.8566, 2.3522 # Default to Paris
        found_coord = False
        for name, coords in PRIMARY_COORDINATES.items():
            if name in city_clean:
                lat, lon = coords["lat"], coords["lon"]
                found_coord = True
                break
                
        if not found_coord:
            # Dynamically geocode using Open-Meteo Free Geocoding API
            log_event("API_CALL", f"Geocoding city: {city}")
            geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
            async with httpx.AsyncClient() as client:
                res = await client.get(geocode_url, timeout=10.0)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("results"):
                        lat = data["results"][0]["latitude"]
                        lon = data["results"][0]["longitude"]
                        log_event("INFO", f"Geocoded {city} to lat={lat}, lon={lon}")
                    else:
                        log_event("WARNING", f"Geocode search returned no results for {city}. Using default Paris coordinates.")
                else:
                    log_event("WARNING", f"Geocode API returned status {res.status_code}. Using default Paris coordinates.")
                    
        # Fetch weather from Open-Meteo
        log_event("API_CALL", f"Fetching forecast from Open-Meteo for lat={lat}, lon={lon}")
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            f"&timezone=auto&start_date={date}&end_date={date}"
        )
        
        async with httpx.AsyncClient() as client:
            res = await client.get(weather_url, timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                daily = data.get("daily", {})
                if daily and daily.get("temperature_2m_max"):
                    temp_high = daily["temperature_2m_max"][0]
                    temp_low = daily["temperature_2m_min"][0]
                    precip_prob = daily.get("precipitation_probability_max", [0])[0]
                    wcode = daily.get("weather_code", [0])[0]
                    
                    # Map weather code to condition
                    if wcode == 0:
                        cond = "Sunny"
                    elif wcode in [1, 2, 3]:
                        cond = "Partly Cloudy"
                    elif wcode in [45, 48]:
                        cond = "Foggy"
                    elif wcode in [51, 53, 55]:
                        cond = "Drizzle"
                    elif wcode in [61, 63, 65]:
                        cond = "Rainy"
                    elif wcode in [71, 73, 75]:
                        cond = "Snowy"
                    elif wcode in [80, 81, 82]:
                        cond = "Showers"
                    else:
                        cond = "Overcast"
                        
                    suitable = precip_prob < 50 and temp_high > 5
                    
                    result = {
                        "temperature_high": temp_high,
                        "temperature_low": temp_low,
                        "precipitation_chance": precip_prob,
                        "condition": cond,
                        "suitable_for_outdoor": suitable,
                        "source": "open_meteo_live"
                    }
                    log_event("RESPONSE", json.dumps(result))
                    return result
            
            # If API fails, raise exception to trigger fallback
            raise httpx.HTTPStatusError("API request failed", request=res.request, response=res)
            
    except Exception as e:
        log_event("WARNING", f"Failed to get live weather for {city} on {date}: {str(e)}. Falling back to seasonal data.")
        # Fallback to seasonal
        month = target_date.month
        season = "winter" if month in [12, 1, 2] else "spring" if month in [3, 4, 5] else "summer" if month in [6, 7, 8] else "autumn"
        city_key = next((k for k in SEASONAL_CLIMATE if k in city_clean), "paris")
        climate = SEASONAL_CLIMATE[city_key][season]
        result = {
            "temperature_high": climate["high"],
            "temperature_low": climate["low"],
            "precipitation_chance": climate["precip"],
            "condition": climate["cond"],
            "suitable_for_outdoor": climate["suitable"],
            "source": "fallback_seasonal_climate"
        }
        log_event("RESPONSE", json.dumps(result))
        return result

@mcp.tool()
async def search_activities(
    city: str, 
    accessibility_required: bool = False, 
    dietary_preference: str | None = None, 
    category: str | None = None
) -> list:
    """
    Search and filter local activities from the database.

    Parameters:
    - city: Target city name (Paris, Tokyo, Barcelona, New York, Bali).
    - accessibility_required: True if wheelchair accessibility is required.
    - dietary_preference: Optional dietary restriction (e.g., gluten-free, vegan, halal).
    - category: Optional category filter (culture, food, nature, adventure, relaxation, shopping).

    Returns:
    A list of matching activities.
    """
    log_event("CALL", f"search_activities(city={city}, accessibility={accessibility_required}, dietary={dietary_preference}, category={category})")
    
    city_clean = city.strip().lower()
    
    # Path to local activities file
    # Look for it first in the project directory, and also support relative imports
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, "data", "activities_db.json")
    
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            activities = json.load(f)
    except Exception as e:
        log_event("ERROR", f"Failed to load activities database at {db_path}: {str(e)}")
        return []

    filtered = []
    for act in activities:
        # 1. City Match
        if city_clean not in act["city"].lower():
            continue
            
        # 2. Accessibility Match
        if accessibility_required and not act.get("wheelchair_accessible", False):
            continue
            
        # 3. Category Match
        if category and category.strip().lower() != act.get("category", "").lower():
            continue
            
        # 4. Dietary Match
        if dietary_preference:
            pref_clean = dietary_preference.strip().lower()
            # If the activity category is 'food', check if it supports the diet options
            if act.get("category") == "food":
                options = [o.lower() for o in act.get("dietary_options", [])]
                if pref_clean not in options:
                    continue
                    
        # Format the item for return (as specified)
        # Returns: list of activities with name, description, duration_hours, cost_per_person, accessibility_rating, dietary_friendly, best_time_of_day, category
        # If the dietary options exist, list them or mark as compatible
        diet_friendly = True if not dietary_preference else (dietary_preference.lower() in [o.lower() for o in act.get("dietary_options", [])])
        
        item = {
            "id": act.get("id"),
            "name": act.get("name"),
            "description": act.get("description"),
            "duration_hours": act.get("duration_hours"),
            "cost_per_person": act.get("cost_per_person"),
            "accessibility_rating": act.get("accessibility_rating"),
            "dietary_friendly": diet_friendly,
            "dietary_options": act.get("dietary_options", []),
            "wheelchair_accessible": act.get("wheelchair_accessible", False),
            "best_time_of_day": act.get("best_time_of_day"),
            "category": act.get("category"),
            "insider_tip": act.get("insider_tip", ""),
            "tags": act.get("tags", [])
        }
        filtered.append(item)
        
    if not filtered:
        target_name = city.title()
        fallbacks = [
            {
                "id": f"{city_clean}_landmark_tour",
                "city": target_name,
                "country": "Unknown",
                "name": f"Historic Landmarks & Architecture Walk in {target_name}",
                "description": f"Explore the most famous landmarks, squares, and historic buildings around the center of {target_name}.",
                "category": "culture",
                "duration_hours": 3.0,
                "cost_per_person": 20.0,
                "currency": "USD",
                "accessibility_rating": "full",
                "wheelchair_accessible": True,
                "dietary_options": [],
                "best_time_of_day": "morning",
                "insider_tip": "Book early in the morning to avoid midday crowds and capture the best lighting.",
                "tags": ["culture", "sightseeing", "guided"]
            },
            {
                "id": f"{city_clean}_food_tasting",
                "city": target_name,
                "country": "Unknown",
                "name": f"Local Street Food & Culinary Tasting Experience",
                "description": f"Dive into the authentic food stalls and markets of {target_name} to taste traditional delicacies.",
                "category": "food",
                "duration_hours": 2.5,
                "cost_per_person": 35.0,
                "currency": "USD",
                "accessibility_rating": "partial",
                "wheelchair_accessible": True,
                "dietary_options": ["vegetarian", "vegan", "halal", "gluten-free"],
                "best_time_of_day": "evening",
                "insider_tip": "Come hungry! Try the local specialty recommendations from the vendors.",
                "tags": ["food", "dining", "local"]
            },
            {
                "id": f"{city_clean}_nature_escape",
                "city": target_name,
                "country": "Unknown",
                "name": f"Scenic Nature Park & Botanical Garden Tour",
                "description": f"Stroll through the lush botanical gardens, nature trails, and green reserves of {target_name}.",
                "category": "nature",
                "duration_hours": 4.0,
                "cost_per_person": 10.0,
                "currency": "USD",
                "accessibility_rating": "full",
                "wheelchair_accessible": True,
                "dietary_options": [],
                "best_time_of_day": "afternoon",
                "insider_tip": "Bring sunscreen, a bottle of water, and comfortable walking shoes.",
                "tags": ["nature", "outdoors", "scenic"]
            },
            {
                "id": f"{city_clean}_museum_visit",
                "city": target_name,
                "country": "Unknown",
                "name": f"National Museum & Art Exhibition",
                "description": f"Learn the history, heritage, and contemporary art culture of the region in the premier museum.",
                "category": "culture",
                "duration_hours": 2.0,
                "cost_per_person": 15.0,
                "currency": "USD",
                "accessibility_rating": "full",
                "wheelchair_accessible": True,
                "dietary_options": [],
                "best_time_of_day": "afternoon",
                "insider_tip": "The audio guide is included with ticket purchase; don't forget to ask for it.",
                "tags": ["indoor", "museum", "art"]
            },
            {
                "id": f"{city_clean}_spa_wellness",
                "city": target_name,
                "country": "Unknown",
                "name": f"Traditional Wellness Massage & Spa Retreat",
                "description": f"Relax with a premium therapeutic massage and bath using locally sourced essential oils.",
                "category": "relaxation",
                "duration_hours": 2.0,
                "cost_per_person": 50.0,
                "currency": "USD",
                "accessibility_rating": "full",
                "wheelchair_accessible": True,
                "dietary_options": [],
                "best_time_of_day": "evening",
                "insider_tip": "Drink the hot ginger tea provided at the end of the session to relax your muscles.",
                "tags": ["indoor", "relaxation", "wellness"]
            }
        ]
        
        for act in fallbacks:
            if accessibility_required and not act.get("wheelchair_accessible", False):
                continue
            if category and category.strip().lower() != act.get("category", "").lower():
                continue
            if dietary_preference:
                pref_clean = dietary_preference.strip().lower()
                if act.get("category") == "food":
                    options = [o.lower() for o in act.get("dietary_options", [])]
                    if pref_clean not in options:
                        continue
            
            diet_friendly = True if not dietary_preference else (dietary_preference.lower() in [o.lower() for o in act.get("dietary_options", [])])
            item = {
                "id": act.get("id"),
                "name": act.get("name"),
                "description": act.get("description"),
                "duration_hours": act.get("duration_hours"),
                "cost_per_person": act.get("cost_per_person"),
                "accessibility_rating": act.get("accessibility_rating"),
                "dietary_friendly": diet_friendly,
                "dietary_options": act.get("dietary_options", []),
                "wheelchair_accessible": act.get("wheelchair_accessible", False),
                "best_time_of_day": act.get("best_time_of_day"),
                "category": act.get("category"),
                "insider_tip": act.get("insider_tip", ""),
                "tags": act.get("tags", [])
            }
            filtered.append(item)
            
    log_event("RESPONSE", f"Found {len(filtered)} activities matching filters.")
    return filtered

@mcp.tool()
async def get_country_info(country_name: str) -> dict:
    """
    Retrieves travel essentials for a country using RestCountries API.

    Parameters:
    - country_name: Name of the country (e.g. France, Japan, Spain, United States, Indonesia).

    Returns:
    A dictionary containing currency, language, timezone, emergency_numbers,
    visa_requirements_note, tipping_culture, and useful_travel_tips.
    """
    log_event("CALL", f"get_country_info(country_name={country_name})")
    
    country_clean = country_name.strip().lower()
    is_mock = os.getenv("TRIPFORGE_MODE", "live").lower() == "mock"
    
    # Handle country name variations
    mapped_country = "france"
    if "japan" in country_clean:
        mapped_country = "japan"
    elif "spain" in country_clean:
        mapped_country = "spain"
    elif "usa" in country_clean or "united states" in country_clean:
        mapped_country = "usa"
    elif "indonesia" in country_clean or "bali" in country_clean:
        mapped_country = "indonesia"
    elif "malaysia" in country_clean:
        mapped_country = "malaysia"
        
    # Check if we are in mock mode
    if is_mock:
        log_event("INFO", f"Returning mock country info for {mapped_country}")
        result = COUNTRY_INFO_FALLBACK[mapped_country]
        log_event("RESPONSE", json.dumps(result))
        return result

    # Live Mode - Call RestCountries API
    try:
        log_event("API_CALL", f"Calling restcountries.com for {country_name}")
        url = f"https://restcountries.com/v3.1/name/{country_name}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=10.0)
            if res.status_code == 200:
                data = res.json()[0]
                
                # Extract currency
                currencies = data.get("currencies", {})
                curr_code = list(currencies.keys())[0] if currencies else "USD"
                
                # Extract languages
                languages = data.get("languages", {})
                lang_list = list(languages.values())
                lang_str = ", ".join(lang_list) if lang_list else "English"
                
                # Extract timezone
                timezones = data.get("timezones", [])
                tz = timezones[0] if timezones else "UTC"
                
                # Get fallbacks for local details (visa, tipping, emergency)
                fallback = COUNTRY_INFO_FALLBACK.get(mapped_country, COUNTRY_INFO_FALLBACK["france"])
                
                result = {
                    "currency": curr_code,
                    "language": lang_str,
                    "timezone": tz,
                    "emergency_numbers": fallback["emergency_numbers"],
                    "visa_requirements_note": fallback["visa_requirements_note"],
                    "tipping_culture": fallback["tipping_culture"],
                    "useful_travel_tips": fallback["useful_travel_tips"],
                    "source": "restcountries_api_live"
                }
                log_event("RESPONSE", json.dumps(result))
                return result
                
            raise httpx.HTTPStatusError("API returned error", request=res.request, response=res)
            
    except Exception as e:
        log_event("WARNING", f"RestCountries API failed: {str(e)}. Falling back to local data.")
        result = COUNTRY_INFO_FALLBACK.get(mapped_country, COUNTRY_INFO_FALLBACK["france"])
        result["source"] = "fallback_local_database"
        log_event("RESPONSE", json.dumps(result))
        return result

@mcp.tool()
async def estimate_transport_cost(origin_city: str, destination_city: str, transport_type: str) -> dict:
    """
    Estimates travel cost and carbon footprint between two cities.

    Parameters:
    - origin_city: Departure city.
    - destination_city: Arrival city.
    - transport_type: Mode of transport ("flight", "train", "bus").

    Returns:
    A dictionary containing estimated_cost_usd, duration_hours, booking_tip, and eco_impact_kg_co2.
    """
    log_event("CALL", f"estimate_transport_cost(origin={origin_city}, destination={destination_city}, type={transport_type})")
    
    orig = origin_city.strip().lower()
    dest = destination_city.strip().lower()
    ttype = transport_type.strip().lower()
    
    # Try direct mapping
    key = None
    if (orig == "new york" or "new york" in orig) and (dest == "paris" or "paris" in dest):
        key = ("new york", "paris")
    elif (orig == "paris" or "paris" in orig) and (dest == "barcelona" or "barcelona" in dest):
        key = ("paris", "barcelona")
    elif (orig == "tokyo" or "tokyo" in orig) and (dest == "bali" or "bali" in dest):
        key = ("tokyo", "bali")
    # Reverse lookups
    elif (orig == "paris" or "paris" in orig) and (dest == "new york" or "new york" in dest):
        key = ("new york", "paris")
    elif (orig == "barcelona" or "barcelona" in orig) and (dest == "paris" or "paris" in dest):
        key = ("paris", "barcelona")
    elif (orig == "bali" or "bali" in orig) and (dest == "tokyo" or "tokyo" in dest):
        key = ("tokyo", "bali")
        
    if key and ttype in TRANSPORT_TABLE[key]:
        data = TRANSPORT_TABLE[key][ttype]
        if data["cost"] is not None:
            result = {
                "estimated_cost_usd": float(data["cost"]),
                "duration_hours": float(data["duration"]),
                "booking_tip": data["tip"],
                "eco_impact_kg_co2": float(data["co2"])
            }
            log_event("RESPONSE", json.dumps(result))
            return result
            
    # Default fallback estimates for other city pairs
    if ttype == "flight":
        result = {
            "estimated_cost_usd": 800.0,
            "duration_hours": 12.0,
            "booking_tip": "Look for connecting flights to reduce cost. Clear cookies when searching.",
            "eco_impact_kg_co2": 950.0
        }
    elif ttype == "train":
        result = {
            "estimated_cost_usd": 120.0,
            "duration_hours": 4.5,
            "booking_tip": "Purchase high-speed rail passes early for discounts.",
            "eco_impact_kg_co2": 15.0
        }
    else:
        result = {
            "estimated_cost_usd": 40.0,
            "duration_hours": 8.0,
            "booking_tip": "Choose express bus services with power outlets.",
            "eco_impact_kg_co2": 35.0
        }
        
    log_event("RESPONSE", json.dumps(result))
    return result

@mcp.tool()
async def check_disruption(city: str, activity_name: str, date: str) -> dict:
    """
    Checks for simulated weather, closure, or logistical disruptions for an activity.

    Parameters:
    - city: The city name.
    - activity_name: The name of the activity.
    - date: Target date in YYYY-MM-DD format.

    Returns:
    A dictionary containing is_disrupted (bool), disruption_reason (str), and severity ("low"|"medium"|"high").
    """
    log_event("CALL", f"check_disruption(city={city}, activity={activity_name}, date={date})")
    
    act_clean = activity_name.strip().lower()
    
    for keyword, info in DISRUPTION_LOOKUP.items():
        if keyword in act_clean:
            # Check if this disruption applies to the specified date
            if date in info["dates"]:
                result = {
                    "is_disrupted": True,
                    "disruption_reason": info["reason"],
                    "severity": info["severity"]
                }
                log_event("RESPONSE", json.dumps(result))
                return result
                
    # Default: No disruption
    result = {
        "is_disrupted": False,
        "disruption_reason": "No disruptions reported.",
        "severity": "low"
    }
    log_event("RESPONSE", json.dumps(result))
    return result

if __name__ == "__main__":
    # When executed as main process, start the FastMCP stdio server
    log_event("STARTUP", "Starting TripForge Travel Tools MCP Server on stdio transport...")
    mcp.run()
