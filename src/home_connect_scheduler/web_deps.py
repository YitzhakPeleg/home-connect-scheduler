from __future__ import annotations

import re
from pathlib import Path

import inflection
from fastapi.templating import Jinja2Templates

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


def _humanize(text: str) -> str:
    """CamelCase to human-readable, with number separation: Eco50 -> Eco 50."""
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    return inflection.titleize(text)


templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.filters["humanize"] = _humanize
templates.env.filters["rsplit"] = lambda s, sep, maxsplit=1: s.rsplit(sep, maxsplit)
