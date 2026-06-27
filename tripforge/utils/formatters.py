# File: tripforge/utils/formatters.py
# Purpose: Formatters for rendering itineraries to Markdown, Rich Terminal panels, and Pandoc PDF formats.
# Competition Concept: Output formatting & Rich terminal visualization

import json
from typing import Dict, Any, List, Union
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.box import ROUNDED

console = Console()

def format_itinerary_markdown(itinerary_data: Dict[str, Any]) -> str:
    """
    Formates structured itinerary data into beautiful, emoji-rich Markdown.
    """
    dest = itinerary_data.get("destination", "Destination")
    days = itinerary_data.get("days", 3)
    travelers = itinerary_data.get("travelers", 2)
    budget = itinerary_data.get("budget", 1000.0)
    curr = itinerary_data.get("currency", "USD")
    
    md = []
    md.append(f"# 🌍 TripForge Itinerary: {dest}")
    md.append(f"**Trip Details:** {days} Days | {travelers} Travelers | Budget: {curr} {budget:,.2f}\n")
    md.append("---")
    
    # Check if there is a 'what changed' section from replan
    if "what_changed" in itinerary_data:
        md.append("## ⚡ What Changed (Replanned)")
        md.append(itinerary_data["what_changed"])
        md.append("\n---")
        
    for day in itinerary_data.get("days_list", []):
        day_num = day.get("day_num", 1)
        theme = day.get("theme", "Exploration")
        md.append(f"## 📅 Day {day_num}: {theme}")
        
        # Schedule table/list
        md.append("| Time of Day | Activity | Duration | Cost | Description |")
        md.append("|---|---|---|---|---|")
        
        for slot in ["morning", "afternoon", "evening"]:
            act = day.get("activities", {}).get(slot, {})
            if act:
                name = act.get("name", "Free Time")
                # Highlight if replanned (using emoji from disruption agent)
                prefix = "⚡ " if act.get("is_replanned") else ""
                desc = act.get("description", "Enjoy exploring the city at your leisure.")
                dur = f"{act.get('duration_hours', 2.0)}h"
                cost = f"{curr} {act.get('cost_per_person', 0.0):.2f}"
                md.append(f"| {slot.title()} | {prefix}{name} | {dur} | {cost} | {desc} |")
                
        md.append("\n### 🍴 Daily Dining")
        meals = day.get("meals", {})
        md.append(f"- **Breakfast:** {meals.get('breakfast', 'Local cafe recommendation')}")
        md.append(f"- **Lunch:** {meals.get('lunch', 'Recommended local bistro')}")
        md.append(f"- **Dinner:** {meals.get('dinner', 'Recommended dinner spot')}")
        
        # Daily transport and tip
        if day.get("transport_note"):
            md.append(f"\n🚶 **Transit:** {day.get('transport_note')}")
            
        md.append(f"\n💡 **Insider Tip:** *{day.get('insider_tip', 'Wander off the beaten path.')}*")
        md.append(f"\n💵 **Daily Total Cost:** {curr} {day.get('daily_cost', 0.0):,.2f}")
        md.append("\n---")
        
    # Trip Summary
    md.append("## 📊 Trip Summary & Essentials")
    total_est = itinerary_data.get("total_cost", 0.0)
    md.append(f"- **Total Estimated Cost:** {curr} {total_est:,.2f}")
    
    pack = itinerary_data.get("packing_suggestions", [])
    if pack:
        md.append("- **Suggested Packing:**")
        for item in pack:
            md.append(f"  - {item}")
            
    emerg = itinerary_data.get("emergency_contacts", {})
    if emerg:
        md.append("- **Emergency Contacts:**")
        for k, v in emerg.items():
            md.append(f"  - {k.title()}: {v}")
            
    tips = itinerary_data.get("currency_tips", "")
    if tips:
        md.append(f"- **Currency & Logistics:** {tips}")
        
    return "\n".join(md)

