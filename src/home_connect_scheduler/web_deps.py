from __future__ import annotations

from pathlib import Path

import inflection
from fastapi.templating import Jinja2Templates

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.filters["humanize"] = inflection.titleize
templates.env.filters["rsplit"] = lambda s, sep, maxsplit=1: s.rsplit(sep, maxsplit)
