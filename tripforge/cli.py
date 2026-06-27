# File: tripforge/cli.py
# Purpose: Entry point click CLI for TripForge containing plan, replan, profile, and demo commands.
# Competition Concept: Agent Skills (CLI) & terminal UX

import os
import sys

# Configure terminal streams to support UTF-8 characters on Windows legacy shells
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import asyncio
import click
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.box import ROUNDED
from dotenv import load_dotenv

# Load env variables at startup
load_dotenv()

# Custom console with colors
console = Console()

# ASCII Header Art
ASCII_HEADER = """
████████╗██████╗ ██╗██████╗ ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
   ██╔══╝██╔══██╗██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
   ██║   ██████╔╝██║██████╔╝█████╗  ██║   ██║██████╔╝██║  ███╗█████╗  
   ██║   ██╔══██╗██║██╔═══╝ ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  
   ██║   ██║  ██║██║██║     ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝     ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
   AI-Powered Travel Planning Agent | Kaggle Capstone 2025
"""

def print_header():
    """Prints the beautiful ASCII art header in bold cyan."""
    console.print(ASCII_HEADER, style="bold cyan")

# Define the root click group
@click.group()
def tripforge():
    """TripForge: AI-powered hyper-personalized multi-agent travel planner."""
    pass

@tripforge.command()
@click.option("--destination", "-d", required=True, help="Destination city (Paris, Tokyo, Barcelona, New York, Bali)")
@click.option("--days", type=int, default=7, show_default=True, help="Number of travel days (1-30)")
@click.option("--travelers", type=int, default=2, show_default=True, help="Number of travelers")
@click.option("--budget", type=float, required=True, help="Total travel budget")
@click.option("--currency", default="USD", show_default=True, help="Currency code")
@click.option("--accessibility", help="Accessibility constraint (wheelchair, visual, hearing)")
@click.option("--dietary", help="Dietary restrictions (gluten-free, vegan, halal, etc.)")
@click.option("--interests", help="Comma-separated interests (e.g. art,food,history)")
@click.option("--start-date", help="Trip start date (YYYY-MM-DD)")
@click.option("--profile", type=click.Path(exists=True), help="Path to saved encrypted profile JSON")
@click.option("--output", "-o", default="itinerary.md", show_default=True, help="Output markdown file path")
@click.option("--verbose", "-v", is_flag=True, help="Streams agent reasoning to the terminal")
def plan(
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    currency: str,
    accessibility: Optional[str],
    dietary: Optional[str],
    interests: Optional[str],
    start_date: Optional[str],
    profile: Optional[str],
    output: str,
    verbose: bool
):
    """Generates a complete personalized day-by-day itinerary."""
    print_header()
    
    # 1. Load profile if provided
    loaded_accessibility = accessibility
    loaded_dietary = dietary
    loaded_travelers = travelers
    loaded_interests_list = [i.strip() for i in interests.split(",")] if interests else None
    
    if profile:
        console.print(f"[dim]Loading profile parameters from: {profile}...[/dim]")
        from tripforge.utils.security import decrypt_profile_content
        try:
            with open(profile, "rb") as f:
                enc_data = f.read()
            prof_dict = decrypt_profile_content(enc_data)
            loaded_accessibility = prof_dict.get("accessibility_needs", loaded_accessibility)
            loaded_dietary = prof_dict.get("dietary_restrictions", loaded_dietary)
            loaded_travelers = prof_dict.get("travelers", loaded_travelers)
            loaded_interests_list = prof_dict.get("interests", loaded_interests_list)
            console.print("[green]✔ Profile loaded successfully.[/green]")
        except Exception as e:
            console.print(f"[bold red]Error decrypting profile: {e}. Utilizing CLI arguments instead.[/bold red]")
            
    # Sanitizations
    from tripforge.utils.security import sanitize_destination, sanitize_budget
    try:
        sanitized_dest = sanitize_destination(destination)
        sanitized_budget = sanitize_budget(budget)
    except ValueError as val_err:
        console.print(f"[bold red]Validation Error: {val_err}[/bold red]")
        sys.exit(1)
        
    # Execute workflow
    from tripforge.orchestrator import run_tripforge
    try:
        loop = asyncio.get_event_loop()
        itinerary_md = loop.run_until_complete(
            run_tripforge(
                destination=sanitized_dest,
                days=days,
                travelers=loaded_travelers,
                budget=sanitized_budget,
                currency=currency,
                accessibility=loaded_accessibility,
                dietary=loaded_dietary,
                interests=loaded_interests_list,
                start_date=start_date,
                verbose=verbose
            )
        )
        
        # Save output
        with open(output, "w", encoding="utf-8") as f:
            f.write(itinerary_md)
            
        console.print(Panel(
            f"[bold green]Success![/bold green] Your day-by-day plan is ready.\nSaved to: [bold underline cyan]{output}[/bold underline cyan]",
            title="✨ Plan Ready",
            border_style="green",
            box=ROUNDED
        ))
        
    except Exception as err:
        console.print(f"[bold red]Execution Failed: {err}[/bold red]")
        sys.exit(1)