def format_itinerary_terminal(itinerary_data: Dict[str, Any]) -> None:
    """
    Renders structured itinerary details nicely in the terminal using Rich.
    """
    dest = itinerary_data.get("destination", "Destination")
    days = itinerary_data.get("days", 3)
    travelers = itinerary_data.get("travelers", 2)
    budget = itinerary_data.get("budget", 1000.0)
    curr = itinerary_data.get("currency", "USD")
    
    header_text = Text.assemble(
        ("🌍 TripForge Travel Plan: ", "bold cyan"),
        (f"{dest} ", "bold green"),
        (f"({days} Days, {travelers} Travelers, Budget: {curr} {budget:,.2f})", "italic white")
    )
    console.print(Panel(header_text, border_style="cyan", box=ROUNDED))
    
    if "what_changed" in itinerary_data:
        console.print(Panel(
            Text(f"⚡ [REPLAN CHANGELOG]\n{itinerary_data['what_changed']}", style="yellow bold"),
            border_style="yellow",
            title="⚡ Plan Adjustments"
        ))
        
    for day in itinerary_data.get("days_list", []):
        day_num = day.get("day_num", 1)
        theme = day.get("theme", "Exploration")
        
        day_title = f"📅 Day {day_num}: {theme}"
        day_content = []
        
        # Schedule table
        table = Table(show_header=True, header_style="bold magenta", box=ROUNDED, expand=True)
        table.add_column("Time", width=12)
        table.add_column("Activity", style="green")
        table.add_column("Duration", width=10, justify="right")
        table.add_column("Cost/Person", width=12, justify="right")
        
        for slot in ["morning", "afternoon", "evening"]:
            act = day.get("activities", {}).get(slot, {})
            if act:
                name = act.get("name", "Free Time")
                prefix = "⚡ " if act.get("is_replanned") else ""
                dur = f"{act.get('duration_hours', 2.0)} hrs"
                cost = f"{curr} {act.get('cost_per_person', 0.0):.2f}"
                table.add_row(slot.title(), f"{prefix}{name}", dur, cost)
                
        # Print day info
        console.print(f"\n[bold green]{day_title}[/bold green]")
        console.print(table)
        
        # Meals
        meals = day.get("meals", {})
        console.print(f"🍴 [bold]Meals:[/bold] Breakfast: [italic]{meals.get('breakfast')}[/italic] | Lunch: [italic]{meals.get('lunch')}[/italic] | Dinner: [italic]{meals.get('dinner')}[/italic]")
        
        # Tip
        console.print(f"💡 [bold yellow]Insider Tip:[/bold yellow] [italic]{day.get('insider_tip')}[/italic]")
        console.print(f"💵 [bold cyan]Daily Spend:[/bold cyan] {curr} {day.get('daily_cost', 0.0):,.2f}")
        console.print("[dim]" + "━" * 60 + "[/dim]")
        
    # Cost Summary Table
    summary_table = Table(title="📊 Cost Summary & Logistics", box=ROUNDED, header_style="bold cyan")
    summary_table.add_column("Item", style="bold")
    summary_table.add_column("Details")
    
    summary_table.add_row("Total Est. Cost", f"{curr} {itinerary_data.get('total_cost', 0.0):,.2f}")
    summary_table.add_row("Packing Tips", ", ".join(itinerary_data.get("packing_suggestions", [])))
    summary_table.add_row("Emergencies", str(itinerary_data.get("emergency_contacts", {})))
    summary_table.add_row("Currency Tips", itinerary_data.get("currency_tips", ""))
    
    console.print(summary_table)

def format_daily_summary(day_data: Dict[str, Any]) -> str:
    """
    Builds a compact string summary of a single day.
    """
    day_num = day_data.get("day_num", 1)
    theme = day_data.get("theme", "")
    cost = day_data.get("daily_cost", 0.0)
    
    m_name = day_data.get("activities", {}).get("morning", {}).get("name", "Free Time")
    a_name = day_data.get("activities", {}).get("afternoon", {}).get("name", "Free Time")
    e_name = day_data.get("activities", {}).get("evening", {}).get("name", "Free Time")
    
    return f"Day {day_num} ({theme}): AM: {m_name} | PM: {a_name} | EV: {e_name} | Total: ${cost:.2f}"

def format_budget_breakdown(budget_data: Dict[str, Any]) -> Table:
    """
    Generates a Rich table containing category cost estimates, percentage breakdowns, and status.
    """
    total = budget_data.get("total_spent", 1.0)
    target = budget_data.get("target_budget", 1.0)
    curr = budget_data.get("currency", "USD")
    
    table = Table(title="💰 TripForge Budget Breakdown Analyzer", box=ROUNDED, header_style="bold green")
    table.add_column("Category", style="bold")
    table.add_column("Spent", justify="right")
    table.add_column("% of Total", justify="right")
    table.add_column("Target limit", justify="right")
    table.add_column("Status", justify="center")
    
    # Target allocations
    targets = {
        "Activities": target * 0.35,
        "Transport": target * 0.20,
        "Food": target * 0.25,
        "Emergency/Other": target * 0.20
    }
    
    breakdown = budget_data.get("categories", {
        "Activities": budget_data.get("activities_cost", 0.0),
        "Transport": budget_data.get("transport_cost", 0.0),
        "Food": budget_data.get("food_cost", 0.0),
        "Emergency/Other": budget_data.get("other_cost", 0.0)
    })
    
    for cat, val in breakdown.items():
        pct = (val / total * 100) if total > 0 else 0
        limit = targets.get(cat, 0.0)
        
        if val > limit:
            status = Text("OVER", style="bold red")
        else:
            status = Text("UNDER", style="bold green")
            
        table.add_row(
            cat, 
            f"{curr} {val:,.2f}", 
            f"{pct:.1f}%", 
            f"{curr} {limit:,.2f}", 
            status
        )
        
    # Totals Row
    status_overall = Text("OVER BUDGET", style="bold red") if total > target else Text("OK", style="bold green")
    table.add_row(
        "Total",
        f"{curr} {total:,.2f}",
        "100.0%",
        f"{curr} {target:,.2f}",
        status_overall,
        style="bold yellow"
    )
    return table

