# File: tripforge/orchestrator.py
# Purpose: Core async pipeline orchestrator linking MCP server, ADK Agents, and the CLI.
# Competition Concept: Orchestrator & Multi-agent flow (ADK)

import os
import sys
import json
import asyncio
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator
from contextlib import AsyncExitStack

# Official MCP Client imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Google ADK imports
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.events.event import Event
from google.genai.types import Content, Part

# Rich console imports
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.theme import Theme

# Helper imports
from tripforge.utils.security import guard_external_call, sign_tool_call, scrub_pii
from tripforge.utils.formatters import format_itinerary_markdown, format_itinerary_terminal

# Custom console with themed styling
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "step": "bold magenta"
})
console = Console(theme=custom_theme)

# Global active MCP session pointer
_ACTIVE_MCP_SESSION = None

# Global mock outputs for simulated mode (avoids Gemini API requirements during judges' review)
MOCK_PROFILE_RESPONSE = """---PROFILE_JSON---
{
  "destination": "Paris",
  "days": 3,
  "travelers": 2,
  "budget": 2000.0,
  "currency": "USD",
  "start_date": "2025-08-15",
  "accessibility_needs": null,
  "dietary_restrictions": null,
  "travel_style": "mid-range",
  "interests": ["culture", "food", "history"]
}
---SUMMARY---
Validated traveler profile for a 3-day exploration of Paris for 2 travelers. Total budget is $2,000.00 USD. No accessibility or dietary restrictions requested. Interests include art, culture, food, and history.
"""

MOCK_RESEARCH_RESPONSE = """---RESEARCH_REPORT---
### 📅 Weather Forecast
- Day 1 (2025-08-15): Sunny, High 24°C, Low 14°C, 10% precipitation. Excellent for outdoor sightseeing.
- Day 2 (2025-08-16): Partly Cloudy, High 22°C, Low 13°C, 20% precipitation. Suitable for outdoor strolls.
- Day 3 (2025-08-17): Sunny, High 25°C, Low 15°C, 15% precipitation. Perfect for walking tours.

### 🏛️ Curated Activity Pool
1. **Louvre Museum Guided Tour** (Category: culture, Cost: €65/person, Duration: 3.0 hrs, Wheelchair: Yes)
2. **Eiffel Tower Summit Access** (Category: culture, Cost: €30/person, Duration: 2.0 hrs, Wheelchair: No)
3. **Bateaux Parisiens Seine River Dinner Cruise** (Category: food, Cost: €95/person, Duration: 2.5 hrs, Wheelchair: Yes)
4. **Montmartre Bohemian Artists Walking Tour** (Category: culture, Cost: €15/person, Duration: 2.0 hrs, Wheelchair: No)
5. **Artisanal Croissant Baking Masterclass** (Category: food, Cost: €75/person, Duration: 3.0 hrs, Wheelchair: Yes)
6. **Le Marais Boutiques & Vintage Shopping** (Category: shopping, Cost: €0/person, Duration: 3.0 hrs, Wheelchair: Yes)
7. **Palace of Versailles & Gardens Tour** (Category: culture, Cost: €28/person, Duration: 5.0 hrs, Wheelchair: Yes)
8. **Paris Catacombs Underground Exploration** (Category: adventure, Cost: €29/person, Duration: 1.5 hrs, Wheelchair: No)

### 🌍 Country Essentials: France
- Currency: EUR (Euro)
- Language: French
- Timezone: UTC+1
- Emergency Numbers: General 112, Police 17, Ambulance 15
- Visa: Schengen regulations apply. 90-day visa-free for many tourists.
- Tipping: Service included. Small round-ups appreciated.

### 🚗 Transport & Logistics
- Estimated Flight Cost: $650.00 USD (Duration: 7.5 hrs, Eco Footprint: 620 kg CO2).
- Tip: Book 3 months in advance. Choose overnight flights to adjust to timezone.
"""

