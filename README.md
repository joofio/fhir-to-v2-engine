# FHIR ↔ HL7v2 Mapping Engine

A bidirectional conversion engine between **HL7 FHIR** resources and **HL7v2** messages, using **FHIR ConceptMaps** for concept translation.

Built with **Python** / **FastAPI**, it exposes a REST API and a browser-based frontend.

---

## Features

| Capability | Details |
|---|---|
| **FHIR → HL7v2** | Convert FHIR Patient / Observation resources to HL7v2 segments (MSH, PID, OBX, …) |
| **HL7v2 → FHIR** | Parse HL7v2 messages and produce FHIR Patient / Observation resources |
| **ConceptMaps** | Upload, create, browse, and apply FHIR ConceptMaps for code translation |
| **REST API** | Full JSON API with interactive Swagger UI (`/docs`) and ReDoc (`/redoc`) |
| **Browser UI** | Mapping list, create/upload form, and a live conversion interface |

---

## Quick Start

### Prerequisites

* Python ≥ 3.11

### Install

```bash
git clone https://github.com/joofio/fhir-to-v2-engine.git
cd fhir-to-v2-engine
pip install -r requirements.txt
```

### Run

```bash
uvicorn app.main:app --reload
```

Open <http://localhost:8000> in your browser.

---

## API Endpoints

### ConceptMaps

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/mappings` | List all ConceptMaps |
| `POST` | `/mappings` | Create a ConceptMap (JSON body) |
| `GET`  | `/mappings/{id}` | Get a ConceptMap by ID |
| `PUT`  | `/mappings/{id}` | Replace a ConceptMap |
| `DELETE` | `/mappings/{id}` | Delete a ConceptMap |
| `POST` | `/mappings/upload` | Upload a FHIR ConceptMap JSON file |

### Conversion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/convert/fhir-to-v2` | Convert a FHIR resource → HL7v2 message |
| `POST` | `/convert/v2-to-fhir` | Convert an HL7v2 message → FHIR resource |

### UI Pages

| Path | Description |
|------|-------------|
| `/` | Landing page |
| `/ui/mappings` | Browse ConceptMaps |
| `/ui/mappings/new` | Create / upload a ConceptMap |
| `/ui/convert` | Interactive conversion tool |
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |

---

## Example: Create a ConceptMap

```bash
curl -X POST http://localhost:8000/mappings \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gender-map",
    "source_system": "http://hl7.org/fhir/administrative-gender",
    "target_system": "http://terminology.hl7.org/CodeSystem/v2-0001",
    "groups": [{
      "source": "http://hl7.org/fhir/administrative-gender",
      "target": "http://terminology.hl7.org/CodeSystem/v2-0001",
      "elements": [
        { "code": "male",    "target": [{ "code": "M", "equivalence": "equivalent" }] },
        { "code": "female",  "target": [{ "code": "F", "equivalence": "equivalent" }] },
        { "code": "other",   "target": [{ "code": "O", "equivalence": "equivalent" }] },
        { "code": "unknown", "target": [{ "code": "U", "equivalence": "equivalent" }] }
      ]
    }]
  }'
```

## Example: FHIR Patient → HL7v2

```bash
curl -X POST http://localhost:8000/convert/fhir-to-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "fhir_resource": {
      "resourceType": "Patient",
      "id": "pt-001",
      "identifier": [{ "use": "usual", "value": "MRN-12345" }],
      "name": [{ "family": "Smith", "given": ["John"] }],
      "gender": "male",
      "birthDate": "1980-06-15"
    },
    "concept_map_id": "<your-map-id>",
    "message_type": "ADT_A01"
  }'
```

**Response:**
```json
{
  "source_format": "FHIR",
  "target_format": "HL7v2",
  "result": "MSH|^~\\&|FHIR2V2|...\rEVN|...\rPID|1|MRN-12345|pt-001||Smith^John||19800615|M",
  "applied_map_id": "<your-map-id>",
  "warnings": []
}
```

## Example: HL7v2 → FHIR Patient

```bash
curl -X POST http://localhost:8000/convert/v2-to-fhir \
  -H "Content-Type: application/json" \
  -d '{
    "v2_message": "MSH|^~\\&|SEND|FAC|REC|FAC|20260101120000||ADT^A01|MSG001|P|2.5\rPID|1|MRN-12345|pt-001||Smith^John||19800615|M",
    "target_resource_type": "Patient",
    "concept_map_id": "<your-map-id>"
  }'
```

---

## Uploading a FHIR ConceptMap file

The `/mappings/upload` endpoint accepts a standard [FHIR ConceptMap](https://www.hl7.org/fhir/conceptmap.html) JSON file:

```bash
curl -X POST http://localhost:8000/mappings/upload \
  -F "file=@my-concept-map.json"
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
fhir-to-v2-engine/
├── app/
│   ├── main.py                   # FastAPI application
│   ├── models.py                 # Pydantic data models
│   ├── store.py                  # In-memory ConceptMap storage
│   ├── routers/
│   │   ├── conversion.py         # /convert endpoints
│   │   ├── frontend.py           # HTML page routes
│   │   └── mappings.py           # /mappings CRUD endpoints
│   ├── services/
│   │   └── mapping_service.py    # Bidirectional conversion logic
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── templates/
│       ├── convert.html
│       ├── index.html
│       ├── mappings.html
│       └── new_mapping.html
├── tests/
│   └── test_engine.py
└── requirements.txt
```

---

## Supported Resource Types

| FHIR Resource | HL7v2 Segments |
|---|---|
| `Patient` | MSH, EVN, PID |
| `Observation` | MSH, OBX |

Support for additional resource types (Encounter, AllergyIntolerance, MedicationRequest, …) can be added by extending `mapping_service.py`.