def export_to_pdf_ready_markdown(itinerary_data: Dict[str, Any]) -> str:
    """
    Renders the itinerary to a clean markdown dialect formatted specifically for Pandoc PDF conversion.
    Includes pagebreaks and title block metadata.
    """
    dest = itinerary_data.get("destination", "Destination")
    days = itinerary_data.get("days", 3)
    travelers = itinerary_data.get("travelers", 2)
    budget = itinerary_data.get("budget", 1000.0)
    curr = itinerary_data.get("currency", "USD")
    
    pdf_md = []
    # Pandoc title block
    pdf_md.append("---")
    pdf_md.append(f"title: \"TripForge Travel Plan: {dest}\"")
    pdf_md.append("author: \"TripForge Concierge Agent\"")
    pdf_md.append(f"date: \"{datetime.now().strftime('%B %d, %Y')}\"")
    pdf_md.append("geometry: margin=1in")
    pdf_md.append("header-includes:")
    pdf_md.append("  - \\usepackage{fancyhdr}")
    pdf_md.append("  - \\pagestyle{fancy}")
    pdf_md.append("---")
    pdf_md.append("\n\\newpage\n")
    
    pdf_md.append(f"# Trip Overview: {dest}")
    pdf_md.append(f"- **Total Duration:** {days} Days")
    pdf_md.append(f"- **Travelers:** {travelers}")
    pdf_md.append(f"- **Total Budget:** {curr} {budget:,.2f}")
    pdf_md.append(f"- **Estimated Total Spend:** {curr} {itinerary_data.get('total_cost', 0.0):,.2f}")
    
    if "what_changed" in itinerary_data:
        pdf_md.append("\n## ⚡ Replan Adjustments")
        pdf_md.append(itinerary_data["what_changed"])
        
    pdf_md.append("\n\\newpage\n")
    
    for day in itinerary_data.get("days_list", []):
        day_num = day.get("day_num", 1)
        theme = day.get("theme", "Exploration")
        pdf_md.append(f"# Day {day_num}: {theme}")
        
        pdf_md.append("\n## Activities Schedule\n")
        for slot in ["morning", "afternoon", "evening"]:
            act = day.get("activities", {}).get(slot, {})
            if act:
                prefix = "⚡ " if act.get("is_replanned") else ""
                pdf_md.append(f"### {slot.title()}: {prefix}{act.get('name')}")
                pdf_md.append(f"- **Duration:** {act.get('duration_hours')} hours")
                pdf_md.append(f"- **Cost:** {curr} {act.get('cost_per_person'):.2f}")
                pdf_md.append(f"- **Description:** {act.get('description')}")
                
        pdf_md.append("\n## Meals & Dining Suggestions")
        meals = day.get("meals", {})
        pdf_md.append(f"- **Breakfast:** {meals.get('breakfast')}")
        pdf_md.append(f"- **Lunch:** {meals.get('lunch')}")
        pdf_md.append(f"- **Dinner:** {meals.get('dinner')}")
        
        pdf_md.append(f"\n💡 **Insider Tip:** *{day.get('insider_tip')}*")
        pdf_md.append(f"\n💵 **Daily Cost:** {curr} {day.get('daily_cost', 0.0):,.2f}")
        
        # Add page breaks between days for a clean PDF look
        pdf_md.append("\n\\newpage\n")
        
    # Logistics section
    pdf_md.append("# Travel Logistics & Essentials")
    pack = itinerary_data.get("packing_suggestions", [])
    if pack:
        pdf_md.append("\n## Recommended Packing Checklist")
        for item in pack:
            pdf_md.append(f"- [ ] {item}")
            
    emerg = itinerary_data.get("emergency_contacts", {})
    if emerg:
        pdf_md.append("\n## Emergency & Contact Details")
        for k, v in emerg.items():
            pdf_md.append(f"- **{k.title()}:** {v}")
            
    tips = itinerary_data.get("currency_tips", "")
    if tips:
        pdf_md.append(f"\n## Currency & Cultural Notes\n{tips}")
        
    return "\n".join(pdf_md)
