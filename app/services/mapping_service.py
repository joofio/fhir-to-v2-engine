"""
Mapping service: bidirectional HL7v2 <-> FHIR conversion using ConceptMaps.

This service handles:
- Parsing HL7v2 messages using the `hl7` library
- Building/reading FHIR resources using `fhir.resources`
- Applying ConceptMap translations to code values
"""
from __future__ import annotations

import re
from typing import Any

import hl7

from app.models import ConceptMap, ConversionResult


# ---------------------------------------------------------------------------
# ConceptMap helpers
# ---------------------------------------------------------------------------

def apply_concept_map(
    code: str,
    system: str,
    concept_map: ConceptMap,
    reverse: bool = False,
) -> str:
    """
    Translate *code* from source → target (or target → source when *reverse*
    is True) using the first matching element in the ConceptMap groups.

    Returns the original code unchanged when no mapping is found.
    """
    for group in concept_map.groups:
        src_system = group.target if reverse else group.source
        # If the group specifies a system, only apply when it matches
        if src_system and src_system != system:
            continue
        for element in group.elements:
            src_code = element.get("code") if not reverse else _first_target_code(element)
            if src_code == code:
                if reverse:
                    return element.get("code", code)
                targets = element.get("target", [])
                if targets:
                    return targets[0].get("code", code)
    return code


def _first_target_code(element: dict[str, Any]) -> str | None:
    targets = element.get("target", [])
    if targets:
        return targets[0].get("code")
    return None


# ---------------------------------------------------------------------------
# FHIR → HL7v2
# ---------------------------------------------------------------------------

def fhir_to_v2(
    fhir_resource: dict[str, Any],
    message_type: str = "ADT_A01",
    concept_map: ConceptMap | None = None,
) -> ConversionResult:
    """
    Convert a FHIR resource (dict) to an HL7v2 message string.

    Currently supports Patient and Observation resources and produces the
    common segments (MSH, EVN, PID, OBX).  Unknown resource types fall back
    to a minimal MSH-only message.
    """
    resource_type = fhir_resource.get("resourceType", "Unknown")
    warnings: list[str] = []

    msh = _build_msh(message_type)

    if resource_type == "Patient":
        segments = _patient_to_v2(fhir_resource, concept_map, warnings)
    elif resource_type == "Observation":
        segments = _observation_to_v2(fhir_resource, concept_map, warnings)
    else:
        warnings.append(
            f"Resource type '{resource_type}' is not fully supported; "
            "only MSH segment generated."
        )
        segments = []

    lines = [msh] + segments
    v2_message = "\r".join(lines)

    return ConversionResult(
        source_format="FHIR",
        target_format="HL7v2",
        result=v2_message,
        applied_map_id=concept_map.id if concept_map else None,
        warnings=warnings,
    )


def _build_msh(message_type: str) -> str:
    event_map = {
        "ADT_A01": "ADT^A01",
        "ADT_A08": "ADT^A08",
        "ORU_R01": "ORU^R01",
    }
    msg_event = event_map.get(message_type, message_type.replace("_", "^"))
    return (
        f"MSH|^~\\&|FHIR2V2|SENDER|RECEIVER|DESTINATION|"
        f"20260101120000||{msg_event}|MSG00001|P|2.5"
    )


