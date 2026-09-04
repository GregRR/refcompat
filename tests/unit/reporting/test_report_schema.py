"""Compatibility-report JSON Schema contract tests."""

from __future__ import annotations

import copy
import json
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

from refcompat.model.conflict_core import ConflictCoreKind
from refcompat.model.constraints import ConstraintRule, ConstraintState, SatisfactionMode
from refcompat.model.contracts import (
    RequirementLevel,
    RequirementOrigin,
    SequenceBindingValidationState,
    SequenceIdentityProvenance,
)
from refcompat.model.evidence import (
    EvidenceKind,
    EvidenceMethod,
    EvidencePolarity,
    EvidenceStrength,
)
from refcompat.model.interpretation import ConditionKind, FindingKind
from refcompat.model.reference_context import SequenceBindingMethod
from refcompat.model.report import AnalysisIssueKind, AnalysisStatus
from refcompat.model.resources import ArtifactDigestAlgorithm, ResourceKind
from refcompat.model.verdict import CompatibilityVerdict
from refcompat.reporting import REPORT_FORMAT, REPORT_SCHEMA_VERSION

_FIXTURE = (
    Path(__file__).parents[2] / "fixtures" / "milestone7" / "stable-compatible-report-1.0.0.json"
)
_INCOMPATIBLE_FIXTURE = (
    Path(__file__).parents[2] / "fixtures" / "milestone7" / "stable-incompatible-report-1.0.0.json"
)
_SCHEMA_NAME = f"compatibility-report-{REPORT_SCHEMA_VERSION}.schema.json"


class _SchemaValidator(Protocol):
    def validate(self, instance: object) -> None: ...


class _SchemaValidatorClass(Protocol):
    def __call__(self, schema: object) -> _SchemaValidator: ...

    def check_schema(self, schema: object) -> None: ...


class _JsonSchemaModule(Protocol):
    Draft202012Validator: _SchemaValidatorClass
    ValidationError: type[Exception]


def _jsonschema() -> _JsonSchemaModule:
    return cast(_JsonSchemaModule, import_module("jsonschema"))


def _schema() -> dict[str, Any]:
    resource = files("refcompat.schemas").joinpath(_SCHEMA_NAME)
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_FIXTURE.read_text(encoding="utf-8")))


def _validator() -> _SchemaValidator:
    schema = _schema()
    module = _jsonschema()
    module.Draft202012Validator.check_schema(schema)
    return module.Draft202012Validator(schema)


def test_stable_schema_is_packaged_and_self_identifying() -> None:
    schema = _schema()

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:refcompat:schema:compatibility-report:1.0.0"
    report_format = schema["$defs"]["reportFormat"]["properties"]
    assert report_format["name"] == {"const": REPORT_FORMAT}
    assert report_format["schema_version"] == {"const": REPORT_SCHEMA_VERSION}


def test_stable_known_answer_validates_against_exact_schema() -> None:
    _validator().validate(_payload())


def test_stable_incompatible_known_answer_validates_against_exact_schema() -> None:
    payload = cast(
        dict[str, Any],
        json.loads(_INCOMPATIBLE_FIXTURE.read_text(encoding="utf-8")),
    )

    _validator().validate(payload)


def test_schema_accepts_invalid_input_without_scientific_result() -> None:
    payload = _payload()
    payload["analysis"] = {
        "status": "invalid_input",
        "issues": [
            {
                "id": "bad-input",
                "kind": "invalid_input",
                "detail": "input is malformed",
                "resource_ids": ["consumer"],
            }
        ],
    }
    payload["scientific_result"] = None

    _validator().validate(payload)


def test_schema_accepts_partial_nonpositive_scientific_result() -> None:
    payload = _payload()
    payload["analysis"] = {
        "status": "partial",
        "issues": [
            {
                "id": "incomplete-operation",
                "kind": "incomplete_operation",
                "detail": "one requested operation did not complete",
                "resource_ids": ["consumer"],
            }
        ],
    }
    scientific_result = cast(dict[str, Any], payload["scientific_result"])
    verdict = cast(dict[str, Any], scientific_result["verdict"])
    verdict["value"] = "indeterminate"
    verdict["constraint_states"] = {
        "satisfied": [],
        "unsatisfied": [],
        "unresolved": [verdict["mandatory_constraint_ids"][0]],
        "not_applicable": [],
    }
    verdict["basis_finding_ids"] = ["finding:partial"]

    _validator().validate(payload)


def test_exact_schema_rejects_draft_header() -> None:
    payload = _payload()
    payload["report_format"] = {
        "name": REPORT_FORMAT,
        "stability": "draft",
        "revision": 2,
    }

    with pytest.raises(_jsonschema().ValidationError):
        _validator().validate(payload)