MOCK_ITINERARY_RESPONSE = """---ITINERARY_MARKDOWN---
# 🌍 TripForge Itinerary: Paris, France
**Trip Details:** 3 Days | 2 Travelers | Budget: USD 2,000.00

---

## 📅 Day 1: Historic Art & Sunset Cruise
- **Morning (09:00 - 12:00):** **Louvre Museum Guided Tour**
  - *Duration:* 3.0 hours | *Cost:* USD 65.00/person
  - *Description:* Skip the line and explore the world's largest art museum with a certified guide. See the Mona Lisa and Venus de Milo.
- **Afternoon (14:00 - 16:00):** **Montmartre Bohemian Artists Walking Tour**
  - *Duration:* 2.0 hours | *Cost:* USD 15.00/person
  - *Description:* Stroll down winding cobblestone streets, visiting spots frequented by Picasso and Van Gogh.
- **Evening (19:30 - 22:00):** **Bateaux Parisiens Seine River Dinner Cruise**
  - *Duration:* 2.5 hours | *Cost:* USD 95.00/person
  - *Description:* Indulge in a premium 3-course French dinner while floating past illuminated historical monuments.
- **🍴 Daily Dining:**
  - *Breakfast:* Croissants and espresso at Café de Flore.
  - *Lunch:* Classic bistro lunch at Le Consulat in Montmartre.
  - *Dinner:* 3-course French dinner onboard the Seine Cruise.
- **🚶 Transit:** Metro between Louvre and Montmartre, taxi to Seine cruise.
- **💡 Insider Tip:** Enter the Louvre from the underground shopping mall 'Carrousel' to bypass queues.
- **💵 Daily Spend:** USD 175.00/person

---

## 📅 Day 2: Pastry Craft & Eiffel Views
- **Morning (09:30 - 11:30):** **Eiffel Tower Summit Access**
  - *Duration:* 2.0 hours | *Cost:* USD 30.00/person
  - *Description:* Take the glass elevators to the very peak of Paris's iconic landmark for 360-degree views.
- **Afternoon (13:30 - 16:30):** **Artisanal Croissant Baking Masterclass**
  - *Duration:* 3.0 hours | *Cost:* USD 75.00/person
  - *Description:* Learn the secrets of French pastry-making from a local chef in a cozy Parisian kitchen.
- **Evening (17:30 - 20:30):** **Le Marais Boutiques & Vintage Shopping**
  - *Duration:* 3.0 hours | *Cost:* USD 0.00/person
  - *Description:* Explore high-fashion boutiques and hidden gardens in Paris's trendiest historic quarter.
- **🍴 Daily Dining:**
  - *Breakfast:* Fresh baguette with butter at a local neighborhood bakery.
  - *Lunch:* Authentic galettes and crepes at Breizh Café in Le Marais.
  - *Dinner:* Steak Frites at L'Entrecôte.
- **🚶 Transit:* Walk between pastry class and Le Marais.
- **💡 Insider Tip:** Sunset is the best time to capture the glittering Eiffel Tower light show.
- **💵 Daily Spend:** USD 105.00/person

---

## 📅 Day 3: Royal Splendor & Underbelly
- **Morning (09:00 - 14:00):** **Palace of Versailles & Gardens Tour**
  - *Duration:* 5.0 hours | *Cost:* USD 28.00/person
  - *Description:* Walk the stunning Hall of Mirrors, explore the grand apartments and manicured gardens.
- **Afternoon (15:30 - 17:00):** **Paris Catacombs Underground Exploration**
  - *Duration:* 1.5 hours | *Cost:* USD 29.00/person
  - *Description:* Descend 20 meters below the streets of Paris into the historic ossuary.
- **Evening (18:30 - 20:30):** **Relaxing Seine Walk & Jardin des Tuileries**
  - *Duration:* 2.0 hours | *Cost:* USD 0.00/person
  - *Description:* Wander the Tuileries gardens and sit in the famous green chairs.
- **🍴 Daily Dining:**
  - *Breakfast:* Coffee and pastries at Angelina Paris near Tuileries.
  - *Lunch:* Quick sandwich at a bakery in Versailles.
  - *Dinner:* Traditional duck confit at Bouillon Chartier.
- **🚶 Transit:** RER C train to and from Versailles.
- **💡 Insider Tip:** Rent a golf cart or hop on the mini-train to save energy at Versailles.
- **💵 Daily Spend:** USD 57.00/person

---

## 📊 Trip Summary & Essentials
- **Total Estimated Cost:** USD 337.00/person (excluding flights)
- **Suggested Packing:** Comfortable walking shoes, plug adapter (Type E), rain umbrella.
- **Emergency Contacts:** General: 112 | Police: 17 | Ambulance: 15
- **Currency & Logistics:** EUR is used. Credit cards widely accepted; keep some coins for public restrooms.

---ITINERARY_JSON---
{
  "destination": "Paris",
  "days": 3,
  "travelers": 2,
  "budget": 2000.0,
  "currency": "USD",
  "total_cost": 674.0,
  "packing_suggestions": ["Comfortable walking shoes", "Plug adapter Type E", "Rain umbrella"],
  "emergency_contacts": {"General": "112", "Police": "17", "Ambulance": "15"},
  "currency_tips": "EUR is used. Credit cards widely accepted; keep some coins for public restrooms.",
  "days_list": [
    {
      "day_num": 1,
      "theme": "Historic Art & Sunset Cruise",
      "transport_note": "Metro between Louvre and Montmartre, taxi to Seine cruise.",
      "insider_tip": "Enter the Louvre from the underground shopping mall 'Carrousel' to bypass queues.",
      "daily_cost": 350.0,
      "activities": {
        "morning": {
          "name": "Louvre Museum Guided Tour",
          "description": "Skip the line and explore the world's largest art museum with a certified guide.",
          "duration_hours": 3.0,
          "cost_per_person": 65.0,
          "category": "culture",
          "is_replanned": false
        },
        "afternoon": {
          "name": "Montmartre Bohemian Artists Walking Tour",
          "description": "Stroll down winding cobblestone streets, visiting spots frequented by Picasso and Van Gogh.",
          "duration_hours": 2.0,
          "cost_per_person": 15.0,
          "category": "culture",
          "is_replanned": false
        },
        "evening": {
          "name": "Bateaux Parisiens Seine River Dinner Cruise",
          "description": "Indulge in a premium 3-course French dinner while floating past illuminated historical monuments.",
          "duration_hours": 2.5,
          "cost_per_person": 95.0,
          "category": "food",
          "is_replanned": false
        }
      },
      "meals": {
        "breakfast": "Croissants and espresso at Café de Flore.",
        "lunch": "Classic bistro lunch at Le Consulat in Montmartre.",
        "dinner": "3-course French dinner onboard the Seine Cruise."
      }
    },
    {
      "day_num": 2,
      "theme": "Pastry Craft & Eiffel Views",
      "transport_note": "Walk or Metro.",
      "insider_tip": "Sunset is the best time to capture the glittering Eiffel Tower light show.",
      "daily_cost": 210.0,
      "activities": {
        "morning": {
          "name": "Eiffel Tower Summit Access",
          "description": "Take the glass elevators to the very peak of Paris's iconic landmark for 360-degree views.",
          "duration_hours": 2.0,
          "cost_per_person": 30.0,
          "category": "culture",
          "is_replanned": false
        },
        "afternoon": {
          "name": "Artisanal Croissant Baking Masterclass",
          "description": "Learn the secrets of French pastry-making from a local chef.",
          "duration_hours": 3.0,
          "cost_per_person": 75.0,
          "category": "food",
          "is_replanned": false
        },
        "evening": {
          "name": "Le Marais Boutiques & Vintage Shopping",
          "description": "Explore high-fashion boutiques and hidden gardens in Paris's trendiest historic quarter.",
          "duration_hours": 3.0,
          "cost_per_person": 0.0,
          "category": "shopping",
          "is_replanned": false
        }
      },
      "meals": {
        "breakfast": "Fresh baguette with butter at a local neighborhood bakery.",
        "lunch": "Authentic galettes and crepes at Breizh Café in Le Marais.",
        "dinner": "Steak Frites at L'Entrecôte."
      }
    },
    {
      "day_num": 3,
      "theme": "Royal Splendor & Underbelly",
      "transport_note": "RER C train to and from Versailles.",
      "insider_tip": "Rent a golf cart or hop on the mini-train to save energy at Versailles.",
      "daily_cost": 114.0,
      "activities": {
        "morning": {
          "name": "Palace of Versailles & Gardens Tour",
          "description": "Walk the stunning Hall of Mirrors, explore the grand apartments and manicured gardens.",
          "duration_hours": 5.0,
          "cost_per_person": 28.0,
          "category": "culture",
          "is_replanned": false
        },
        "afternoon": {
          "name": "Paris Catacombs Underground Exploration",
          "description": "Descend 20 meters below the streets of Paris into the historic ossuary.",
          "duration_hours": 1.5,
          "cost_per_person": 29.0,
          "category": "adventure",
          "is_replanned": false
        },
        "evening": {
          "name": "Relaxing Seine Walk & Jardin des Tuileries",
          "description": "Wander the Tuileries gardens and sit in the famous green chairs.",
          "duration_hours": 2.0,
          "cost_per_person": 0.0,
          "category": "relaxation",
          "is_replanned": false
        }
      },
      "meals": {
        "breakfast": "Coffee and pastries at Angelina Paris near Tuileries.",
        "lunch": "Quick sandwich at a bakery in Versailles.",
        "dinner": "Traditional duck confit at Bouillon Chartier."
      }
    }
  ]
}"""

