from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import inflection
import yaml
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from loguru import logger

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.store import load
from home_connect_scheduler.web_deps import templates

router = APIRouter(prefix="/programs", tags=["programs"])

# Options to hide from the display (present on every program, just noise)
HIDDEN_OPTIONS = {"BSH.Common.Option.StartInRelative", "BSH.Common.Option.FinishInRelative"}

# Load static program specs (duration, energy, water) from YAML
_SPECS_PATH = Path(__file__).resolve().parent.parent / "program_specs.yaml"


def _load_specs() -> dict[str, dict[str, Any]]:
    if _SPECS_PATH.exists():
        with open(_SPECS_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def _humanize_key(key: str) -> str:
    """Extract last segment and convert CamelCase to human-readable."""
    segment = key.rsplit(".", 1)[-1]
    segment = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", segment)
    return inflection.titleize(segment)


def _get_spec(program_key: str) -> dict[str, Any] | None:
    """Look up static specs by matching the last segment of the program key."""
    last_segment = program_key.rsplit(".", 1)[-1]
    return _load_specs().get(last_segment)


def _format_option(opt: dict[str, Any]) -> dict[str, str]:
    """Format a single option for display."""
    opt_key = opt.get("key", "")
    opt_type = opt.get("type", "")
    constraints = opt.get("constraints", {})

    parts: list[str] = []

    if opt_type:
        parts.append(opt_type)

    if "default" in constraints:
        default = constraints["default"]
        if isinstance(default, bool):
            parts.append(f"default: {'Yes' if default else 'No'}")
        else:
            val = default
            unit = opt.get("unit", "")
            if unit == "seconds" and isinstance(val, int | float):
                minutes = int(val) // 60
                parts.append(f"default: {minutes} min")
            else:
                parts.append(f"default: {val}")

    if "min" in constraints and "max" in constraints:
        mn, mx = constraints["min"], constraints["max"]
        unit = opt.get("unit", "")
        if unit == "seconds":
            parts.append(f"range: {mn // 60}-{mx // 60} min")
        elif unit == "%":
            parts.append(f"range: {mn}-{mx}%")
        else:
            parts.append(f"range: {mn}-{mx}")

    if "allowedvalues" in constraints:
        values = [v.rsplit(".", 1)[-1] for v in constraints["allowedvalues"]]
        parts.append(", ".join(values))

    return {
        "key": opt_key,
        "name": _humanize_key(opt_key),
        "display": " | ".join(parts) if parts else "",
    }


def _extract_program_info(details: dict[str, Any]) -> dict[str, Any]:
    """Extract structured info from a program details response."""
    key = details.get("key", "")
    options = details.get("options", [])
    spec = _get_spec(key)

    visible_options = [
        _format_option(opt) for opt in options if opt.get("key", "") not in HIDDEN_OPTIONS
    ]

    # Use static specs for duration/energy/water, fall back to API data
    duration = spec.get("duration") if spec else None
    energy = spec.get("energy") if spec else None
    water = spec.get("water") if spec else None
    name = spec["name"] if spec else _humanize_key(key)

    # Also check API options as fallback
    for opt in options:
        opt_key = opt.get("key", "").lower()
        constraints = opt.get("constraints", {})
        value = constraints.get("default", opt.get("value"))

        if duration is None and any(
            k in opt_key for k in ("duration", "programtime", "finishinrelative")
        ):
            if "min" in constraints:
                duration = constraints["min"] // 60
            elif opt.get("unit") == "seconds" and isinstance(value, int | float):
                duration = int(value) // 60

        if energy is None and "energy" in opt_key and value is not None:
            energy = value

        if water is None and "water" in opt_key and value is not None:
            water = value

    return {
        "key": key,
        "name": name,
        "options": visible_options,
        "duration": duration,
        "energy": energy,
        "water": water,
    }


@router.get("", response_class=HTMLResponse)
async def list_programs(request: Request) -> HTMLResponse:
    data = load()
    if not data.tokens or not data.selected_appliance:
        return templates.TemplateResponse(
            request,
            "programs.html",
            {"connected": data.tokens is not None, "programs": [], "sort": "name"},
        )

    client = HomeConnectClient()
    try:
        program_list = await client.list_programs(data.selected_appliance)

        # Fetch details for each program concurrently
        tasks = [
            client.get_program_details(data.selected_appliance, p["key"]) for p in program_list
        ]
        details_list = await asyncio.gather(*tasks, return_exceptions=True)

        programs = []
        for i, details in enumerate(details_list):
            if isinstance(details, Exception):
                logger.debug("Program details unavailable: {}", details)
                programs.append(_extract_program_info({"key": program_list[i]["key"]}))
            else:
                programs.append(_extract_program_info(details))
    except Exception as exc:
        logger.error("Failed to fetch programs: {}", exc)
        programs = []
    finally:
        await client.close()

    # Sort
    sort_by = request.query_params.get("sort", "name")
    reverse = request.query_params.get("dir", "asc") == "desc"

    sort_keys = {
        "name": lambda p: p["name"].lower(),
        "duration": lambda p: p["duration"] if p["duration"] is not None else float("inf"),
        "energy": lambda p: p["energy"] if p["energy"] is not None else float("inf"),
        "water": lambda p: p["water"] if p["water"] is not None else float("inf"),
        "options": lambda p: len(p["options"]),
    }
    programs.sort(key=sort_keys.get(sort_by, sort_keys["name"]), reverse=reverse)

    return templates.TemplateResponse(
        request,
        "programs.html",
        {
            "connected": True,
            "programs": programs,
            "sort": sort_by,
            "sort_dir": "desc" if reverse else "asc",
        },
    )
