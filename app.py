# File: app.py
# Purpose: Core entry point for the Flask web application.
# Competition Concept: Agent Skills (Web Integration) & Orchestration

import os
import sys

# Configure terminal streams to support UTF-8 characters on Windows legacy shells
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uuid
import json
import asyncio
import re
from flask import Flask, render_template, request, session, redirect, url_for, Response, jsonify, send_file
from dotenv import load_dotenv

# Ensure the project root directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["TRIPFORGE_WEB_MODE"] = "true"

from tripforge.orchestrator import stream_tripforge, stream_replan
from tripforge.utils.security import sanitize_destination, sanitize_budget
import traceback
from datetime import datetime

def log_pipeline_error(error: Exception):
    """Logs the full exception traceback to stderr and a dedicated tripforge.log file."""
    timestamp = datetime.now().isoformat()
    tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    
    # 1. Output to standard error (visible in running terminal)
    sys.stderr.write(f"\n[{timestamp}] [PIPELINE_ERROR] Exception caught:\n{tb_str}\n")
    sys.stderr.flush()
    
    # 2. Append to a persistent tripforge.log file in the project directory
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tripforge.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Error Type: {type(error).__name__}\n")
            f.write(f"Error Message: {str(error)}\n")
            f.write(f"Traceback:\n{tb_str}")
            f.write(f"{'='*80}\n")
    except OSError as e:
        # Silently ignore read-only file system errors (e.g. on Vercel)
        if e.errno != 30:
            sys.stderr.write(f"Failed to write to log file {log_path}: {e}\n")
            sys.stderr.flush()
    except Exception as log_err:
        sys.stderr.write(f"Failed to write to log file {log_path}: {log_err}\n")
        sys.stderr.flush()

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Secure fallback secret key for development session encryption
app.secret_key = os.getenv("FLASK_SECRET_KEY", "tripforge-secure-web-secret-987654")

# Global caches for storing streaming itineraries (since Flask cookies cannot be modified during stream writes)
ITINERARY_CACHE = {}
SUMMARY_CACHE = {}
INPUT_CACHE = {}

@app.before_request
def ensure_session_id():
    """Generates a stable unique identifier for cached itinerary storage per user."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

@app.after_request
def set_security_headers(response):
    """Sets standard security headers on all responses to satisfy competition rules."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Allow Tailwind CSS, Marked.js, Google Fonts, and Leaflet Map assets
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' cdn.tailwindcss.com cdn.jsdelivr.net fonts.googleapis.com fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' cdn.tailwindcss.com fonts.googleapis.com unpkg.com; "
        "font-src 'self' fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline' cdn.tailwindcss.com cdn.jsdelivr.net unpkg.com; "
        "img-src 'self' data: https://*.basemaps.cartocdn.com https://*.tile.openstreetmap.org unpkg.com; "
        "connect-src 'self'"
    )
    return response

@app.route("/")
def index():
    """Renders index.html containing the trip planning preferences form."""
    return render_template("index.html")

@app.route("/plan", methods=["POST"])
def plan():
    """Validates inputs using the security module and stores parameters in the user session."""
    dest = request.form.get("destination", "").strip()
    days_raw = request.form.get("days", "7")
    travelers_raw = request.form.get("travelers", "2")
    budget_raw = request.form.get("budget", "")
    currency = request.form.get("currency", "USD")
    accessibility = request.form.get("accessibility")
    dietary_list = request.form.getlist("dietary") # list of checkboxes
    interests_list = request.form.getlist("interests") # list of interest pills
    start_date = request.form.get("start_date")
    
    # 1. Input Validation and Security Sanitations
    try:
        sanitized_dest = sanitize_destination(dest)
        sanitized_budget = sanitize_budget(budget_raw)
        days = int(days_raw)
        travelers = int(travelers_raw)
        
        if days < 1 or days > 30:
            raise ValueError("Number of days must be between 1 and 30.")
        if travelers < 1 or travelers > 20:
            raise ValueError("Number of travelers must be between 1 and 20.")
            
    except ValueError as e:
        return render_template("index.html", error=str(e), form_data=request.form)
        
    # Store parameters in session
    session_id = session["session_id"]
    INPUT_CACHE[session_id] = {
        "destination": sanitized_dest,
        "days": days,
        "travelers": travelers,
        "budget": sanitized_budget,
        "currency": currency,
        "accessibility": accessibility if accessibility != "None" else None,
        "dietary": ", ".join(dietary_list) if dietary_list else None,
        "interests": interests_list,
        "start_date": start_date if start_date else None
    }
    
    session["replan_mode"] = False
    mock_mode_raw = request.form.get("mock_mode", "false")
    session["mock_mode"] = (mock_mode_raw == "true") or (os.getenv("TRIPFORGE_MODE", "live").lower() == "mock") or not os.getenv("GOOGLE_API_KEY")
    
    # Store bypass guard pre-grant consent
    bypass_guard_raw = request.form.get("bypass_guard", "false")
    session["bypass_guard"] = (bypass_guard_raw == "true")
    
    return redirect(url_for("stream_page"))