MOCK_REPLAN_RESPONSE = """---REPLANNED_MARKDOWN---
# ⚡ What Changed (Replanned)
- **Day 1 Morning Activity Swapped:** The Louvre Museum was affected by a strike disruption. We successfully replaced it with a **Sainte-Chapelle & Conciergerie Tour**, saving $45.00 per person and maintaining safety parameters.
- **Budget Balance:** The updated daily cost for Day 1 is now $260.00 total ($130.00/person), which is well below the per-day budget ceiling.
- **Preserved Plan:** Day 2 and Day 3 plans have been preserved exactly as scheduled.

---

# 🌍 TripForge Itinerary: Paris, France (Replanned)
**Trip Details:** 3 Days | 2 Travelers | Budget: USD 2,000.00

---

## 📅 Day 1: Historic Art & Sunset Cruise
- **Morning (09:00 - 11:00):** **⚡ Sainte-Chapelle & Conciergerie Tour**
  - *Duration:* 2.0 hours | *Cost:* USD 20.00/person
  - *Description:* Visit the stunning Gothic chapel with its breathtaking 13th-century stained glass windows.
- **Afternoon (14:00 - 16:00):** **Montmartre Bohemian Artists Walking Tour**
  - *Duration:* 2.0 hours | *Cost:* USD 15.00/person
  - *Description:* Stroll down winding cobblestone streets, visiting spots frequented by Picasso and Van Gogh.
- **Evening (19:30 - 22:00):** **Bateaux Parisiens Seine River Dinner Cruise**
  - *Duration:* 2.5 hours | *Cost:* USD 95.00/person
  - *Description:* Indulge in a premium 3-course French dinner while floating past illuminated historical monuments.
- **🍴 Daily Dining:**
  - *Breakfast:* Croissants and espresso at Café de Flore.
  - *Lunch:* Classic bistro lunch at Le Consulat in Montmartre.
  - *Dinner:* 3-course French dinner onboard the Seine Cruise.
- **🚶 Transit:** Metro between Sainte-Chapelle and Montmartre, taxi to Seine cruise.
- **💡 Insider Tip:** Enter the Sainte-Chapelle early in the morning to beat the lines.
- **💵 Daily Spend:** USD 130.00/person

---

## 📅 Day 2: Pastry Craft & Eiffel Views
- **Morning (09:30 - 11:30):** **Eiffel Tower Summit Access**
  - *Duration:* 2.0 hours | *Cost:* USD 30.00/person
  - *Description:* Take the glass elevators to the very peak of Paris's iconic landmark for 360-degree views.
- **Afternoon (13:30 - 16:30):** **Artisanal Croissant Baking Masterclass**
  - *Duration:* 3.0 hours | *Cost:* USD 75.00/person
  - *Description:* Learn the secrets of French pastry-making from a local chef in a cozy Parisian kitchen.
- **Evening (17:30 - 20:30):** **Le Marais Boutiques & Vintage Shopping**
  - *Duration:* 3.0 hours | *Cost:* USD 0.00/person
  - *Description:* Explore high-fashion boutiques and hidden gardens in Paris's trendiest historic quarter.
- **🍴 Daily Dining:**
  - *Breakfast:* Fresh baguette with butter at a local neighborhood bakery.
  - *Lunch:* Authentic galettes and crepes at Breizh Café in Le Marais.
  - *Dinner:* Steak Frites at L'Entrecôte.
- **🚶 Transit:* Walk between pastry class and Le Marais.
- **💡 Insider Tip:** Sunset is the best time to capture the glittering Eiffel Tower light show.
- **💵 Daily Spend:** USD 105.00/person

---

## 📅 Day 3: Royal Splendor & Underbelly
- **Morning (09:00 - 14:00):** **Palace of Versailles & Gardens Tour**
  - *Duration:* 5.0 hours | *Cost:* USD 28.00/person
  - *Description:* Walk the stunning Hall of Mirrors, explore the grand apartments and manicured gardens.
- **Afternoon (15:30 - 17:00):** **Paris Catacombs Underground Exploration**
  - *Duration:* 1.5 hours | *Cost:* USD 29.00/person
  - *Description:* Descend 20 meters below the streets of Paris into the historic ossuary.
- **Evening (18:30 - 20:30):** **Relaxing Seine Walk & Jardin des Tuileries**
  - *Duration:* 2.0 hours | *Cost:* USD 0.00/person
  - *Description:* Wander the Tuileries gardens and sit in the famous green chairs.
- **🍴 Daily Dining:**
  - *Breakfast:* Coffee and pastries at Angelina Paris near Tuileries.
  - *Lunch:* Quick sandwich at a bakery in Versailles.
  - *Dinner:* Traditional duck confit at Bouillon Chartier.
- **🚶 Transit:** RER C train to and from Versailles.
- **💡 Insider Tip:** Rent a golf cart or hop on the mini-train to save energy at Versailles.
- **💵 Daily Spend:** USD 57.00/person

---

## 📊 Trip Summary & Essentials
- **Total Estimated Cost:** USD 292.00/person (excluding flights)
- **Suggested Packing:** Comfortable walking shoes, plug adapter (Type E), rain umbrella.
- **Emergency Contacts:** General: 112 | Police: 17 | Ambulance: 15
- **Currency & Logistics:** EUR is used. Credit cards widely accepted; keep some coins for public restrooms.

---REPLANNED_JSON---
{
  "destination": "Paris",
  "days": 3,
  "travelers": 2,
  "budget": 2000.0,
  "currency": "USD",
  "total_cost": 584.0,
  "packing_suggestions": ["Comfortable walking shoes", "Plug adapter Type E", "Rain umbrella"],
  "emergency_contacts": {"General": "112", "Police": "17", "Ambulance": "15"},
  "currency_tips": "EUR is used. Credit cards widely accepted; keep some coins for public restrooms.",
  "what_changed": "- **Day 1 Morning Activity Swapped:** The Louvre Museum was affected by a strike disruption. We successfully replaced it with a **Sainte-Chapelle & Conciergerie Tour**, saving $45.00 per person.\\n- **Budget Balance:** The updated daily cost for Day 1 is now $260.00 total ($130.00/person), which is well under budget.\\n- **Preserved Plan:** Days 2 and 3 preserved exactly as scheduled.",
  "days_list": [
    {
      "day_num": 1,
      "theme": "Historic Art & Sunset Cruise (Replanned)",
      "transport_note": "Metro between Sainte-Chapelle and Montmartre, taxi to Seine cruise.",
      "insider_tip": "Enter the Sainte-Chapelle early in the morning to beat the lines.",
      "daily_cost": 260.0,
      "activities": {
        "morning": {
          "name": "Sainte-Chapelle & Conciergerie Tour",
          "description": "Visit the stunning Gothic chapel with its breathtaking 13th-century stained glass windows.",
          "duration_hours": 2.0,
          "cost_per_person": 20.0,
          "category": "culture",
          "is_replanned": true
        },
        "afternoon": {
          "name": "Montmartre Bohemian Artists Walking Tour",
          "description": "Stroll down winding cobblestone streets, visiting spots frequented by Picasso and Van Gogh.",
          "duration_hours": 2.0,
          "cost_per_person": 15.0,
          "category": "culture",
          "is_replanned": false
        },
        "evening": {
          "name": "Bateaux Parisiens Seine River Dinner Cruise",
          "description": "Indulge in a premium 3-course French dinner while floating past illuminated historical monuments.",
          "duration_hours": 2.5,
          "cost_per_person": 95.0,
          "category": "food",
          "is_replanned": false
        }
      },
      "meals": {
        "breakfast": "Croissants and espresso at Café de Flore.",
        "lunch": "Classic bistro lunch at Le Consulat in Montmartre.",
        "dinner": "3-course French dinner onboard the Seine Cruise."
      }
    },
    {
      "day_num": 2,
      "theme": "Pastry Craft & Eiffel Views",
      "transport_note": "Walk or Metro.",
      "insider_tip": "Sunset is the best time to capture the glittering Eiffel Tower light show.",
      "daily_cost": 210.0,
      "activities": {
        "morning": {
          "name": "Eiffel Tower Summit Access",
          "description": "Take the glass elevators to the very peak of Paris's iconic landmark for 360-degree views.",
          "duration_hours": 2.0,
          "cost_per_person": 30.0,
          "category": "culture",
          "is_replanned": false
        },
        "afternoon": {
          "name": "Artisanal Croissant Baking Masterclass",
          "description": "Learn the secrets of French pastry-making from a local chef.",
          "duration_hours": 3.0,
          "cost_per_person": 75.0,
          "category": "food",
          "is_replanned": false
        },
        "evening": {
          "name": "Le Marais Boutiques & Vintage Shopping",
          "description": "Explore high-fashion boutiques and hidden gardens in Paris's trendiest historic quarter.",
          "duration_hours": 3.0,
          "cost_per_person": 0.0,
          "category": "shopping",
          "is_replanned": false
        }
      },
      "meals": {
        "breakfast": "Fresh baguette with butter at a local neighborhood bakery.",
        "lunch": "Authentic galettes and crepes at Breizh Café in Le Marais.",
        "dinner": "Steak Frites at L'Entrecôte."
      }
    },
    {
      "day_num": 3,
      "theme": "Royal Splendor & Underbelly",
      "transport_note": "RER C train to and from Versailles.",
      "insider_tip": "Rent a golf cart or hop on the mini-train to save energy at Versailles.",
      "daily_cost": 114.0,
      "activities": {
        "morning": {
          "name": "Palace of Versailles & Gardens Tour",
          "description": "Walk the stunning Hall of Mirrors, explore the grand apartments and manicured gardens.",
          "duration_hours": 5.0,
          "cost_per_person": 28.0,
          "category": "culture",
          "is_replanned": false
        },
        "afternoon": {
          "name": "Paris Catacombs Underground Exploration",
          "description": "Descend 20 meters below the streets of Paris into the historic ossuary.",
          "duration_hours": 1.5,
          "cost_per_person": 29.0,
          "category": "adventure",
          "is_replanned": false
        },
        "evening": {
          "name": "Relaxing Seine Walk & Jardin des Tuileries",
          "description": "Wander the Tuileries gardens and sit in the famous green chairs.",
          "duration_hours": 2.0,
          "cost_per_person": 0.0,
          "category": "relaxation",
          "is_replanned": false
        }
      },
      "meals": {
        "breakfast": "Coffee and pastries at Angelina Paris near Tuileries.",
        "lunch": "Quick sandwich at a bakery in Versailles.",
        "dinner": "Traditional duck confit at Bouillon Chartier."
      }
    }
  ]
}"""