def _safe(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _patient_to_v2(
    patient: dict[str, Any],
    concept_map: ConceptMap | None,
    warnings: list[str],
) -> list[str]:
    segments: list[str] = ["EVN||20260101120000"]

    # PID segment
    patient_id = patient.get("id", "")
    name_list = patient.get("name", [{}])
    name = name_list[0] if name_list else {}
    family = _safe(name.get("family", ""))
    given = " ".join(name.get("given", []))
    dob = _safe(patient.get("birthDate", "")).replace("-", "")

    raw_gender = _safe(patient.get("gender", ""))
    gender = _map_gender_to_v2(raw_gender, concept_map, warnings)

    # Identifier
    identifiers = patient.get("identifier", [])
    mrn = ""
    for ident in identifiers:
        if ident.get("use") == "usual" or not mrn:
            mrn = _safe(ident.get("value", ""))

    # PID layout: 1=setId 2=extId 3=intId 4=altId 5=name 6=maidenName 7=dob 8=sex
    pid = (
        f"PID|1|{mrn}|{patient_id}||"
        f"{family}^{given}||{dob}|{gender}"
    )
    segments.append(pid)
    return segments


def _map_gender_to_v2(
    fhir_gender: str,
    concept_map: ConceptMap | None,
    warnings: list[str],
) -> str:
    default_map = {"male": "M", "female": "F", "other": "O", "unknown": "U"}
    if concept_map:
        mapped = apply_concept_map(
            fhir_gender,
            "http://hl7.org/fhir/administrative-gender",
            concept_map,
        )
        if mapped != fhir_gender:
            return mapped
        warnings.append(
            f"No ConceptMap entry for gender '{fhir_gender}'; using default mapping."
        )
    return default_map.get(fhir_gender.lower(), fhir_gender)


def _observation_to_v2(
    observation: dict[str, Any],
    concept_map: ConceptMap | None,
    warnings: list[str],
) -> list[str]:
    segments: list[str] = []

    code_cc = observation.get("code", {})
    code_codings = code_cc.get("coding", [{}])
    obs_code = ""
    obs_system = ""
    obs_display = ""
    if code_codings:
        obs_code = _safe(code_codings[0].get("code", ""))
        obs_system = _safe(code_codings[0].get("system", ""))
        obs_display = _safe(code_codings[0].get("display", ""))

    if concept_map:
        obs_code = apply_concept_map(obs_code, obs_system, concept_map)

    value = ""
    units = ""
    if "valueQuantity" in observation:
        vq = observation["valueQuantity"]
        value = _safe(vq.get("value", ""))
        units = _safe(vq.get("unit", ""))
    elif "valueString" in observation:
        value = _safe(observation["valueString"])
    elif "valueCodeableConcept" in observation:
        vcc = observation["valueCodeableConcept"]
        codings = vcc.get("coding", [{}])
        value = _safe(codings[0].get("code", "")) if codings else ""
        if concept_map and value:
            value = apply_concept_map(
                value,
                _safe(codings[0].get("system", "")) if codings else "",
                concept_map,
            )

    obx = (
        f"OBX|1|NM|{obs_code}^{obs_display}^{obs_system}||{value}|{units}"
    )
    segments.append(obx)
    return segments


# ---------------------------------------------------------------------------
# HL7v2 → FHIR
# ---------------------------------------------------------------------------

def v2_to_fhir(
    v2_message: str,
    target_resource_type: str = "Patient",
    concept_map: ConceptMap | None = None,
) -> ConversionResult:
    """
    Parse an HL7v2 message string and convert it to a FHIR resource dict.

    Supports Patient (from PID) and Observation (from OBX) conversion.
    """
    warnings: list[str] = []

    # Normalise line endings
    v2_message = v2_message.replace("\n", "\r").replace("\r\r", "\r")

    try:
        msg = hl7.parse(v2_message)
    except Exception as exc:
        warnings.append(f"HL7v2 parse warning: {exc}")
        msg = None

    if target_resource_type == "Patient":
        result = _v2_to_patient(msg, v2_message, concept_map, warnings)
    elif target_resource_type == "Observation":
        result = _v2_to_observation(msg, v2_message, concept_map, warnings)
    else:
        warnings.append(
            f"Target resource type '{target_resource_type}' is not fully supported; "
            "returning raw segment data."
        )
        result = _raw_segments(v2_message)

    return ConversionResult(
        source_format="HL7v2",
        target_format="FHIR",
        result=result,
        applied_map_id=concept_map.id if concept_map else None,
        warnings=warnings,
    )


def _get_field(msg: Any, segment_name: str, field_index: int, default: str = "") -> str:
    """Safely extract a field value from a parsed HL7v2 message."""
    try:
        segment = msg.segment(segment_name)
        value = str(segment[field_index])
        return value if value else default
    except Exception:
        return default


def _v2_to_patient(
    msg: Any,
    raw: str,
    concept_map: ConceptMap | None,
    warnings: list[str],
) -> dict[str, Any]:
    resource: dict[str, Any] = {"resourceType": "Patient"}

    if msg is None:
        warnings.append("Could not parse HL7v2 message; returning empty Patient.")
        return resource

    # PID-3 = patient identifier list, PID-5 = patient name, PID-7 = DOB, PID-8 = sex
    patient_id = _get_field(msg, "PID", 3)
    mrn = _get_field(msg, "PID", 2)
    name_raw = _get_field(msg, "PID", 5)
    dob_raw = _get_field(msg, "PID", 7)
    gender_raw = _get_field(msg, "PID", 8)

    if patient_id:
        resource["id"] = patient_id

    # Name: Family^Given
    if name_raw:
        parts = name_raw.split("^")
        family = parts[0] if parts else ""
        given = parts[1] if len(parts) > 1 else ""
        name_entry: dict[str, Any] = {"use": "official"}
        if family:
            name_entry["family"] = family
        if given:
            name_entry["given"] = [given]
        resource["name"] = [name_entry]

    if mrn:
        resource["identifier"] = [{"use": "usual", "value": mrn}]

    if dob_raw:
        # YYYYMMDD → YYYY-MM-DD
        dob = re.sub(r"(\d{4})(\d{2})(\d{2}).*", r"\1-\2-\3", dob_raw)
        resource["birthDate"] = dob

    if gender_raw:
        fhir_gender = _map_gender_to_fhir(gender_raw, concept_map, warnings)
        resource["gender"] = fhir_gender

    return resource


def _map_gender_to_fhir(
    v2_gender: str,
    concept_map: ConceptMap | None,
    warnings: list[str],
) -> str:
    default_map = {"M": "male", "F": "female", "O": "other", "U": "unknown"}
    if concept_map:
        mapped = apply_concept_map(
            v2_gender,
            "http://terminology.hl7.org/CodeSystem/v2-0001",
            concept_map,
            reverse=True,
        )
        if mapped != v2_gender:
            return mapped
        warnings.append(
            f"No ConceptMap entry for gender '{v2_gender}'; using default mapping."
        )
    return default_map.get(v2_gender.upper(), v2_gender.lower())


def _v2_to_observation(
    msg: Any,
    raw: str,
    concept_map: ConceptMap | None,
    warnings: list[str],
) -> dict[str, Any]:
    resource: dict[str, Any] = {"resourceType": "Observation", "status": "final"}

    if msg is None:
        warnings.append("Could not parse HL7v2 message; returning empty Observation.")
        return resource

    obs_code_raw = _get_field(msg, "OBX", 3)  # e.g. "8867-4^Heart rate^LN"
    value_raw = _get_field(msg, "OBX", 5)
    units_raw = _get_field(msg, "OBX", 6)
    value_type = _get_field(msg, "OBX", 2, "NM")

    if obs_code_raw:
        parts = obs_code_raw.split("^")
        code = parts[0]
        display = parts[1] if len(parts) > 1 else ""
        system = parts[2] if len(parts) > 2 else ""

        if concept_map:
            code = apply_concept_map(code, system, concept_map, reverse=True)

        resource["code"] = {
            "coding": [{"system": system, "code": code, "display": display}]
        }

    if value_raw:
        if value_type == "NM":
            try:
                resource["valueQuantity"] = {
                    "value": float(value_raw),
                    "unit": units_raw,
                }
            except ValueError:
                resource["valueString"] = value_raw
        else:
            resource["valueString"] = value_raw

    return resource


def _raw_segments(raw: str) -> dict[str, Any]:
    segments: dict[str, list[list[str]]] = {}
    for line in raw.split("\r"):
        line = line.strip()
        if not line:
            continue
        fields = line.split("|")
        name = fields[0]
        segments.setdefault(name, []).append(fields[1:])
    return {"raw_segments": segments}