@app.route("/stream")
def stream_page():
    """Renders the live progress tracking page (result.html State 1)."""
    return render_template("result.html", streaming=True)

@app.route("/stream/events")
def stream_events():
    """SSE endpoint executing the multi-agent orchestration and yielding live JSON updates."""
    import queue
    import threading

    session_id = session.get("session_id")
    replan_mode = session.get("replan_mode", False)
    is_mock = session.get("mock_mode", False)
    
    if is_mock:
        os.environ["TRIPFORGE_MODE"] = "mock"
    else:
        os.environ["TRIPFORGE_MODE"] = "live"
        
    # Configure bypass guard based on user pre-consent
    bypass_guard = session.get("bypass_guard", True)
    if bypass_guard:
        os.environ["TRIPFORGE_BYPASS_GUARD"] = "true"
    else:
        os.environ["TRIPFORGE_BYPASS_GUARD"] = "false"
        
    inputs = INPUT_CACHE.get(session_id, {})
    disruption = session.get("disruption_event", "General delay") if replan_mode else None
    existing_itinerary = ITINERARY_CACHE.get(session_id, "") if replan_mode else ""
    
    def event_generator():
        q = queue.Queue()
        
        def run_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def run_pipeline():
                try:
                    if replan_mode:
                        profile_dummy = {
                            "destination": inputs.get("destination", "Paris"),
                            "days": inputs.get("days", 3),
                            "travelers": inputs.get("travelers", 2),
                            "budget": inputs.get("budget", 2000.0),
                            "currency": inputs.get("currency", "USD"),
                            "accessibility_needs": inputs.get("accessibility"),
                            "dietary_restrictions": inputs.get("dietary"),
                            "interests": inputs.get("interests", [])
                        }
                        generator = stream_replan(
                            existing_itinerary=existing_itinerary,
                            disruption=disruption,
                            profile=profile_dummy
                        )
                    else:
                        generator = stream_tripforge(
                            destination=inputs.get("destination"),
                            days=inputs.get("days", 7),
                            travelers=inputs.get("travelers", 2),
                            budget=inputs.get("budget", 2000.0),
                            currency=inputs.get("currency", "USD"),
                            accessibility=inputs.get("accessibility"),
                            dietary=inputs.get("dietary"),
                            interests=inputs.get("interests"),
                            start_date=inputs.get("start_date")
                        )
                    
                    async for event in generator:
                        q.put(event)
                except Exception as e:
                    log_pipeline_error(e)
                    err_msg = str(e)
                    if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg or "quota" in err_msg.lower():
                        friendly_msg = "Gemini API rate limit or quota exceeded (429 Resource Exhausted). Please wait a minute before retrying, or check 'Enable Mock Mode' below the launch button to run offline."
                    else:
                        friendly_msg = f"Pipeline failed: {err_msg}"
                    q.put({"type": "error", "message": friendly_msg})
                finally:
                    q.put(None)
            
            try:
                loop.run_until_complete(run_pipeline())
            finally:
                loop.close()
                
        t = threading.Thread(target=run_async_loop)
        t.start()
        
        while True:
            event = q.get()
            if event is None:
                break
            if isinstance(event, dict) and event.get("type") == "error":
                yield f"data: {json.dumps(event)}\n\n"
                break
            if isinstance(event, dict) and event.get("type") == "complete":
                ITINERARY_CACHE[session_id] = event["itinerary"]
                SUMMARY_CACHE[session_id] = event["summary"]
            yield f"data: {json.dumps(event)}\n\n"
            
        t.join()
            
    response = Response(event_generator(), content_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response

@app.route("/result")
def result():
    """Renders result.html showing the completed day-by-day itinerary and summary tables."""
    session_id = session.get("session_id")
    itinerary = ITINERARY_CACHE.get(session_id)
    summary = SUMMARY_CACHE.get(session_id)
    
    if not itinerary:
        return redirect(url_for("index"))
        
    return render_template("result.html", streaming=False, itinerary=itinerary, summary=summary)

@app.route("/replan", methods=["POST"])
def replan():
    """Accepts a disruption, sets session flags, and redirects to stream page to update plan."""
    disruption = request.form.get("disruption", "").strip()
    if not disruption:
        disruption = "Unexpected logistical delay"
        
    session["replan_mode"] = True
    session["disruption_event"] = disruption
    
    return jsonify({"status": "ok", "redirect": url_for("stream_page")})

@app.route("/demo")
def demo():
    """Renders the offline demonstration page."""
    return render_template("demo.html")

@app.route("/demo/run")
def demo_run():
    """Triggers the pre-configured mock scenario for judges."""
    session_id = session["session_id"]
    
    # Configure mock inputs
    INPUT_CACHE[session_id] = {
        "destination": "Paris",
        "days": 3,
        "travelers": 2,
        "budget": 2000.0,
        "currency": "EUR",
        "accessibility": None,
        "dietary": None,
        "interests": ["culture", "food", "history"],
        "start_date": "2025-08-15"
    }
    
    session["replan_mode"] = False
    session["mock_mode"] = True
    
    return redirect(url_for("stream_page"))

@app.route("/download")
def download():
    """Outputs the markdown itinerary as a downloadable attachment."""
    session_id = session.get("session_id")
    itinerary = ITINERARY_CACHE.get(session_id)
    inputs = INPUT_CACHE.get(session_id, {})
    
    if not itinerary:
        return redirect(url_for("index"))
        
    dest_clean = inputs.get("destination", "trip").lower().replace(" ", "_")
    filename = f"tripforge_{dest_clean}.md"
    
    # Create temp directory in workspace for downloads (fallback to system temp if read-only)
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch")
    try:
        os.makedirs(temp_dir, exist_ok=True)
        test_file = os.path.join(temp_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("")
        os.remove(test_file)
    except Exception:
        import tempfile
        temp_dir = tempfile.gettempdir()
        
    temp_path = os.path.join(temp_dir, filename)
    
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(itinerary)
        
    return send_file(temp_path, as_attachment=True, download_name=filename)

@app.route("/health")
def health():
    """Check target deployment status and agent settings."""
    is_mock = (os.getenv("TRIPFORGE_MODE", "live").lower() == "mock") or not os.getenv("GOOGLE_API_KEY")
    return jsonify({
        "status": "ok",
        "version": "0.1.0",
        "mode": "mock" if is_mock else "live",
        "agents": ["profile", "research", "itinerary", "disruption"]
    })

if __name__ == "__main__":
    is_mock = (os.getenv("TRIPFORGE_MODE", "live").lower() == "mock") or not os.getenv("GOOGLE_API_KEY")
    print("\n" + "="*60)
    print(f"[*] TripForge Server Starting Up in {'MOCK' if is_mock else 'LIVE'} Mode")
    print(f"[*] Local Access: http://127.0.5.100:5000 -> Map to http://127.0.0.1:5000")
    print(f"[*] Local Access URL: http://127.0.0.1:5000")
    print("="*60 + "\n")
    app.run(debug=True, use_reloader=False, port=5000)
