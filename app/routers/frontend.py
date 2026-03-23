"""
Frontend HTML routes served via Jinja2 templates.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import app.store as store

router = APIRouter(tags=["frontend"])

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=os.path.abspath(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Landing page."""
    return templates.TemplateResponse(request, "index.html")


@router.get("/ui/mappings", response_class=HTMLResponse)
async def ui_mappings(request: Request) -> HTMLResponse:
    """List available ConceptMaps."""
    mappings = store.list_all()
    return templates.TemplateResponse(
        request, "mappings.html", {"mappings": mappings}
    )


@router.get("/ui/mappings/new", response_class=HTMLResponse)
async def ui_new_mapping(request: Request) -> HTMLResponse:
    """Form to create / upload a ConceptMap."""
    return templates.TemplateResponse(request, "new_mapping.html")


@router.get("/ui/convert", response_class=HTMLResponse)
async def ui_convert(request: Request) -> HTMLResponse:
    """Conversion interface."""
    mappings = store.list_all()
    return templates.TemplateResponse(
        request, "convert.html", {"mappings": mappings}
    )
