from __future__ import annotations

import pytest
from jsonschema import ValidationError

from amica.schemas import load_schema
from amica.validation import ensure_services_registered, validate_workflow_output


@pytest.mark.unit
def test_load_schema_returns_dict() -> None:
    schema = load_schema("workflow_output.schema.json")
    assert schema["title"] == "WorkflowOutput"
    assert "properties" in schema


@pytest.mark.unit
def test_validate_workflow_output_accepts_valid_payload() -> None:
    payload = {
        "status": "completed",
        "summary": "Done",
        "actions": [{"name": "svc"}],
        "warnings": [],
    }
    validate_workflow_output(payload)


@pytest.mark.unit
def test_validate_workflow_output_rejects_missing_fields() -> None:
    with pytest.raises(ValidationError):
        validate_workflow_output({"status": "completed"})


@pytest.mark.unit
def test_ensure_services_registered_detects_missing() -> None:
    with pytest.raises(ValidationError):
        ensure_services_registered(["svc_a", "svc_b"], ["svc_a"])


@pytest.mark.unit
def test_ensure_services_registered_passes_when_all_present() -> None:
    ensure_services_registered(["svc_a"], ["svc_a", "svc_b"])
