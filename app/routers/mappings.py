"""
ConceptMap CRUD endpoints.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

import app.store as store
from app.models import ConceptMap, ConceptMapCreate

router = APIRouter(prefix="/mappings", tags=["mappings"])


@router.get("", response_model=list[ConceptMap])
async def list_mappings() -> list[ConceptMap]:
    """Return all stored ConceptMaps."""
    return store.list_all()


@router.post("", response_model=ConceptMap, status_code=status.HTTP_201_CREATED)
async def create_mapping(payload: ConceptMapCreate) -> ConceptMap:
    """Create a new ConceptMap from a JSON body."""
    cm = ConceptMap(**payload.model_dump())
    return store.save(cm)


@router.get("/{mapping_id}", response_model=ConceptMap)
async def get_mapping(mapping_id: str) -> ConceptMap:
    """Retrieve a single ConceptMap by ID."""
    cm = store.get(mapping_id)
    if cm is None:
        raise HTTPException(status_code=404, detail="ConceptMap not found")
    return cm


@router.put("/{mapping_id}", response_model=ConceptMap)
async def update_mapping(mapping_id: str, payload: ConceptMapCreate) -> ConceptMap:
    """Replace an existing ConceptMap."""
    existing = store.get(mapping_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="ConceptMap not found")
    updated = ConceptMap(
        **payload.model_dump(),
        id=mapping_id,
        created_at=existing.created_at,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    return store.save(updated)


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(mapping_id: str) -> None:
    """Delete a ConceptMap by ID."""
    if not store.delete(mapping_id):
        raise HTTPException(status_code=404, detail="ConceptMap not found")


@router.post("/upload", response_model=ConceptMap, status_code=status.HTTP_201_CREATED)
async def upload_mapping(file: UploadFile = File(...)) -> ConceptMap:
    """
    Upload a FHIR ConceptMap JSON file and store it.

    The JSON must represent a FHIR ConceptMap resource (resourceType = ConceptMap).
    """
    if file.content_type not in ("application/json", "text/json", "application/fhir+json"):
        # Accept any content but warn on non-JSON
        pass

    content = await file.read()
    try:
        data: dict[str, Any] = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    if data.get("resourceType") == "ConceptMap":
        cm = _from_fhir_concept_map(data)
    else:
        # Treat the JSON directly as a ConceptMapCreate payload
        try:
            payload = ConceptMapCreate(**data)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot parse as ConceptMap: {exc}",
            ) from exc
        cm = ConceptMap(**payload.model_dump())

    return store.save(cm)


def _from_fhir_concept_map(data: dict[str, Any]) -> ConceptMap:
    """Convert a raw FHIR ConceptMap resource dict into our internal model."""
    groups_raw = data.get("group", [])
    from app.models import ConceptMapGroup

    groups = [
        ConceptMapGroup(
            source=g.get("source"),
            target=g.get("target"),
            elements=g.get("element", []),
        )
        for g in groups_raw
    ]

    return ConceptMap(
        name=data.get("name") or data.get("id") or "imported",
        title=data.get("title"),
        description=data.get("description"),
        source_system=data.get("sourceUri") or data.get("sourceCanonical") or "",
        target_system=data.get("targetUri") or data.get("targetCanonical") or "",
        version=data.get("version", "1.0.0"),
        status=data.get("status", "active"),
        groups=groups,
    )