def test_exact_schema_rejects_unknown_fields() -> None:
    payload = _payload()
    payload["future_field"] = True

    with pytest.raises(_jsonschema().ValidationError):
        _validator().validate(payload)


def test_exact_schema_rejects_local_artifact_paths() -> None:
    payload = _payload()
    request = cast(dict[str, Any], payload["request"])
    resources = cast(list[dict[str, Any]], request["resources"])
    artifact = cast(dict[str, Any], resources[0]["artifact"])
    artifact["path"] = "/local/machine/reference.fa"

    with pytest.raises(_jsonschema().ValidationError):
        _validator().validate(payload)


def test_exact_schema_rejects_schema_version_mismatch() -> None:
    payload = _payload()
    report_format = copy.deepcopy(cast(dict[str, Any], payload["report_format"]))
    report_format["schema_version"] = "1.1.0"
    payload["report_format"] = report_format

    with pytest.raises(_jsonschema().ValidationError):
        _validator().validate(payload)


def test_analysis_status_controls_scientific_result_presence() -> None:
    payload = _payload()
    payload["analysis"] = {
        "status": "invalid_input",
        "issues": [
            {
                "id": "bad-input",
                "kind": "invalid_input",
                "detail": "input is malformed",
                "resource_ids": [],
            }
        ],
    }

    with pytest.raises(_jsonschema().ValidationError):
        _validator().validate(payload)


def test_schema_closes_current_enum_and_typed_union_inventory() -> None:
    schema = _schema()
    defs = cast(dict[str, Any], schema["$defs"])

    enum_expectations = {
        ("analysis", "status"): AnalysisStatus,
        ("analysisIssue", "kind"): AnalysisIssueKind,
        ("resource", "kind"): ResourceKind,
        ("requirementBase", "origin"): RequirementOrigin,
        ("requirementBase", "level"): RequirementLevel,
        ("evaluation", "state"): ConstraintState,
        ("evidenceItem", "kind"): EvidenceKind,
        ("evidenceItem", "method"): EvidenceMethod,
        ("evidenceItem", "strength"): EvidenceStrength,
        ("evidenceItem", "polarity"): EvidencePolarity,
        ("finding", "kind"): FindingKind,
        ("condition", "kind"): ConditionKind,
        ("conflictCore", "kind"): ConflictCoreKind,
        ("verdict", "value"): CompatibilityVerdict,
        ("sequenceBinding", "method"): SequenceBindingMethod,
    }
    for (definition, property_name), enum_type in enum_expectations.items():
        properties = cast(dict[str, Any], defs[definition]["properties"])
        assert set(properties[property_name]["enum"]) == {item.value for item in enum_type}

    artifact_properties = cast(dict[str, Any], defs["artifactDigest"]["properties"])
    assert {artifact_properties["algorithm"]["const"]} == {
        item.value for item in ArtifactDigestAlgorithm
    }

    requirement_types = {
        variant["allOf"][1]["properties"]["type"]["const"]
        for variant in defs["requirement"]["oneOf"]
    }
    assert requirement_types == {
        "sequence_presence",
        "sequence_length",
        "sequence_identity",
        "sequence_binding",
        "sequence_order",
        "coordinate_bounds",
        "reference_bases",
    }

    capability_types = {
        variant["allOf"][1]["properties"]["type"]["const"]
        for variant in defs["capability"]["oneOf"]
    }
    assert capability_types == {
        "sequence_presence",
        "sequence_length",
        "sequence_identity",
        "sequence_identity_absence",
        "sequence_binding_validation",
        "sequence_order",
        "coordinate_bounds_validation",
        "reference_base_validation",
    }

    capability_variants = cast(list[dict[str, Any]], defs["capability"]["oneOf"])
    identity_variant = next(
        variant
        for variant in capability_variants
        if variant["allOf"][1]["properties"]["type"]["const"] == "sequence_identity"
    )
    identity_properties = cast(dict[str, Any], identity_variant["allOf"][1]["properties"])
    assert set(identity_properties["provenance"]["enum"]) == {
        item.value for item in SequenceIdentityProvenance
    }

    binding_variant = next(
        variant
        for variant in capability_variants
        if variant["allOf"][1]["properties"]["type"]["const"] == "sequence_binding_validation"
    )
    binding_properties = cast(dict[str, Any], binding_variant["allOf"][1]["properties"])
    assert set(binding_properties["state"]["enum"]) == {
        item.value for item in SequenceBindingValidationState
    }

    constraint_properties = cast(dict[str, Any], defs["constraint"]["properties"])
    assert set(constraint_properties["rule"]["enum"]) == {item.value for item in ConstraintRule}

    satisfaction = cast(dict[str, Any], defs["evaluation"]["properties"])["satisfaction_mode"][
        "oneOf"
    ][1]["enum"]
    assert set(satisfaction) == {item.value for item in SatisfactionMode}
