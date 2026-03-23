"""
Data models for the FHIR <-> HL7v2 mapping engine.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ConceptMapGroup(BaseModel):
    source: str | None = None
    target: str | None = None
    elements: list[dict[str, Any]] = Field(default_factory=list)


class ConceptMap(BaseModel):
    """Simplified representation of a FHIR ConceptMap resource."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    title: str | None = None
    description: str | None = None
    source_system: str
    target_system: str
    version: str = "1.0.0"
    status: str = "active"
    groups: list[ConceptMapGroup] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = {"extra": "allow"}


class ConceptMapCreate(BaseModel):
    """Payload for creating or updating a ConceptMap."""

    name: str
    title: str | None = None
    description: str | None = None
    source_system: str
    target_system: str
    version: str = "1.0.0"
    status: str = "active"
    groups: list[ConceptMapGroup] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class ConvertFHIRToV2Request(BaseModel):
    """Request body for FHIR → HL7v2 conversion."""

    fhir_resource: dict[str, Any]
    concept_map_id: str | None = None
    message_type: str = "ADT_A01"


class ConvertV2ToFHIRRequest(BaseModel):
    """Request body for HL7v2 → FHIR conversion."""

    v2_message: str
    concept_map_id: str | None = None
    target_resource_type: str | None = None


class ConversionResult(BaseModel):
    """Result of a conversion operation."""

    source_format: str
    target_format: str
    result: Any
    applied_map_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