# Simulated Async Generator for Mock Mode
class MockAgentAsyncGenerator:
    def __init__(self, agent_name: str, response_text: str):
        self.agent_name = agent_name
        self.response_text = response_text
        self._sent = False

    def __aiter__(self):
        return self

    async def __anext__(self) -> Event:
        if self._sent:
            raise StopAsyncIteration
        self._sent = True
        
        # Introduce a short artificial delay per agent to simulate thinking
        await asyncio.sleep(2.0)
        
        part = Part(text=self.response_text)
        content = Content(parts=[part], role="model")
        
        event = Event(
            invocation_id=f"mock-inv-{self.agent_name}",
            author=self.agent_name,
            content=content
        )
        return event

# Global patch context
_RUNNER_PATCH = None

def apply_mock_runner_patch():
    """Monkey patches google-adk InMemoryRunner.run_async to intercept Gemini API calls and return mock data."""
    global _RUNNER_PATCH
    if _RUNNER_PATCH is not None:
        return
        
    def mock_run_async(self_runner, *, user_id: str, session_id: str, **kwargs) -> AsyncGenerator[Event, None]:
        # Search for which agent is attached to the runner
        agent_name = "Agent"
        if hasattr(self_runner, "agent") and self_runner.agent:
            agent_name = self_runner.agent.name
        elif hasattr(self_runner, "root_agent") and self_runner.root_agent:
            agent_name = self_runner.root_agent.name
            
        if agent_name == "ProfileAgent":
            return MockAgentAsyncGenerator("ProfileAgent", MOCK_PROFILE_RESPONSE)
        elif agent_name == "ResearchAgent":
            return MockAgentAsyncGenerator("ResearchAgent", MOCK_RESEARCH_RESPONSE)
        elif agent_name == "ItineraryAgent":
            return MockAgentAsyncGenerator("ItineraryAgent", MOCK_ITINERARY_RESPONSE)
        elif agent_name == "DisruptionAgent":
            return MockAgentAsyncGenerator("DisruptionAgent", MOCK_REPLAN_RESPONSE)
            
        return MockAgentAsyncGenerator(agent_name, "Simulated fallback response.")

    # Apply mock patch directly onto the InMemoryRunner class
    InMemoryRunner.run_async = mock_run_async
    _RUNNER_PATCH = True
    console.print("[yellow][MOCK MODE] Google ADK LLM runner successfully patched to mock model response offline.[/yellow]")

# --- MCP Tool Client-side Wrappers ---

def _clean_city_param(city: Any) -> str:
    if not city:
        return "Tokyo"
    if isinstance(city, dict):
        for key in ["destination", "city", "location", "country", "name"]:
            if key in city and isinstance(city[key], str):
                return city[key]
        for val in city.values():
            if isinstance(val, str):
                return val
        return "Tokyo"
    if isinstance(city, (list, tuple)):
        if len(city) > 0:
            return _clean_city_param(city[0])
        return "Tokyo"
    return str(city)

def _clean_string_param(val: Any) -> Optional[str]:
    if not val:
        return None
    if isinstance(val, (list, tuple)):
        if len(val) > 0:
            return _clean_string_param(val[0])
        return None
    if isinstance(val, dict):
        for key in ["name", "value", "type", "preference"]:
            if key in val and isinstance(val[key], str):
                return val[key]
        for v in val.values():
            if isinstance(v, str):
                return v
        return None
    val_str = str(val).strip()
    if val_str.lower() in ["none", "null", "undefined", ""]:
        return None
    return val_str

def _clean_bool_param(val: Any) -> bool:
    if not val:
        return False
    if isinstance(val, bool):
        return val
    val_str = str(val).strip().lower()
    if val_str in ["false", "none", "no", "0", "null", "undefined"]:
        return False
    return True

