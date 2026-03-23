"""
Tests for the FHIR ↔ HL7v2 mapping engine.

Covers:
- ConceptMap CRUD API endpoints
- FHIR → HL7v2 conversion
- HL7v2 → FHIR conversion
- Concept mapping (code translation) applied during conversion
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.store as store
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_store():
    """Reset the in-memory store before each test."""
    store.clear()
    yield
    store.clear()


# ---------------------------------------------------------------------------
# ConceptMap CRUD
# ---------------------------------------------------------------------------

GENDER_MAP_PAYLOAD = {
    "name": "gender-map",
    "title": "Gender Code Mapping",
    "source_system": "http://hl7.org/fhir/administrative-gender",
    "target_system": "http://terminology.hl7.org/CodeSystem/v2-0001",
    "groups": [
        {
            "source": "http://hl7.org/fhir/administrative-gender",
            "target": "http://terminology.hl7.org/CodeSystem/v2-0001",
            "elements": [
                {"code": "male",   "target": [{"code": "M", "equivalence": "equivalent"}]},
                {"code": "female", "target": [{"code": "F", "equivalence": "equivalent"}]},
                {"code": "other",  "target": [{"code": "O", "equivalence": "equivalent"}]},
                {"code": "unknown","target": [{"code": "U", "equivalence": "equivalent"}]},
            ],
        }
    ],
}


def test_create_and_list_mapping():
    resp = client.post("/mappings", json=GENDER_MAP_PAYLOAD)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "gender-map"
    assert "id" in created

    resp = client.get("/mappings")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == created["id"]


def test_get_mapping():
    created = client.post("/mappings", json=GENDER_MAP_PAYLOAD).json()
    resp = client.get(f"/mappings/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "gender-map"


def test_get_mapping_not_found():
    resp = client.get("/mappings/nonexistent")
    assert resp.status_code == 404


def test_update_mapping():
    created = client.post("/mappings", json=GENDER_MAP_PAYLOAD).json()
    updated_payload = {**GENDER_MAP_PAYLOAD, "title": "Updated Title"}
    resp = client.put(f"/mappings/{created['id']}", json=updated_payload)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


def test_delete_mapping():
    created = client.post("/mappings", json=GENDER_MAP_PAYLOAD).json()
    resp = client.delete(f"/mappings/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/mappings/{created['id']}").status_code == 404


def test_upload_mapping_json():
    import io, json

    payload = {
        "resourceType": "ConceptMap",
        "name": "uploaded-map",
        "status": "active",
        "sourceUri": "http://example.org/src",
        "targetUri": "http://example.org/tgt",
        "group": [
            {
                "source": "http://example.org/src",
                "target": "http://example.org/tgt",
                "element": [
                    {"code": "A", "target": [{"code": "1", "equivalence": "equivalent"}]}
                ],
            }
        ],
    }
    file_bytes = json.dumps(payload).encode()
    resp = client.post(
        "/mappings/upload",
        files={"file": ("map.json", io.BytesIO(file_bytes), "application/json")},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "uploaded-map"


# ---------------------------------------------------------------------------
# FHIR → HL7v2
# ---------------------------------------------------------------------------

PATIENT_FHIR = {
    "resourceType": "Patient",
    "id": "pt-001",
    "identifier": [{"use": "usual", "value": "MRN-001"}],
    "name": [{"family": "Smith", "given": ["John"]}],
    "gender": "male",
    "birthDate": "1980-06-15",
}


def test_fhir_patient_to_v2_no_map():
    resp = client.post(
        "/convert/fhir-to-v2",
        json={"fhir_resource": PATIENT_FHIR},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["source_format"] == "FHIR"
    assert result["target_format"] == "HL7v2"
    v2 = result["result"]
    assert "MSH" in v2
    assert "PID" in v2
    assert "Smith" in v2
    assert "John" in v2


def test_fhir_patient_to_v2_with_map():
    cm = client.post("/mappings", json=GENDER_MAP_PAYLOAD).json()
    resp = client.post(
        "/convert/fhir-to-v2",
        json={
            "fhir_resource": PATIENT_FHIR,
            "concept_map_id": cm["id"],
            "message_type": "ADT_A01",
        },
    )
    assert resp.status_code == 200
    result = resp.json()
    # Gender 'male' should have been mapped to 'M'
    assert "|M" in result["result"] or "M" in result["result"]


def test_fhir_observation_to_v2():
    obs = {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "8867-4",
                "display": "Heart rate",
            }]
        },
        "valueQuantity": {"value": 72, "unit": "bpm"},
    }
    resp = client.post(
        "/convert/fhir-to-v2",
        json={"fhir_resource": obs, "message_type": "ORU_R01"},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert "OBX" in result
    assert "8867-4" in result


def test_fhir_to_v2_unknown_resource():
    unknown = {"resourceType": "Medication", "id": "med-001"}
    resp = client.post("/convert/fhir-to-v2", json={"fhir_resource": unknown})
    assert resp.status_code == 200
    result = resp.json()
    assert "MSH" in result["result"]
    assert len(result["warnings"]) > 0


def test_fhir_to_v2_unknown_map_id():
    resp = client.post(
        "/convert/fhir-to-v2",
        json={"fhir_resource": PATIENT_FHIR, "concept_map_id": "no-such-id"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# HL7v2 → FHIR
# ---------------------------------------------------------------------------

V2_PATIENT_MSG = (
    "MSH|^~\\&|SEND|FAC|REC|FAC|20260101120000||ADT^A01|MSG001|P|2.5\r"
    "EVN||20260101120000\r"
    "PID|1|MRN-001|pt-001||Smith^John||19800615|M"
)


def test_v2_patient_to_fhir_no_map():
    resp = client.post(
        "/convert/v2-to-fhir",
        json={"v2_message": V2_PATIENT_MSG, "target_resource_type": "Patient"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["source_format"] == "HL7v2"
    assert result["target_format"] == "FHIR"
    fhir = result["result"]
    assert fhir["resourceType"] == "Patient"
    assert fhir.get("id") == "pt-001"
    assert fhir.get("birthDate") == "1980-06-15"


def test_v2_patient_to_fhir_gender_mapped():
    cm = client.post("/mappings", json=GENDER_MAP_PAYLOAD).json()
    resp = client.post(
        "/convert/v2-to-fhir",
        json={
            "v2_message": V2_PATIENT_MSG,
            "target_resource_type": "Patient",
            "concept_map_id": cm["id"],
        },
    )
    assert resp.status_code == 200
    fhir = resp.json()["result"]
    assert fhir.get("gender") == "male"


def test_v2_observation_to_fhir():
    v2_obs = (
        "MSH|^~\\&|SEND|FAC|REC|FAC|20260101120000||ORU^R01|MSG002|P|2.5\r"
        "OBX|1|NM|8867-4^Heart rate^LN||72|bpm"
    )
    resp = client.post(
        "/convert/v2-to-fhir",
        json={"v2_message": v2_obs, "target_resource_type": "Observation"},
    )
    assert resp.status_code == 200
    fhir = resp.json()["result"]
    assert fhir["resourceType"] == "Observation"
    assert fhir["code"]["coding"][0]["code"] == "8867-4"
    assert fhir["valueQuantity"]["value"] == 72.0


def test_v2_to_fhir_unknown_resource_type():
    resp = client.post(
        "/convert/v2-to-fhir",
        json={"v2_message": V2_PATIENT_MSG, "target_resource_type": "Encounter"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert len(result["warnings"]) > 0


def test_v2_to_fhir_unknown_map_id():
    resp = client.post(
        "/convert/v2-to-fhir",
        json={"v2_message": V2_PATIENT_MSG, "concept_map_id": "no-such-id"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auto-detection: HL7v2 → FHIR (no target_resource_type provided)
# ---------------------------------------------------------------------------

def test_v2_auto_detect_patient_from_adt():
    """ADT message with PID → auto-detected as Patient."""
    resp = client.post(
        "/convert/v2-to-fhir",
        json={"v2_message": V2_PATIENT_MSG},  # no target_resource_type
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["source_format"] == "HL7v2"
    assert result["target_format"] == "FHIR"
    fhir = result["result"]
    assert fhir["resourceType"] == "Patient"
    assert fhir.get("id") == "pt-001"


def test_v2_auto_detect_bundle_from_oru():
    """ORU message with both PID and OBX → auto-detected as Bundle."""
    oru_msg = (
        "MSH|^~\\&|SEND|FAC|REC|FAC|20260101120000||ORU^R01|MSG003|P|2.5\r"
        "PID|1|MRN-002|pt-002||Doe^Jane||19900101|F\r"
        "OBX|1|NM|8867-4^Heart rate^LN||60|bpm"
    )
    resp = client.post(
        "/convert/v2-to-fhir",
        json={"v2_message": oru_msg},  # no target_resource_type
    )
    assert resp.status_code == 200
    result = resp.json()
    fhir = result["result"]
    assert fhir["resourceType"] == "Bundle"
    resource_types = [e["resource"]["resourceType"] for e in fhir["entry"]]
    assert "Patient" in resource_types
    assert "Observation" in resource_types


def test_v2_auto_detect_explicit_auto_string():
    """Passing target_resource_type='auto' is equivalent to omitting it."""
    resp = client.post(
        "/convert/v2-to-fhir",
        json={"v2_message": V2_PATIENT_MSG, "target_resource_type": "auto"},
    )
    assert resp.status_code == 200
    fhir = resp.json()["result"]
    assert fhir["resourceType"] == "Patient"


# ---------------------------------------------------------------------------
# Generic FHIR → HL7v2 (unsupported resource type)
# ---------------------------------------------------------------------------

def test_fhir_generic_resource_produces_nte_segments():
    """Unknown FHIR resource types are encoded as NTE segments (not dropped)."""
    medication = {
        "resourceType": "Medication",
        "id": "med-001",
        "code": {"text": "Aspirin 100 mg"},
        "status": "active",
    }
    resp = client.post(
        "/convert/fhir-to-v2",
        json={"fhir_resource": medication},
    )
    assert resp.status_code == 200
    result = resp.json()
    v2 = result["result"]
    assert "MSH" in v2
    assert "NTE" in v2
    assert "Medication" in v2
    assert len(result["warnings"]) > 0


# ---------------------------------------------------------------------------
# Frontend pages (smoke tests)
# ---------------------------------------------------------------------------

def test_index_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "FHIR" in resp.text


def test_mappings_page():
    resp = client.get("/ui/mappings")
    assert resp.status_code == 200


def test_new_mapping_page():
    resp = client.get("/ui/mappings/new")
    assert resp.status_code == 200


def test_convert_page():
    resp = client.get("/ui/convert")
    assert resp.status_code == 200
