"""
FHIR ↔ HL7v2 Mapping Engine
=============================
FastAPI application entry point.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import conversion, frontend, mappings

app = FastAPI(
    title="FHIR ↔ HL7v2 Mapping Engine",
    description=(
        "Bidirectional conversion between HL7 FHIR and HL7v2 messages "
        "using FHIR ConceptMaps for concept translation."
    ),
    version="0.1.0",
)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=os.path.abspath(_STATIC_DIR)), name="static")

app.include_router(frontend.router)
app.include_router(mappings.router)
app.include_router(conversion.router)
