"""
Conversion endpoints: FHIR ↔ HL7v2.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

import app.store as store
from app.models import (
    ConvertFHIRToV2Request,
    ConvertV2ToFHIRRequest,
    ConversionResult,
)
from app.services.mapping_service import fhir_to_v2, v2_to_fhir

router = APIRouter(prefix="/convert", tags=["conversion"])


def _load_map(concept_map_id: str):
    cm = store.get(concept_map_id)
    if cm is None:
        raise HTTPException(
            status_code=404,
            detail=f"ConceptMap '{concept_map_id}' not found",
        )
    return cm


@router.post("/fhir-to-v2", response_model=ConversionResult)
async def convert_fhir_to_v2(req: ConvertFHIRToV2Request) -> ConversionResult:
    """
    Convert a FHIR resource (JSON) to an HL7v2 message.

    A ConceptMap must be supplied to define the code-translation rules.
    """
    cm = _load_map(req.concept_map_id)
    return fhir_to_v2(req.fhir_resource, req.message_type, cm)


@router.post("/v2-to-fhir", response_model=ConversionResult)
async def convert_v2_to_fhir(req: ConvertV2ToFHIRRequest) -> ConversionResult:
    """
    Convert an HL7v2 message string to a FHIR resource.

    A ConceptMap must be supplied to define the code-translation rules.
    """
    cm = _load_map(req.concept_map_id)
    return v2_to_fhir(req.v2_message, req.target_resource_type, cm)
