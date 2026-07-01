# 🌍 TripForge

> **AI-powered hyper-personalized travel planning web agent**

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Kaggle Competition](https://img.shields.io/badge/Kaggle-Vibecoding%20Agents%20Capstone-blueviolet.svg)](https://www.kaggle.com/)

---

## 📖 What is TripForge?

TripForge is an autonomous, multi-agent travel concierge system developed for the Kaggle "Vibecoding Agents Capstone Project" competition. The system accepts traveler preferences (such as destination, budget, accessibility needs, and dietary restrictions) through a beautiful web dashboard and designs a custom, day-by-day travel itinerary. Leveraging real-time Model Context Protocol (MCP) tools and Google's Agent Development Kit (ADK), it dynamically monitors local weather, transit costs, and active city disruptions to adapt plans instantly in the browser when strikes, closures, or weather disruptions occur.

The application streams agent progress in real time using Server-Sent Events (SSE) so users can watch each agent working live under the hood.

---

## 🏗️ System Architecture

TripForge is orchestrated around a sequential multi-agent pipeline linked to a standalone Model Context Protocol (MCP) server, serving outputs directly to a Flask web server:

```
              User Web browser
                     │
                     ▼
         ┌───────────────────────┐
         │   Flask Web Server    │
         │       (app.py)        │
         └───────────────────────┘
                     │  (SSE Logs / Redirects)
                     ▼
         ┌───────────────────────┐
         │ TripForge Orchestrator│
         └───────────────────────┘
             │   │   │   │
             ▼   ▼   ▼   ▼
         Profile Research Itinerary Disruption
          Agent    Agent     Agent     Agent
             │   │   │   │
             └─┬─┴─┬─┴─┬─┘
               │   │   │
               ▼   ▼   ▼
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

Open `.env` and add your Google Gemini API key:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

Launch the Flask web server:
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser to plan your first journey!

---

## ⚡ Try Without API Keys (Mock Mode)

To allow instant testing and grading, TripForge includes a full mock simulation pipeline. If no API keys are present in the environment, the system automatically redirects to the mock generator runner.

You can trigger a pre-configured demo with one click:
1. Navigate to **[http://127.0.0.1:5000/demo](http://127.0.0.1:5000/demo)**.
2. Click **🎬 Launch Demo Scenario**.
3. Watch the step checklist (👤 $\rightarrow$ 🔍 $\rightarrow$ 📅 $\rightarrow$ ⚡) and raw logs stream live in the browser as the agents coordinate offline data.

---

## 🏆 Kaggle Capstone Concepts

TripForge demonstrates the four core components of the Kaggle Vibecoding Agent Capstone:

| Concept | Location in Codebase | Description |
| :--- | :--- | :--- |
| **Multi-Agent System (ADK)** | [tripforge/agents/](file:///d:/codingProject/GITHUB/Kaggle/tripforge/agents/) | Uses Google's code-first `google-adk` framework to implement four specialized agents: Profile, Research, Itinerary, and Disruption Agents. |
| **MCP Server** | [tripforge/mcp_server/](file:///d:/codingProject/GITHUB/Kaggle/tripforge/mcp_server/) | Runs a standalone Python Model Context Protocol server exposing weather, activities database searches, and disruption checkers over stdio transport. |
| **Antigravity** | [app.py](file:///d:/codingProject/GITHUB/Kaggle/app.py) | Created autonomously by the Antigravity developer agent. Features clean code, offline fallback loops, and Windows console safety. |
| **Agent Skills (Web UI)** | [templates/](file:///d:/codingProject/GITHUB/Kaggle/templates/) | Exposes all agent interactions and live logs using a responsive Flask web application with real-time SSE streaming. |

---

## 🔒 Implemented Security Features

TripForge is built with robust security controls to protect traveler privacy:

1. **Profile Data Encryption**: Traveler preferences are validated and encrypted using symmetric Fernet cryptography with a dynamically derived hardware fingerprint (no key saved on disk).
2. **PII Scrubbing**: Logs are automatically scrubbed using regex rules to replace emails, phone numbers, and passport-like digits with `[REDACTED]` tokens.
3. **Input Sanitization**: Input fields are validated against strict filters. Destinations are checked against supported cities, and budgets are limited to a safe range ($10 - $1,000,000) to block injection patterns.
4. **MCP Call Signing**: MCP tool calls are signed with an HMAC-SHA256 signature containing parameters and verified by the server before tool execution.
5. **No-Cloud-Sync Guard**: Warns before querying external services and prompts the user for consent before making outgoing live connections.

---

## 📁 Project Structure

```
tripforge/
├── app.py                          # Flask application entry point
├── pyproject.toml                  # Package dependencies config
├── requirements.txt                # Python requirements
├── .env.example                    # Environment variable template
├── .gitignore                      # Excludes .env, outputs, etc.
├── README.md                       # Competition documentation
├── data/
│   └── activities_db.json          # Local activities database
├── templates/                      # Flask HTML templates
│   ├── base.html                   # Core layout skeleton
│   ├── index.html                  # Main interactive planning form
│   ├── result.html                 # Dual-state progress stream + results page
│   ├── replan.html                 # Standalone disruption resolver
│   └── demo.html                   # Pre-configured demo dashboard
├── static/                         # Static assets
│   ├── css/
│   │   └── custom.css              # Custom font styles and animations
│   └── js/
│       └── stream.js               // SSE streaming logic receiver
├── tripforge/
│   ├── __init__.py
│   ├── orchestrator.py             # Generator-based multi-agent pipeline
│   ├── agents/                     # Google ADK Agents
│   │   ├── __init__.py
│   │   ├── profile_agent.py
│   │   ├── research_agent.py
│   │   ├── itinerary_agent.py
│   │   └── disruption_agent.py
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   └── travel_tools_server.py  # Python MCP SDK travel tools server
│   └── utils/
│       ├── __init__.py
│       ├── security.py             # HMAC, Fernet keys, and PII redactor
│       └── formatters.py           # HTML summary tables compiler
└── profiles/
    └── .gitkeep
```

---