@tripforge.command()
@click.option("--itinerary", "-i", required=True, type=click.Path(exists=True), help="Path to existing markdown itinerary")
@click.option("--disruption", "-d", required=True, help="Disruption description (e.g. flight cancellation, strike)")
@click.option("--output", "-o", default="replanned.md", show_default=True, help="Output path for updated plan")
@click.option("--verbose", "-v", is_flag=True, help="Print detailed replanning steps")
def replan(itinerary: str, disruption: str, output: str, verbose: bool):
    """Replans an existing itinerary in response to disruptions."""
    print_header()
    
    # Read existing itinerary
    with open(itinerary, "r", encoding="utf-8") as f:
        existing_md = f.read()
        
    # Standard dummy traveler profile for standalone replan
    profile_dummy = {
        "destination": "Paris",
        "days": 3,
        "travelers": 2,
        "budget": 2000.0,
        "currency": "USD",
        "accessibility_needs": None,
        "dietary_restrictions": None,
        "travel_style": "mid-range",
        "interests": ["culture", "food"]
    }
    
    from tripforge.orchestrator import run_replan
    try:
        loop = asyncio.get_event_loop()
        updated_md = loop.run_until_complete(
            run_replan(
                existing_itinerary=existing_md,
                disruption=disruption,
                profile=profile_dummy,
                verbose=verbose
            )
        )
        
        with open(output, "w", encoding="utf-8") as f:
            f.write(updated_md)
            
        console.print(Panel(
            f"[bold green]Success![/bold green] Itinerary has been successfully replanned to resolve conflict.\nSaved to: [bold underline cyan]{output}[/bold underline cyan]",
            title="⚡ Replan Done",
            border_style="yellow",
            box=ROUNDED
        ))
    except Exception as err:
        console.print(f"[bold red]Replanning Failed: {err}[/bold red]")
        sys.exit(1)

@tripforge.group(name="profile")
def profile_group():
    """Manage encrypted traveler profiles."""
    pass

@profile_group.command(name="create")
@click.option("--name", required=True, help="Name of the traveler/profile")
@click.option("--travelers", type=int, default=2, show_default=True, help="Number of travelers")
@click.option("--accessibility", help="Accessibility requirements")
@click.option("--dietary", help="Dietary restrictions")
@click.option("--interests", help="Comma-separated interests")
@click.option("--save", "-s", required=True, help="File path to save the encrypted profile (e.g. profiles/family.json)")
def profile_create(name: str, travelers: int, accessibility: Optional[str], dietary: Optional[str], interests: Optional[str], save: str):
    """Creates a new traveler profile and saves it encrypted."""
    print_header()
    
    interests_list = [i.strip() for i in interests.split(",")] if interests else []
    
    profile_data = {
        "name": name,
        "travelers": travelers,
        "accessibility_needs": accessibility,
        "dietary_restrictions": dietary,
        "interests": interests_list
    }
    
    from tripforge.utils.security import encrypt_profile
    try:
        console.print(f"[dim]Validating and encrypting profile '{name}'...[/dim]")
        # Save directory check
        dir_name = os.path.dirname(save)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            
        enc_bytes = encrypt_profile(profile_data)
        with open(save, "wb") as f:
            f.write(enc_bytes)
            
        console.print(f"[green]✔ Profile encrypted and saved to: {save}[/green]")
    except Exception as e:
        console.print(f"[bold red]Failed to create profile: {e}[/bold red]")
        sys.exit(1)

