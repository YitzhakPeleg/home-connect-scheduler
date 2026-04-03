from __future__ import annotations

import asyncio
import re
from typing import Any

import inflection
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from loguru import logger

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.store import load
from home_connect_scheduler.web_deps import templates

router = APIRouter(prefix="/programs", tags=["programs"])


def _humanize_key(key: str) -> str:
    """Extract last segment and convert CamelCase to human-readable.

    Also inserts spaces before numbers: Eco50 -> Eco 50, Quick45 -> Quick 45.
    """
    segment = key.rsplit(".", 1)[-1]
    # Insert space between letters and digits: "Eco50" -> "Eco 50"
    segment = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", segment)
    return inflection.titleize(segment)


def _format_option_value(opt: dict[str, Any]) -> str:
    """Format an option's value/constraints for display."""
    unit = opt.get("unit", "")
    constraints = opt.get("constraints", {})

    if "allowedvalues" in constraints:
        values = [v.rsplit(".", 1)[-1] for v in constraints["allowedvalues"]]
        return ", ".join(values)

    if "min" in constraints and "max" in constraints:
        mn, mx = constraints["min"], constraints["max"]
        if unit == "seconds":
            return f"{mn // 60}-{mx // 60} min"
        if unit == "%":
            return f"{mn}-{mx}%"
        return f"{mn}-{mx} {unit}".strip()

    val = opt.get("value")
    if isinstance(val, bool):
        return "Yes / No"
    if unit == "seconds" and isinstance(val, int | float):
        return f"{int(val) // 60} min"
    if unit == "%":
        return f"{val}%"
    if val is not None:
        return str(val)
    return ""


def _extract_program_info(details: dict[str, Any]) -> dict[str, Any]:
    """Extract structured info from a program details response."""
    key = details.get("key", "")
    options = details.get("options", [])

    info: dict[str, Any] = {
        "key": key,
        "name": _humanize_key(key),
        "options": [],
        "duration_min": None,
        "duration_max": None,
        "energy": None,
        "water": None,
    }

    for opt in options:
        opt_key = opt.get("key", "")
        opt_name = _humanize_key(opt_key)
        opt_display = _format_option_value(opt)
        constraints = opt.get("constraints", {})

        info["options"].append(
            {
                "key": opt_key,
                "name": opt_name,
                "display": opt_display,
            }
        )

        # Extract well-known values for sorting
        lower_key = opt_key.lower()
        if "duration" in lower_key or "finishinrelative" in lower_key:
            if "max" in constraints:
                info["duration_max"] = constraints["max"]
            if "min" in constraints:
                info["duration_min"] = constraints["min"]
            elif opt.get("unit") == "seconds" and isinstance(opt.get("value"), int | float):
                info["duration_min"] = int(opt["value"])

        if "energyforecast" in lower_key:
            info["energy"] = opt.get("value")
        if "waterforecast" in lower_key:
            info["water"] = opt.get("value")

    return info


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
        for details in details_list:
            if isinstance(details, Exception):
                logger.warning("Failed to fetch program details: {}", details)
                continue
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
        "duration": lambda p: p["duration_min"] if p["duration_min"] is not None else float("inf"),
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