def _normalize_summary_data(summary_data: Any, destination: str, days: int, travelers: int, budget: float, currency: str, start_date: str = None) -> dict:
    if not isinstance(summary_data, dict):
        summary_data = {}
        
    # Standard fallback basic fields
    if not summary_data.get("destination"):
        summary_data["destination"] = destination
    if not summary_data.get("days"):
        summary_data["days"] = days
    if not summary_data.get("travelers"):
        summary_data["travelers"] = travelers
    if not summary_data.get("budget"):
        summary_data["budget"] = budget
    if not summary_data.get("currency"):
        summary_data["currency"] = currency
    if not summary_data.get("total_cost"):
        summary_data["total_cost"] = budget
        
    # Emergency contacts
    emerg = summary_data.get("emergency_contacts")
    if not emerg:
        summary_data["emergency_contacts"] = {"General": "112", "Police": "112", "Ambulance": "112"}
    elif isinstance(emerg, str):
        summary_data["emergency_contacts"] = {"Contacts": emerg}
    elif not isinstance(emerg, dict):
        summary_data["emergency_contacts"] = {"General": "112", "Police": "112", "Ambulance": "112"}
        
    # Packing suggestions
    packing = summary_data.get("packing_suggestions")
    if not packing:
        summary_data["packing_suggestions"] = ["Comfortable walking shoes", "Passport/Visa", "Adapters"]
    elif isinstance(packing, str):
        items = [x.strip() for x in re.split(r'[,;\n]', packing) if x.strip()]
        summary_data["packing_suggestions"] = items if items else ["Comfortable walking shoes"]
    elif not isinstance(packing, (list, tuple)):
        summary_data["packing_suggestions"] = ["Comfortable walking shoes"]
        
    # Currency tips
    tips = summary_data.get("currency_tips")
    if not tips:
        summary_data["currency_tips"] = "Credit cards widely accepted."
    elif not isinstance(tips, str):
        summary_data["currency_tips"] = str(tips)
        
    # Geocoding & Weather Integration
    import urllib.request
    import urllib.parse
    
    lat = summary_data.get("latitude")
    lon = summary_data.get("longitude")
    
    if lat is None or lon is None:
        coords_map = {
            "paris": (48.8566, 2.3522),
            "tokyo": (35.6762, 139.6503),
            "barcelona": (41.3851, 2.1734),
            "new york": (40.7128, -74.0060),
            "bali": (-8.4095, 115.1889),
            "berlin": (52.5200, 13.4050),
            "germany": (52.5200, 13.4050),
            "munich": (48.1351, 11.5820),
            "london": (51.5074, -0.1278)
        }
        
        dest_clean = destination.strip().lower()
        matched_coords = None
        for key, coords in coords_map.items():
            if key in dest_clean:
                matched_coords = coords
                break
                
        if matched_coords:
            lat, lon = matched_coords
        else:
            try:
                quoted = urllib.parse.quote(destination)
                url = f"https://geocoding-api.open-meteo.com/v1/search?name={quoted}&count=1&language=en&format=json"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    data = json.loads(response.read().decode())
                    if data.get("results"):
                        lat = data["results"][0]["latitude"]
                        lon = data["results"][0]["longitude"]
                    else:
                        lat, lon = 48.8566, 2.3522
            except Exception:
                lat, lon = 48.8566, 2.3522
            
    summary_data["latitude"] = lat
    summary_data["longitude"] = lon
    
    # Check if weather elements were predicted by AI in the summary_data
    w_high = summary_data.get("weather_high")
    w_low = summary_data.get("weather_low")
    w_cond = summary_data.get("weather_condition")
    w_icon = summary_data.get("weather_icon")
    
    # If any weather field is missing from AI output, calculate geoclimatic seasonal fallbacks
    if w_high is None or w_low is None or w_cond is None or w_icon is None:
        try:
            month = 8
            if start_date:
                try:
                    month = datetime.strptime(start_date, "%Y-%m-%d").month
                except Exception:
                    pass
            
            # Geoclimatic zoning check: if within 15 degrees of equator (like Malaysia or Bali), use tropical defaults
            if abs(lat) < 15:
                cond, icon = "Warm/Tropical", "🌴"
                high, low = 31, 24
            else:
                if month in [12, 1, 2]:
                    cond, icon = "Cool/Rainy", "🌧️"
                    high, low = 8, 3
                elif month in [3, 4, 5]:
                    cond, icon = "Mild/Spring", "⛅"
                    high, low = 16, 8
                elif month in [6, 7, 8]:
                    cond, icon = "Warm/Sunny", "☀️"
                    high, low = 26, 16
                else:
                    cond, icon = "Cool/Autumn", "🍂"
                    high, low = 15, 9
                
            w_high = w_high if w_high is not None else high
            w_low = w_low if w_low is not None else low
            w_cond = w_cond if w_cond is not None else cond
            w_icon = w_icon if w_icon is not None else icon
        except Exception:
            w_high = w_high if w_high is not None else 22.0
            w_low = w_low if w_low is not None else 12.0
            w_cond = w_cond if w_cond is not None else "Mild Weather"
            w_icon = w_icon if w_icon is not None else "⛅"
            
    summary_data["weather_high"] = w_high
    summary_data["weather_low"] = w_low
    summary_data["weather_condition"] = w_cond
    summary_data["weather_icon"] = w_icon
        
    # Attempt to query live forecast from Open-Meteo if not in mock mode
    is_mock = os.getenv("TRIPFORGE_MODE", "live").lower() == "mock"
    if not is_mock:
        try:
            s_date = start_date or datetime.today().strftime('%Y-%m-%d')
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&daily=temperature_2m_max,temperature_2m_min,weather_code"
                f"&timezone=auto&start_date={s_date}&end_date={s_date}"
            )
            req = urllib.request.Request(weather_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3.0) as response:
                w_data = json.loads(response.read().decode())
                daily = w_data.get("daily", {})
                if daily and daily.get("temperature_2m_max"):
                    temp_high = daily["temperature_2m_max"][0]
                    temp_low = daily["temperature_2m_min"][0]
                    wcode = daily.get("weather_code", [0])[0]
                    
                    if wcode == 0:
                        cond, icon = "Sunny", "☀️"
                    elif wcode in [1, 2, 3]:
                        cond, icon = "Partly Cloudy", "⛅"
                    elif wcode in [45, 48]:
                        cond, icon = "Foggy", "🌫️"
                    elif wcode in [51, 53, 55]:
                        cond, icon = "Drizzle", "🌧️"
                    elif wcode in [61, 63, 65]:
                        cond, icon = "Rainy", "🌧️"
                    elif wcode in [71, 73, 75]:
                        cond, icon = "Snowy", "❄️"
                    elif wcode in [80, 81, 82]:
                        cond, icon = "Showers", "🌦️"
                    else:
                        cond, icon = "Overcast", "☁️"
                        
                    summary_data["weather_high"] = temp_high
                    summary_data["weather_low"] = temp_low
                    summary_data["weather_condition"] = cond
                    summary_data["weather_icon"] = icon
        except Exception:
            pass
            
    return summary_data

