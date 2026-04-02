from __future__ import annotations

import asyncio
import webbrowser
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.models import DayOfWeek, Schedule
from home_connect_scheduler.store import load, save

app = typer.Typer(name="hcs", help="HomeConnect Scheduler CLI")
schedule_app = typer.Typer(help="Manage schedules")
app.add_typer(schedule_app, name="schedule")
console = Console()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --- connect ---


@app.command()
def connect() -> None:
    """Authenticate with HomeConnect via OAuth."""
    client = HomeConnectClient()
    url = client.get_auth_url()
    console.print(f"Opening browser for authorization...\n{url}")
    webbrowser.open(url)
    try:
        code = client.wait_for_callback()
    except TimeoutError:
        console.print("[red]Timed out waiting for callback.[/red]")
        raise typer.Exit(1) from None
    _run(client.exchange_code(code))
    console.print("[green]Connected successfully![/green]")


# --- appliances ---


@app.command()
def appliances() -> None:
    """List available appliances."""
    client = HomeConnectClient()
    items = _run(client.list_appliances())
    table = Table(title="Appliances")
    table.add_column("haId")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Brand")
    for a in items:
        table.add_row(a["haId"], a["type"], a.get("name", ""), a.get("brand", ""))
    console.print(table)


@app.command(name="select")
def select_appliance(
    ha_id: Annotated[str, typer.Argument(help="The haId of the appliance to select")],
) -> None:
    """Select an appliance for scheduling."""
    data = load()
    data.selected_appliance = ha_id
    save(data)
    console.print(f"[green]Selected appliance: {ha_id}[/green]")


# --- programs ---


@app.command()
def programs() -> None:
    """List available programs for the selected appliance."""
    data = load()
    if not data.selected_appliance:
        console.print("[red]No appliance selected. Run 'hcs select <haId>' first.[/red]")
        raise typer.Exit(1)
    client = HomeConnectClient()
    items = _run(client.list_programs(data.selected_appliance))
    table = Table(title=f"Programs for {data.selected_appliance}")
    table.add_column("Key")
    for p in items:
        table.add_row(p["key"])
    console.print(table)


# --- schedule commands ---


@schedule_app.command(name="add")
def schedule_add(
    name: Annotated[str, typer.Option(help="Schedule name")],
    day: Annotated[DayOfWeek, typer.Option(help="Day of week")],
    time: Annotated[str, typer.Option(help="Time in HH:MM format")],
    program: Annotated[str, typer.Option(help="Program key")],
) -> None:
    """Add a new schedule."""
    data = load()
    sched = Schedule(name=name, day=day, time=time, program=program)
    data.schedules.append(sched)
    save(data)
    console.print(f"[green]Added schedule '{name}' (id={sched.id})[/green]")


@schedule_app.command(name="list")
def schedule_list() -> None:
    """List all schedules."""
    data = load()
    if not data.schedules:
        console.print("No schedules configured.")
        return
    table = Table(title="Schedules")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Day")
    table.add_column("Time")
    table.add_column("Program")
    table.add_column("Enabled")
    for s in data.schedules:
        table.add_row(s.id, s.name, s.day.value, s.time, s.program, str(s.enabled))
    console.print(table)


@schedule_app.command(name="remove")
def schedule_remove(
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID to remove")],
) -> None:
    """Remove a schedule."""
    data = load()
    before = len(data.schedules)
    data.schedules = [s for s in data.schedules if s.id != schedule_id]
    if len(data.schedules) == before:
        console.print(f"[red]Schedule '{schedule_id}' not found.[/red]")
        raise typer.Exit(1)
    save(data)
    console.print(f"[green]Removed schedule {schedule_id}[/green]")


@schedule_app.command(name="toggle")
def schedule_toggle(
    schedule_id: Annotated[str, typer.Argument(help="Schedule ID to toggle")],
) -> None:
    """Toggle a schedule on/off."""
    data = load()
    for s in data.schedules:
        if s.id == schedule_id:
            s.enabled = not s.enabled
            save(data)
            state = "enabled" if s.enabled else "disabled"
            console.print(f"[green]Schedule {schedule_id} is now {state}[/green]")
            return
    console.print(f"[red]Schedule '{schedule_id}' not found.[/red]")
    raise typer.Exit(1)


# --- status ---


@app.command()
def status() -> None:
    """Show scheduler status: upcoming runs and recent results."""
    data = load()
    if not data.schedules:
        console.print("No schedules configured.")
        return

    table = Table(title="Upcoming Schedules")
    table.add_column("Name")
    table.add_column("Day")
    table.add_column("Time")
    table.add_column("Program")
    table.add_column("Enabled")
    for s in data.schedules:
        if s.enabled:
            table.add_row(s.name, s.day.value, s.time, s.program, str(s.enabled))
    console.print(table)

    if data.run_log:
        log_table = Table(title="Recent Runs (last 10)")
        log_table.add_column("Time")
        log_table.add_column("Schedule")
        log_table.add_column("Success")
        log_table.add_column("Message")
        for r in data.run_log[-10:]:
            log_table.add_row(
                r.timestamp.isoformat(),
                r.schedule_name,
                "[green]yes[/green]" if r.success else "[red]no[/red]",
                r.message,
            )
        console.print(log_table)


# --- start (manual trigger) ---


@app.command(name="start")
def start_program(
    program: Annotated[str, typer.Argument(help="Program key to start")],
) -> None:
    """Manually start a program on the selected appliance."""
    data = load()
    if not data.selected_appliance:
        console.print("[red]No appliance selected. Run 'hcs select <haId>' first.[/red]")
        raise typer.Exit(1)
    client = HomeConnectClient()
    _run(client.start_program(data.selected_appliance, program))
    console.print(f"[green]Started {program}[/green]")


# --- run (daemon) ---


@app.command()
def run() -> None:
    """Start the scheduler daemon."""
    from home_connect_scheduler.scheduler import start_scheduler

    logger.info("Starting scheduler daemon")
    start_scheduler()
