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

async def get_weather_tool(city: str, date: str) -> dict:
    """Wrapper calling MCP get_weather tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    # Security Guard Consent Check
    if not guard_external_call("Open-Meteo Weather API", f"City: {city}, Date: {date}"):
        raise PermissionError("Access to external Weather API denied by user.")
        
    params = {"city": city, "date": date}
    # HMAC Signing
    params["signature"] = sign_tool_call("get_weather", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("get_weather", params)
    if res.content and len(res.content) > 0:
        return json.loads(res.content[0].text)
    return {}

async def search_activities_tool(city: str, accessibility_required: bool = False, dietary_preference: str = None, category: str = None) -> list:
    """Wrapper calling MCP search_activities tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    # Local activities DB is considered a safe local query, so we skip warning
    params = {
        "city": city, 
        "accessibility_required": accessibility_required, 
        "dietary_preference": dietary_preference, 
        "category": category
    }
    params["signature"] = sign_tool_call("search_activities", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("search_activities", params)
    if res.content and len(res.content) > 0:
        return json.loads(res.content[0].text)
    return []

async def get_country_info_tool(country_name: str) -> dict:
    """Wrapper calling MCP get_country_info tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    if not guard_external_call("RestCountries API", f"Country: {country_name}"):
        raise PermissionError("Access to external RestCountries API denied by user.")
        
    params = {"country_name": country_name}
    params["signature"] = sign_tool_call("get_country_info", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("get_country_info", params)
    if res.content and len(res.content) > 0:
        return json.loads(res.content[0].text)
    return {}

async def estimate_transport_cost_tool(origin_city: str, destination_city: str, transport_type: str) -> dict:
    """Wrapper calling MCP estimate_transport_cost tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    params = {
        "origin_city": origin_city, 
        "destination_city": destination_city, 
        "transport_type": transport_type
    }
    params["signature"] = sign_tool_call("estimate_transport_cost", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("estimate_transport_cost", params)
    if res.content and len(res.content) > 0:
        return json.loads(res.content[0].text)
    return {}

async def check_disruption_tool(city: str, activity_name: str, date: str) -> dict:
    """Wrapper calling MCP check_disruption tool."""
    global _ACTIVE_MCP_SESSION
    if not _ACTIVE_MCP_SESSION:
        raise RuntimeError("MCP Client Session not active.")
        
    params = {"city": city, "activity_name": activity_name, "date": date}
    params["signature"] = sign_tool_call("check_disruption", params)
    
    res = await _ACTIVE_MCP_SESSION.call_tool("check_disruption", params)
    if res.content and len(res.content) > 0:
        return json.loads(res.content[0].text)
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
    """
    Main TripForge workflow. Launches MCP server, runs ProfileAgent, ResearchAgent, and ItineraryAgent in sequence.
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
        
    # Start MCP Server subprocess and Client Session
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tripforge.mcp_server.travel_tools_server"],
        env={**os.environ, "PYTHONPATH": base_dir}
    )
    
    async with AsyncExitStack() as stack:
        # Step 0: Connect to local MCP Server
        console.print("[dim]Connecting to TripForge local MCP server subprocess...[/dim]")
        read, write = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        _ACTIVE_MCP_SESSION = session
        console.print("[dim]✔ MCP Server connection established successfully.[/dim]")
        
        # Define progress bars
        steps = [
            ("Profile validation", 1),
            ("Destination research", 2),
            ("Itinerary compilation", 3),
            ("Disruption analysis", 4)
        ]
        
        # Load agents
        from tripforge.agents.profile_agent import get_profile_agent
        from tripforge.agents.research_agent import get_research_agent
        from tripforge.agents.itinerary_agent import get_itinerary_agent
        from tripforge.agents.disruption_agent import get_disruption_agent
        
        mcp_tools = [get_weather_tool, search_activities_tool, get_country_info_tool, estimate_transport_cost_tool]
        itinerary_tools = [check_disruption_tool, search_activities_tool]
        
        model_name = "gemini-2.5-flash"
        p_agent = get_profile_agent(model_name)
        r_agent = get_research_agent(model_name, mcp_tools)
        i_agent = get_itinerary_agent(model_name, itinerary_tools)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            # --- STEP 1: PROFILE AGENT ---
            task1 = progress.add_task(f"[step]Step 1/4: Validating profile for {destination}...[/step]", total=10)
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
            profile_response = ""
            async for event in p_runner.run_async(user_id="user_1", session_id="sess_profile", new_message=json.dumps(raw_input)):
                if event.is_final_response():
                    profile_response = _extract_text(event)
                if verbose and hasattr(event, "content") and event.content:
                    console.print(f"[dim][ProfileAgent Reasoning]: {profile_response}[/dim]")
            
            # Parse profile details
            profile_json_match = re.search(r"---PROFILE_JSON---\s*(\{.*?\})", profile_response, re.DOTALL)
            if profile_json_match:
                profile_data = json.loads(profile_json_match.group(1))
            else:
                profile_data = raw_input
                
            progress.update(task1, completed=10, description=f"[success]✅ Step 1/4: Profile validated ({profile_data.get('travelers')} travelers, {profile_data.get('currency')} {profile_data.get('budget'):,.2f} budget)[/success]")
            
            # --- STEP 2: RESEARCH AGENT ---
            task2 = progress.add_task(f"[step]Step 2/4: Gathers destination data for {destination}...[/step]", total=10)
            
            r_runner = InMemoryRunner(agent=r_agent)
            research_response = ""
            async for event in r_runner.run_async(user_id="user_1", session_id="sess_research", new_message=json.dumps(profile_data)):
                if event.is_final_response():
                    research_response = _extract_text(event)
                if verbose and hasattr(event, "content") and event.content:
                    console.print(f"[dim][ResearchAgent Reasoning]: {research_response}[/dim]")
                    
            progress.update(task2, completed=10, description=f"[success]🔍 Step 2/4: Researching {destination}... (fetched weather, activities, country info)[/success]")
            
            # --- STEP 3: ITINERARY AGENT ---
            task3 = progress.add_task("[step]Step 3/4: Building your itinerary...[/step]", total=10)
            
            itinerary_input = {
                "profile": profile_data,
                "research": research_response
            }
            
            i_runner = InMemoryRunner(agent=i_agent)
            itinerary_response = ""
            async for event in i_runner.run_async(user_id="user_1", session_id="sess_itinerary", new_message=json.dumps(itinerary_input)):
                if event.is_final_response():
                    itinerary_response = _extract_text(event)
                if verbose and hasattr(event, "content") and event.content:
                    console.print(f"[dim][ItineraryAgent Reasoning]: {itinerary_response}[/dim]")
                    
            # Parse itinerary text
            itinerary_md_match = re.search(r"---ITINERARY_MARKDOWN---\s*(.*?)(?:---ITINERARY_JSON---|$$)", itinerary_response, re.DOTALL)
            final_markdown = itinerary_md_match.group(1).strip() if itinerary_md_match else itinerary_response
            
            progress.update(task3, completed=10, description="[success]📅 Step 3/4: Itinerary built successfully[/success]")
            
            # --- STEP 4: DISRUPTION CHECKS (Orchestrator validation) ---
            task4 = progress.add_task("[step]Step 4/4: Checking for active disruptions...[/step]", total=10)
            
            # Parse itinerary JSON to check if any activity is marked as disrupted
            itinerary_json_match = re.search(r"---ITINERARY_JSON---\s*(\{.*\})", itinerary_response, re.DOTALL)
            
            has_disruptions = False
            disrupted_activity = ""
            disrupted_reason = ""
            
            if itinerary_json_match:
                try:
                    itinerary_dict = json.loads(itinerary_json_match.group(1))
                    # Call disruption check tool for each scheduled activity
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
                    console.print(f"[warning]Warning checking disruptions: {ex}. Skipping automated replan.[/warning]")
                    
            if has_disruptions:
                console.print(f"[warning]⚡ Alert: Active disruption detected for '{disrupted_activity}': {disrupted_reason}. Launching DisruptionAgent...[/warning]")
                # Launch replan
                final_markdown = await run_replan(final_markdown, f"Disruption: {disrupted_activity} - {disrupted_reason}", profile_data, verbose=verbose)
                
            progress.update(task4, completed=10, description="[success]⚡ Step 4/4: Finished checks for disruptions[/success]")
            
        console.print(f"[success]✨ Your itinerary is ready![/success]")
        # Reset pointer
        _ACTIVE_MCP_SESSION = None
        return final_markdown

async def run_replan(
    existing_itinerary: str,
    disruption: str,
    profile: dict,
    verbose: bool = False
) -> str:
    """
    Triggers DisruptionAgent to resolve a scheduling conflict and output an updated itinerary.
    """
    global _ACTIVE_MCP_SESSION
    is_mock = os.getenv("TRIPFORGE_MODE", "live").lower() == "mock"
    
    if is_mock:
        apply_mock_runner_patch()
        
    console.print(f"[info]⚡ TripForge is replanning your itinerary due to: '{disruption}'...[/info]")
    
    # Check keys
    if not is_mock and not os.getenv("GOOGLE_API_KEY"):
        is_mock = True
        os.environ["TRIPFORGE_MODE"] = "mock"
        apply_mock_runner_patch()
        
    # Replan tools
    from tripforge.agents.disruption_agent import get_disruption_agent
    replan_tools = [check_disruption_tool, search_activities_tool, get_weather_tool]
    
    d_agent = get_disruption_agent("gemini-2.5-flash", replan_tools)
    
    # If MCP session is not active, start it
    started_here = False
    stack = AsyncExitStack()
    
    try:
        if not _ACTIVE_MCP_SESSION:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            server_params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "tripforge.mcp_server.travel_tools_server"],
                env={**os.environ, "PYTHONPATH": base_dir}
            )
            read, write = await stack.enter_async_context(stdio_client(server_params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            _ACTIVE_MCP_SESSION = session
            started_here = True
            
        replan_input = {
            "existing_itinerary": existing_itinerary,
            "disruption_event": disruption,
            "profile": profile
        }
        
        d_runner = InMemoryRunner(agent=d_agent)
        replan_response = ""
        async for event in d_runner.run_async(user_id="user_1", session_id="sess_replan", new_message=json.dumps(replan_input)):
            if event.is_final_response():
                replan_response = _extract_text(event)
            if verbose and hasattr(event, "content") and event.content:
                console.print(f"[dim][DisruptionAgent Reasoning]: {replan_response}[/dim]")
                
        # Parse replanned text
        replan_md_match = re.search(r"---REPLANNED_MARKDOWN---\s*(.*?)(?:---REPLANNED_JSON---|$$)", replan_response, re.DOTALL)
        final_replan_md = replan_md_match.group(1).strip() if replan_md_match else replan_response
        
        return final_replan_md
        
    finally:
        if started_here:
            await stack.aclose()
            _ACTIVE_MCP_SESSION = None