@profile_group.command(name="list")
def profile_list():
    """Lists all saved profiles in the profiles/ directory."""
    print_header()
    
    profiles_dir = "profiles"
    if not os.path.exists(profiles_dir):
        console.print(f"[warning]Warning: Directory '{profiles_dir}' does not exist.[/warning]")
        return
        
    files = [f for f in os.listdir(profiles_dir) if f.endswith(".json")]
    if not files:
        console.print("[info]No saved profile files found under profiles/ directory.[/info]")
        return
        
    table = Table(title="🔑 Saved Traveler Profiles (Encrypted on Disk)", box=ROUNDED, header_style="bold cyan")
    table.add_column("Filename", style="green")
    table.add_column("Traveler Name", style="bold")
    table.add_column("Travelers Count", justify="center")
    table.add_column("Accessibility Constraints", style="yellow")
    table.add_column("Dietary Needs", style="magenta")
    table.add_column("Interests")
    
    from tripforge.utils.security import decrypt_profile_content
    for file in files:
        path = os.path.join(profiles_dir, file)
        try:
            with open(path, "rb") as f:
                enc_data = f.read()
            data = decrypt_profile_content(enc_data)
            table.add_row(
                file,
                data.get("name", "N/A"),
                str(data.get("travelers", 2)),
                str(data.get("accessibility_needs") or "None"),
                str(data.get("dietary_restrictions") or "None"),
                ", ".join(data.get("interests", []))
            )
        except Exception:
            table.add_row(
                file,
                "[red]Decryption Error[/red]",
                "N/A",
                "N/A",
                "N/A",
                "[dim]Different Machine Key[/dim]"
            )
            
    console.print(table)

@tripforge.command()
@click.option("--output", "-o", default="paris_trip.md", show_default=True, help="Output markdown path")
@click.option("--verbose", "-v", is_flag=True, help="Print agent details")
def demo(output: str, verbose: bool):
    """Runs a simulated live scenario offline without requiring API keys."""
    # Force Mock Mode
    os.environ["TRIPFORGE_MODE"] = "mock"
    
    print_header()
    console.print("[bold yellow]🚀 Running TripForge Demonstration Scenario[/bold yellow]")
    console.print("[bold yellow]------------------------------------------------[/bold yellow]")
    
    # Run mock planning workflow
    from tripforge.orchestrator import run_tripforge
    loop = asyncio.get_event_loop()
    try:
        itinerary_md = loop.run_until_complete(
            run_tripforge(
                destination="Paris",
                days=3,
                travelers=2,
                budget=2000.0,
                currency="USD",
                accessibility=None,
                dietary=None,
                interests=["culture", "food", "history"],
                start_date="2025-08-15",
                verbose=verbose
            )
        )
        
        # Save output
        with open(output, "w", encoding="utf-8") as f:
            f.write(itinerary_md)
            
        console.print(Panel(
            f"[bold green]Success![/bold green] Demo scenario completed offline in 10s.\nSaved to: [bold underline cyan]{output}[/bold underline cyan]\n\n"
            f"To test disruption replanning, execute:\n"
            f"[bold cyan]tripforge replan --itinerary {output} --disruption \"Louvre closed due to strike\"[/bold cyan]",
            title="✨ Demo Finished",
            border_style="green",
            box=ROUNDED
        ))
        
    except Exception as e:
        console.print(f"[bold red]Demo Scenario Failed: {e}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    tripforge()