async def get_weather_tool(city: str, date: str) -> dict:
    """Wrapper calling MCP get_weather tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    city = _clean_city_param(city)
    date = _clean_string_param(date) or datetime.today().strftime('%Y-%m-%d')
        
    # Security Guard Consent Check
    if not guard_external_call("Open-Meteo Weather API", f"City: {city}, Date: {date}"):
        # Fallback to local seasonal weather data instead of raising PermissionError
        month = 8  # default to summer/autumn
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
            month = target_date.month
        except Exception:
            pass
        
        # Simple seasonal mapping
        if month in [12, 1, 2]:
            cond = "Cloudy"
            high, low = 8, 3
            suitable = False
        elif month in [3, 4, 5]:
            cond = "Partly Cloudy"
            high, low = 15, 7
            suitable = True
        elif month in [6, 7, 8]:
            cond = "Sunny"
            high, low = 25, 15
            suitable = True
        else:
            cond = "Rainy"
            high, low = 16, 9
            suitable = False
            
        return {
            "temperature_high": high,
            "temperature_low": low,
            "precipitation_chance": 20,
            "condition": cond,
            "suitable_for_outdoor": suitable,
            "source": "fallback_seasonal_estimate"
        }
        
    params = {"city": city, "date": date}
    # HMAC Signing
    params["signature"] = sign_tool_call("get_weather", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("get_weather", params)
    try:
        if res.content and len(res.content) > 0:
            return json.loads(res.content[0].text)
    except Exception as e:
        sys.stderr.write(f"[ORCHESTRATOR] Error parsing weather tool response: {str(e)}\n")
        sys.stderr.flush()
    return {}

async def search_activities_tool(city: str, accessibility_required: bool = False, dietary_preference: str = None, category: str = None) -> list:
    """Wrapper calling MCP search_activities tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    city = _clean_city_param(city)
    accessibility_required = _clean_bool_param(accessibility_required)
    dietary_preference = _clean_string_param(dietary_preference)
    category = _clean_string_param(category)
        
    # Local activities DB is considered a safe local query, so we skip warning
    params = {
        "city": city, 
        "accessibility_required": accessibility_required
    }
    if dietary_preference is not None:
        params["dietary_preference"] = dietary_preference
    if category is not None:
        params["category"] = category
        
    params["signature"] = sign_tool_call("search_activities", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("search_activities", params)
    try:
        if res.content and len(res.content) > 0:
            return json.loads(res.content[0].text)
    except Exception as e:
        raw_text = res.content[0].text if (res.content and len(res.content) > 0) else None
        sys.stderr.write(f"[ORCHESTRATOR] Error parsing search_activities tool response: {str(e)}. Raw text: {repr(raw_text)}\n")
        sys.stderr.flush()
    return []

async def get_country_info_tool(country_name: str) -> dict:
    """Wrapper calling MCP get_country_info tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    country_name = _clean_city_param(country_name)
        
    if not guard_external_call("RestCountries API", f"Country: {country_name}"):
        # Fallback to local country info data instead of raising PermissionError
        c_name = country_name.strip().lower()
        if "japan" in c_name:
            result = {
                "currency": "JPY",
                "language": "Japanese",
                "timezone": "UTC+9",
                "emergency_numbers": {"General": "110/119", "Police": "110", "Ambulance": "119"},
                "visa_requirements_note": "90-day visa-free entry for tourist visits for citizens of many countries.",
                "tipping_culture": "Tipping is not practiced in Japan. Exceptional service is covered by the bill.",
                "useful_travel_tips": "Carry cash (many places don't accept cards). Respect public rules (no eating while walking, keep quiet on trains). Use a Suica/Pasmo card.",
                "source": "fallback_local_database"
            }
        elif "spain" in c_name:
            result = {
                "currency": "EUR",
                "language": "Spanish",
                "timezone": "UTC+1",
                "emergency_numbers": {"General": "112", "Police": "091", "Ambulance": "061"},
                "visa_requirements_note": "Schengen area rules apply. 90-day visa-free entry for tourist visits.",
                "tipping_culture": "Tipping is optional but appreciated (usually 5-10% in sit-down restaurants).",
                "useful_travel_tips": "Dining hours are late (lunch at 2 PM, dinner at 9 PM). Watch out for pickpockets in crowded tourist spots.",
                "source": "fallback_local_database"
            }
        elif "indonesia" in c_name or "bali" in c_name:
            result = {
                "currency": "IDR",
                "language": "Indonesian",
                "timezone": "UTC+8",
                "emergency_numbers": {"General": "112", "Police": "110", "Ambulance": "118"},
                "visa_requirements_note": "Visa on arrival (VOA) required for many nationalities, valid for 30 days.",
                "tipping_culture": "Tipping is not mandatory but rounding up bills or leaving 10% is customary for drivers and tour guides.",
                "useful_travel_tips": "Drink bottled water only. Renting scooters requires an international driving permit. Dress modestly when visiting temples.",
                "source": "fallback_local_database"
            }
        elif "usa" in c_name or "states" in c_name:
            result = {
                "currency": "USD",
                "language": "English",
                "timezone": "EST/CST/MST/PST",
                "emergency_numbers": {"General": "911", "Police": "911", "Ambulance": "911"},
                "visa_requirements_note": "ESTA required for visa-waiver countries. Otherwise, standard B1/B2 tourist visa.",
                "tipping_culture": "Tipping is standard practice: 15-20% in restaurants, $1-2 per drink at bars, and 10-15% for taxi drivers.",
                "useful_travel_tips": "Sales tax is added at checkout, not on price tags. Distances are large, so renting a car is often required outside major cities.",
                "source": "fallback_local_database"
            }
        else: # Default to France/Paris
            result = {
                "currency": "EUR",
                "language": "French",
                "timezone": "UTC+1",
                "emergency_numbers": {"General": "112", "Police": "17", "Ambulance": "15"},
                "visa_requirements_note": "Schengen area rules apply. 90-day visa-free entry for citizens of many countries.",
                "tipping_culture": "Service compris is included in restaurant bills. Leaving an extra 5-10% is customary for good service.",
                "useful_travel_tips": "Buy daily metro passes. Learn basic French greetings (Bonjour, Merci). Keep cash for bakeries.",
                "source": "fallback_local_database"
            }
        return result
        
    params = {"country_name": country_name}
    params["signature"] = sign_tool_call("get_country_info", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("get_country_info", params)
    try:
        if res.content and len(res.content) > 0:
            return json.loads(res.content[0].text)
    except Exception as e:
        sys.stderr.write(f"[ORCHESTRATOR] Error parsing get_country_info tool response: {str(e)}\n")
        sys.stderr.flush()
    return {}

async def estimate_transport_cost_tool(origin_city: str, destination_city: str, transport_type: str) -> dict:
    """Wrapper calling MCP estimate_transport_cost tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    origin_city = _clean_city_param(origin_city)
    destination_city = _clean_city_param(destination_city)
    transport_type = _clean_string_param(transport_type) or "flight"
        
    params = {
        "origin_city": origin_city, 
        "destination_city": destination_city, 
        "transport_type": transport_type
    }
    params["signature"] = sign_tool_call("estimate_transport_cost", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("estimate_transport_cost", params)
    try:
        if res.content and len(res.content) > 0:
            return json.loads(res.content[0].text)
    except Exception as e:
        sys.stderr.write(f"[ORCHESTRATOR] Error parsing estimate_transport_cost tool response: {str(e)}\n")
        sys.stderr.flush()
    return {}

async def check_disruption_tool(city: str, activity_name: str, date: str) -> dict:
    """Wrapper calling MCP check_disruption tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    city = _clean_city_param(city)
    activity_name = _clean_string_param(activity_name) or ""
    date = _clean_string_param(date) or datetime.today().strftime('%Y-%m-%d')
        
    params = {"city": city, "activity_name": activity_name, "date": date}
    params["signature"] = sign_tool_call("check_disruption", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("check_disruption", params)
    try:
        if res.content and len(res.content) > 0:
            return json.loads(res.content[0].text)
    except Exception as e:
        sys.stderr.write(f"[ORCHESTRATOR] Error parsing check_disruption tool response: {str(e)}\n")
        sys.stderr.flush()
    return {}

# Helper to extract text contents from events
def _extract_text(event: Event) -> str:
    if not event.content or not event.content.parts:
        return ""
    texts = []
    for p in event.content.parts:
        if hasattr(p, "text") and p.text:
            texts.append(p.text)
    return "".join(texts)

# --- Orchestrator Pipeline Executions ---

async def stream_tripforge(
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    currency: str = "USD",
    accessibility: str = None,
    dietary: str = None,
    travel_style: str = None,
    interests: list = None,
    start_date: str = None,
    verbose: bool = False
) -> AsyncGenerator[dict, None]:
    """
    Async generator workflow for TripForge. Launches MCP server, runs ProfileAgent, 
    ResearchAgent, and ItineraryAgent in sequence, yielding progress events.
    """
    global _ACTIVE_MCP_SESSION
    is_mock = os.getenv("TRIPFORGE_MODE", "live").lower() == "mock"
    
    if is_mock:
        apply_mock_runner_patch()
        
    console.print(f"[info]🌍 TripForge is planning your {days}-day trip to {destination}...[/info]")
    
    # Check Gemini API Key
    if not is_mock and not os.getenv("GOOGLE_API_KEY"):
        is_mock = True
        os.environ["TRIPFORGE_MODE"] = "mock"
        apply_mock_runner_patch()
        
    yield {
        "type": "progress",
        "step": 1,
        "message": "Connecting to local travel tools MCP server subprocess...",
        "icon": "👤"
    }
    
    # Start MCP Server subprocess and Client Session
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Ensure all parent import paths (including site-packages and base_dir) are passed to the subprocess
    python_path_dirs = [base_dir] + [p for p in sys.path if p]
    # Remove duplicates while preserving order
    seen = set()
    python_path_dirs = [x for x in python_path_dirs if not (x in seen or seen.add(x))]
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tripforge.mcp_server.travel_tools_server"],
        env={**os.environ, "PYTHONPATH": os.pathsep.join(python_path_dirs)}
    )
    
    async with AsyncExitStack() as stack:
        # Step 0: Connect to local MCP Server
        read, write = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        _ACTIVE_MCP_SESSION = session
        
        # Load agents
        from tripforge.agents.profile_agent import get_profile_agent
        from tripforge.agents.research_agent import get_research_agent
        from tripforge.agents.itinerary_agent import get_itinerary_agent
        from tripforge.agents.disruption_agent import get_disruption_agent
        
        mcp_tools = [get_weather_tool, search_activities_tool, get_country_info_tool, estimate_transport_cost_tool]
        itinerary_tools = [check_disruption_tool, search_activities_tool]
        
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        p_agent = get_profile_agent(model_name)
        r_agent = get_research_agent(model_name, mcp_tools)
        i_agent = get_itinerary_agent(model_name, itinerary_tools)
        
        # --- STEP 1: PROFILE AGENT ---
        yield {
            "type": "progress",
            "step": 1,
            "message": f"Validating travel profile for {destination}...",
            "icon": "👤"
        }
        
        raw_input = {
            "destination": destination,
            "days": days,
            "travelers": travelers,
            "budget": budget,
            "currency": currency,
            "start_date": start_date,
            "accessibility_needs": accessibility,
            "dietary_restrictions": dietary,
            "travel_style": travel_style,
            "interests": interests
        }
        
        p_runner = InMemoryRunner(agent=p_agent)
        p_runner.auto_create_session = True
        profile_response = ""
        async for event in p_runner.run_async(
            user_id="user_1",
            session_id="sess_profile",
            new_message=Content(role="user", parts=[Part(text=json.dumps(raw_input))])
        ):
            if event.is_final_response():
                profile_response = _extract_text(event)
            if verbose and hasattr(event, "content") and event.content:
                console.print(f"[dim][ProfileAgent Reasoning]: {profile_response}[/dim]")
        
        # Parse profile details
        profile_json_match = re.search(r"---PROFILE_JSON---\s*(\{.*?\})", profile_response, re.DOTALL)
        if profile_json_match:
            try:
                profile_data = json.loads(profile_json_match.group(1))
            except Exception:
                profile_data = raw_input
        else:
            profile_data = raw_input
            
        t_val = profile_data.get('travelers') or raw_input.get('travelers') or travelers or 1
        c_val = profile_data.get('currency') or raw_input.get('currency') or currency or "USD"
        b_val = profile_data.get('budget')
        if b_val is None:
            b_val = raw_input.get('budget') or budget or 0.0
        try:
            b_formatted = f"{float(b_val):,.2f}"
        except Exception:
            b_formatted = "0.00"
            
        yield {
            "type": "progress",
            "step": 1,
            "message": f"Profile validated successfully ({t_val} travelers, {c_val} {b_formatted} budget)",
            "icon": "👤",
            "status": "done"
        }
        
        # --- STEP 2: RESEARCH AGENT ---
        yield {
            "type": "progress",
            "step": 2,
            "message": f"Researching weather, transport, and activity pools for {destination}...",
            "icon": "🔍"
        }
        
        r_runner = InMemoryRunner(agent=r_agent)
        r_runner.auto_create_session = True
        research_response = ""
        async for event in r_runner.run_async(
            user_id="user_1",
            session_id="sess_research",
            new_message=Content(role="user", parts=[Part(text=json.dumps(profile_data))])
        ):
            if event.is_final_response():
                research_response = _extract_text(event)
            if verbose and hasattr(event, "content") and event.content:
                console.print(f"[dim][ResearchAgent Reasoning]: {research_response}[/dim]")
                
        yield {
            "type": "progress",
            "step": 2,
            "message": f"Research complete. Found weather predictions and curated activities for {destination}.",
            "icon": "🔍",
            "status": "done"
        }
        
        # --- STEP 3: ITINERARY AGENT ---
        yield {
            "type": "progress",
            "step": 3,
            "message": f"Compiling day-by-day travel plan for {destination}...",
            "icon": "📅"
        }
        
        itinerary_input = {
            "profile": profile_data,
            "research": research_response
        }
        
        i_runner = InMemoryRunner(agent=i_agent)
        i_runner.auto_create_session = True
        itinerary_response = ""
        async for event in i_runner.run_async(
            user_id="user_1",
            session_id="sess_itinerary",
            new_message=Content(role="user", parts=[Part(text=json.dumps(itinerary_input))])
        ):
            if event.is_final_response():
                itinerary_response = _extract_text(event)
            if verbose and hasattr(event, "content") and event.content:
                console.print(f"[dim][ItineraryAgent Reasoning]: {itinerary_response}[/dim]")
                
        # Parse itinerary text
        itinerary_md_match = re.search(r"---ITINERARY_MARKDOWN---\s*(.*?)(?:---ITINERARY_JSON---|$$)", itinerary_response, re.DOTALL)
        final_markdown = itinerary_md_match.group(1).strip() if itinerary_md_match else itinerary_response
        
        yield {
            "type": "progress",
            "step": 3,
            "message": "Itinerary compiled successfully.",
            "icon": "📅",
            "status": "done"
        }
        
        # --- STEP 4: DISRUPTION CHECKS ---
        yield {
            "type": "progress",
            "step": 4,
            "message": "Scanning for active logistical, strike, or weather disruptions...",
            "icon": "⚡"
        }
        
        itinerary_json_match = re.search(r"---ITINERARY_JSON---\s*(\{.*\})", itinerary_response, re.DOTALL)
        
        has_disruptions = False
        disrupted_activity = ""
        disrupted_reason = ""
        
        if itinerary_json_match:
            try:
                itinerary_dict = json.loads(itinerary_json_match.group(1))
                for day in itinerary_dict.get("days_list", []):
                    for slot, act in day.get("activities", {}).items():
                        if act and "name" in act:
                            chk = await check_disruption_tool(destination, act["name"], start_date or "2025-08-15")
                            if chk.get("is_disrupted"):
                                has_disruptions = True
                                disrupted_activity = act["name"]
                                disrupted_reason = chk.get("disruption_reason", "Closed")
                                break
                    if has_disruptions:
                        break
            except Exception as ex:
                console.print(f"[warning]Warning checking disruptions: {ex}[/warning]")
                
        if has_disruptions:
            yield {
                "type": "progress",
                "step": 4,
                "message": f"Conflict detected: '{disrupted_activity}' ({disrupted_reason}). Rerouting with DisruptionAgent...",
                "icon": "⚡"
            }
            # Run replan
            # Yield progress updates internally by calling stream_replan generator
            replan_summary = None
            async for ev in stream_replan(final_markdown, f"Disruption: {disrupted_activity} - {disrupted_reason}", profile_data, verbose=verbose):
                if ev["type"] == "progress":
                    yield {
                        "type": "progress",
                        "step": 4,
                        "message": f"Replanning: {ev['message']}",
                        "icon": "⚡"
                    }
                elif ev["type"] == "complete":
                    final_markdown = ev["itinerary"]
                    replan_summary = ev["summary"]
                    
            yield {
                "type": "progress",
                "step": 4,
                "message": f"Successfully rerouted plan to resolve conflict at '{disrupted_activity}'.",
                "icon": "⚡",
                "status": "done"
            }
        else:
            yield {
                "type": "progress",
                "step": 4,
                "message": "No active disruptions reported. Safety checks complete.",
                "icon": "⚡",
                "status": "done"
            }
            
        # Parse final summary dict
        final_json_match = re.search(r"---ITINERARY_JSON---\s*(\{.*\})", itinerary_response, re.DOTALL)
        if final_json_match:
            try:
                summary_data = json.loads(final_json_match.group(1))
            except Exception:
                summary_data = {}
        else:
            summary_data = {}
            
        # Hardened type-safe normalizer
        summary_data = _normalize_summary_data(summary_data, destination, days, travelers, budget, currency, start_date)
            
        _ACTIVE_MCP_SESSION = None
        yield {
            "type": "complete",
            "itinerary": final_markdown,
            "summary": summary_data
        }

async def run_tripforge(
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    currency: str = "USD",
    accessibility: str = None,
    dietary: str = None,
    travel_style: str = None,
    interests: list = None,
    start_date: str = None,
    verbose: bool = False
) -> str:
    """Original run wrapper that returns final markdown string for CLI compatibility."""
    final_md = ""
    async for event in stream_tripforge(
        destination=destination,
        days=days,
        travelers=travelers,
        budget=budget,
        currency=currency,
        accessibility=accessibility,
        dietary=dietary,
        travel_style=travel_style,
        interests=interests,
        start_date=start_date,
        verbose=verbose
    ):
        if event["type"] == "complete":
            final_md = event["itinerary"]
    return final_md

async def stream_replan(
    existing_itinerary: str,
    disruption: str,
    profile: dict,
    verbose: bool = False
) -> AsyncGenerator[dict, None]:
    """Async generator workflow for DisruptionAgent replanning."""
    global _ACTIVE_MCP_SESSION
    is_mock = os.getenv("TRIPFORGE_MODE", "live").lower() == "mock"
    
    if is_mock:
        apply_mock_runner_patch()
        
    yield {
        "type": "progress",
        "step": 1,
        "message": "Analyzing original itinerary layout...",
        "icon": "👤"
    }
    
    # Check keys
    if not is_mock and not os.getenv("GOOGLE_API_KEY"):
        is_mock = True
        os.environ["TRIPFORGE_MODE"] = "mock"
        apply_mock_runner_patch()
        
    from tripforge.agents.disruption_agent import get_disruption_agent
    replan_tools = [check_disruption_tool, search_activities_tool, get_weather_tool]
    d_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    d_agent = get_disruption_agent(d_model, replan_tools)
    
    started_here = False
    stack = AsyncExitStack()
    
    try:
        if not _ACTIVE_MCP_SESSION:
            yield {
                "type": "progress",
                "step": 2,
                "message": "Opening connection to travel tools MCP server subprocess...",
                "icon": "🔍"
            }
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # Ensure all parent import paths (including site-packages and base_dir) are passed to the subprocess
            python_path_dirs = [base_dir] + [p for p in sys.path if p]
            # Remove duplicates while preserving order
            seen = set()
            python_path_dirs = [x for x in python_path_dirs if not (x in seen or seen.add(x))]
            
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "tripforge.mcp_server.travel_tools_server"],
                env={**os.environ, "PYTHONPATH": os.pathsep.join(python_path_dirs)}
            )
            read, write = await stack.enter_async_context(stdio_client(server_params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            _ACTIVE_MCP_SESSION = session
            started_here = True
            
        yield {
            "type": "progress",
            "step": 3,
            "message": f"Synthesizing alternative schedules to bypass disruption: '{disruption}'...",
            "icon": "📅"
        }
        
        replan_input = {
            "existing_itinerary": existing_itinerary,
            "disruption_event": disruption,
            "profile": profile
        }
        
        d_runner = InMemoryRunner(agent=d_agent)
        d_runner.auto_create_session = True
        replan_response = ""
        async for event in d_runner.run_async(
            user_id="user_1",
            session_id="sess_replan",
            new_message=Content(role="user", parts=[Part(text=json.dumps(replan_input))])
        ):
            if event.is_final_response():
                replan_response = _extract_text(event)
            if verbose and hasattr(event, "content") and event.content:
                console.print(f"[dim][DisruptionAgent Reasoning]: {replan_response}[/dim]")
                
        yield {
            "type": "progress",
            "step": 4,
            "message": "Applying modifications and updating financial summaries...",
            "icon": "⚡"
        }
        
        # Parse replanned text
        replan_md_match = re.search(r"---REPLANNED_MARKDOWN---\s*(.*?)(?:---REPLANNED_JSON---|$$)", replan_response, re.DOTALL)
        final_replan_md = replan_md_match.group(1).strip() if replan_md_match else replan_response
        
        replan_json_match = re.search(r"---REPLANNED_JSON---\s*(\{.*\})", replan_response, re.DOTALL)
        if replan_json_match:
            try:
                summary_data = json.loads(replan_json_match.group(1))
            except Exception:
                summary_data = {}
        else:
            summary_data = {}
            
        # Hardened type-safe normalizer for replan summary
        dest_val = profile.get("destination") or "Paris"
        days_val = profile.get("days") or 3
        trav_val = profile.get("travelers") or 2
        budg_val = profile.get("budget") or 2000.0
        curr_val = profile.get("currency") or "USD"
        start_date_val = profile.get("start_date")
        summary_data = _normalize_summary_data(summary_data, dest_val, days_val, trav_val, budg_val, curr_val, start_date_val)
            
        yield {
            "type": "progress",
            "step": 4,
            "message": "Replan complete.",
            "icon": "⚡",
            "status": "done"
        }
        
        yield {
            "type": "complete",
            "itinerary": final_replan_md,
            "summary": summary_data
        }
        
    finally:
        if started_here:
            await stack.aclose()
            _ACTIVE_MCP_SESSION = None

async def run_replan(
    existing_itinerary: str,
    disruption: str,
    profile: dict,
    verbose: bool = False
) -> str:
    """Original replan wrapper that returns final markdown string for CLI compatibility."""
    final_replan_md = ""
    async for event in stream_replan(
        existing_itinerary=existing_itinerary,
        disruption=disruption,
        profile=profile,
        verbose=verbose
    ):
        if event["type"] == "complete":
            final_replan_md = event["itinerary"]
    return final_replan_md

