# 🌍 TripForge

> **AI-powered hyper-personalized travel planning agent**

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Kaggle Competition](https://img.shields.io/badge/Kaggle-Vibecoding%20Agents%20Capstone-blueviolet.svg)](https://www.kaggle.com/)

---

## 📖 What is TripForge?

TripForge is an autonomous, multi-agent travel concierge system developed for the Kaggle "Vibecoding Agents Capstone Project" competition. The system takes traveler preferences (such as destination, budget, accessibility needs, and dietary restrictions) and designs a custom, day-by-day travel itinerary. Leveraging real-time Model Context Protocol (MCP) tools and Google's Agent Development Kit (ADK), it dynamically monitors local weather, transit costs, and active city disruptions to adapt plans instantly when strikes, cancellations, or weather disruptions occur.

---

## 🏗️ System Architecture

TripForge is orchestrated around a sequential multi-agent pipeline linked to a standalone Model Context Protocol (MCP) server:

```
   User Input
       │
       ▼
   ┌─────────────────────────────────────────┐
   │           TripForge Orchestrator         │
   └─────────────────────────────────────────┘
       │           │           │           │
       ▼           ▼           ▼           ▼
   Profile     Research    Itinerary  Disruption
    Agent       Agent        Agent      Agent
       │           │           │           │
       └───────────┴───────────┴───────────┘
                       │
                       ▼
           ┌───────────────────────┐
           │      MCP Server       │
           │  ┌─────────────────┐  │
           │  │  Weather Tool   │  │
           │  │ Activity Search │  │
           │  │  Country Info   │  │
           │  │  Transport Est. │  │
           │  │ Disruption Check│  │
           └──┴─────────────────┴──┘
                       │
                       ▼
               External APIs
          (Open-Meteo, RestCountries,
           Local Activities DB)
```

---

## 🚀 Quick Start

Get your system set up and running in live mode:

```bash
# Clone the repository
git clone https://github.com/yourusername/tripforge
cd tripforge

# Install package in editable mode
pip install -e .

# Copy environment template and fill in API keys
cp .env.example .env
```

Open `.env` and add your Google Gemini and OpenWeatherMap credentials:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
OPENWEATHERMAP_API_KEY=your_openweathermap_api_key_here
```

Generate your first plan:
```bash
tripforge plan --destination "Paris" --days 3 --travelers 2 --budget 1500 --interests "art,food"
```

---

## ⚡ Try Without API Keys (Mock Mode)

To allow instant testing and grading, TripForge includes a full mock simulation pipeline. If no API keys are present, or when calling the `demo` command, the system automatically patches the ADK runner to simulate reasoning offline.

Execute the demo instantly:
```bash
tripforge demo
```
This runs the full multi-agent orchestrator offline, starts the local MCP server, checks for mock disruptions, and saves a beautiful 3-day Paris itinerary to `paris_trip.md`.

---

## 🕹️ CLI Commands & Examples

### 1. `tripforge plan`
Generate an itinerary matching custom constraints.
```bash
tripforge plan \
  --destination "Paris" \
  --days 3 \
  --travelers 2 \
  --budget 2000 \
  --currency USD \
  --accessibility "wheelchair" \
  --dietary "gluten-free" \
  --interests "art,food" \
  --output "paris_trip.md"
```

### 2. `tripforge replan`
Rebuild an itinerary to resolve a disruption.
```bash
tripforge replan \
  --itinerary paris_trip.md \
  --disruption "Louvre closed due to strike" \
  --output "paris_trip_updated.md"
```

### 3. `tripforge profile create`
Securely validate and save traveler preferences as encrypted JSON files.
```bash
tripforge profile create \
  --name "family-paris" \
  --travelers 4 \
  --accessibility "wheelchair" \
  --dietary "gluten-free" \
  --interests "art,food" \
  --save "profiles/family.json"
```

### 4. `tripforge profile list`
List all saved traveler profiles in the local database.
```bash
tripforge profile list
```

---

## 🏆 Kaggle Capstone Concepts

TripForge demonstrates the four core components of the Kaggle Vibecoding Agent Capstone:

| Concept | Location in Codebase | Description |
| :--- | :--- | :--- |
| **Multi-Agent System (ADK)** | [tripforge/agents/](file:///d:/codingProject/GITHUB/Kaggle/tripforge/agents/) | Uses Google's code-first `google-adk` framework to implement four specialized agents: Profile, Research, Itinerary, and Disruption Agents. |
| **MCP Server** | [tripforge/mcp_server/](file:///d:/codingProject/GITHUB/Kaggle/tripforge/mcp_server/) | Runs a standalone Python Model Context Protocol server exposing weather, activities database searches, and disruption checkers. |
| **Antigravity** | [tripforge/cli.py](file:///d:/codingProject/GITHUB/Kaggle/tripforge/cli.py) | Created autonomously by the Antigravity developer agent. Demonstrates clean code, offline fallback loops, and Windows console safety. |
| **Agent Skills (CLI)** | [tripforge/cli.py](file:///d:/codingProject/GITHUB/Kaggle/tripforge/cli.py) | Exposes all agent commands using `Click` and renders outputs using `Rich` tables, columns, progress indicators, and spinners. |

---

## 🔒 Implemented Security Features

TripForge is built with robust security controls to protect traveler privacy:

1. **Profile Data Encryption**: Traveler profiles are stored encrypted using symmetric Fernet cryptography. The key is derived dynamically at runtime from machine-specific hardware fingerprints (UUID/node properties) and is never stored on disk.
2. **PII Scrubbing**: Logs are automatically scrubbed using regex rules to replace emails, phone numbers, and passport-like digits with `[REDACTED]` tokens.
3. **Input Sanitization**: Input fields are validated against strict filters. Destinations are checked against supported cities, and budgets are limited to a safe range ($10 - $1,000,000) to block injection patterns.
4. **MCP Call Signing**: MCP tool calls are signed with an HMAC-SHA256 signature containing parameters and verified by the server before tool execution.
5. **No-Cloud-Sync Guard**: Generates console alerts before querying external services and prompts the user for consent before making outgoing live connections containing query parameters.

---

## 📁 Project Structure

```
tripforge/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── data/
│   └── activities_db.json
├── tests/
│   └── test_tripforge.py
├── tripforge/
│   ├── __init__.py
│   ├── cli.py
│   ├── orchestrator.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── profile_agent.py
│   │   ├── research_agent.py
│   │   ├── itinerary_agent.py
│   │   └── disruption_agent.py
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   └── travel_tools_server.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── weather_tool.py
│   │   ├── activities_tool.py
│   │   └── country_info_tool.py
│   └── utils/
│       ├── __init__.py
│       ├── security.py
│       └── formatters.py
└── profiles/
    └── .gitkeep
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
