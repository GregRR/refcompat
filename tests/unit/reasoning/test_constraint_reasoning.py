"""Unit tests for the first exact typed constraint evaluator."""

from __future__ import annotations

from refcompat.model.constraints import (
    ConstraintId,
    ConstraintRule,
    ConstraintState,
    SatisfactionMode,
)
from refcompat.model.contracts import (
    CapabilityId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderCapability,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.identity import Md5Digest, RefgetSequenceId
from refcompat.model.resources import ResourceId
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint

_REQUIRED = ResourceId("consumer")
_ANCHOR = ResourceId("reference")
_MD5_A = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_B = Md5Digest("ca773511c152b8191d2757f5a45ff252")
_REFGET = RefgetSequenceId("SQ.01234567890123456789012345678901")


def _presence_requirement(
    level: RequirementLevel = RequirementLevel.MANDATORY,
) -> SequencePresenceRequirement:
    return SequencePresenceRequirement(
        id=RequirementId("req-presence"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=level,
        sequence_name="chr1",
    )


def test_builder_filters_unrelated_capability_types() -> None:
    requirement = _presence_requirement()
    presence = SequencePresenceCapability(
        id=CapabilityId("presence"), resource_id=_ANCHOR, sequence_name="chr1", present=True
    )
    length = SequenceLengthCapability(
        id=CapabilityId("length"), resource_id=_ANCHOR, sequence_name="chr1", length=4
    )

    constraint = build_constraint(ConstraintId("constraint"), requirement, (presence, length))

    assert constraint.rule is ConstraintRule.SEQUENCE_PRESENCE
    assert constraint.candidate_capabilities == (presence,)


def test_presence_requires_explicit_negative_capability_to_prove_absence() -> None:
    unresolved = evaluate_constraint(
        build_constraint(ConstraintId("missing-evidence"), _presence_requirement(), ())
    )
    absent = SequencePresenceCapability(
        id=CapabilityId("absent"), resource_id=_ANCHOR, sequence_name="chr1", present=False
    )
    unsatisfied = evaluate_constraint(
        build_constraint(ConstraintId("proven-absent"), _presence_requirement(), (absent,))
    )

    assert unresolved.state is ConstraintState.UNRESOLVED
    assert unresolved.relevant_capability_ids == ()
    assert unsatisfied.state is ConstraintState.UNSATISFIED
    assert unsatisfied.relevant_capability_ids == (CapabilityId("absent"),)


def test_presence_exact_match_is_satisfied() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_ANCHOR, sequence_name="chr1", present=True
    )

    result = evaluate_constraint(
        build_constraint(ConstraintId("constraint"), _presence_requirement(), (present,))
    )

    assert result.state is ConstraintState.SATISFIED
    assert result.satisfaction_mode is SatisfactionMode.EXACT


def test_conflicting_presence_capabilities_are_unresolved() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_ANCHOR, sequence_name="chr1", present=True
    )
    absent = SequencePresenceCapability(
        id=CapabilityId("absent"), resource_id=_ANCHOR, sequence_name="chr1", present=False
    )

    result = evaluate_constraint(
        build_constraint(ConstraintId("constraint"), _presence_requirement(), (present, absent))
    )

    assert result.state is ConstraintState.UNRESOLVED
    assert result.relevant_capability_ids == (CapabilityId("present"), CapabilityId("absent"))


def test_length_match_conflict_and_missing_name_are_distinct() -> None:
    requirement = SequenceLengthRequirement(
        id=RequirementId("req-length"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )
    matching = SequenceLengthCapability(
        id=CapabilityId("matching"), resource_id=_ANCHOR, sequence_name="chr1", length=4
    )
    wrong = SequenceLengthCapability(
        id=CapabilityId("wrong"), resource_id=_ANCHOR, sequence_name="chr1", length=5
    )
    other_name = SequenceLengthCapability(
        id=CapabilityId("other"), resource_id=_ANCHOR, sequence_name="chr2", length=4
    )

    satisfied = evaluate_constraint(build_constraint(ConstraintId("ok"), requirement, (matching,)))
    unsatisfied = evaluate_constraint(build_constraint(ConstraintId("bad"), requirement, (wrong,)))
    unresolved = evaluate_constraint(
        build_constraint(ConstraintId("unknown"), requirement, (other_name,))
    )

    assert satisfied.state is ConstraintState.SATISFIED
    assert unsatisfied.state is ConstraintState.UNSATISFIED
    assert unresolved.state is ConstraintState.UNRESOLVED


def test_conflicting_length_capabilities_do_not_average_to_a_result() -> None:
    requirement = SequenceLengthRequirement(
        id=RequirementId("req-length"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        length=4,
    )
    matching = SequenceLengthCapability(
        id=CapabilityId("matching"), resource_id=_ANCHOR, sequence_name="chr1", length=4
    )
    wrong = SequenceLengthCapability(
        id=CapabilityId("wrong"), resource_id=_ANCHOR, sequence_name="chr1", length=5
    )

    result = evaluate_constraint(
        build_constraint(ConstraintId("constraint"), requirement, (matching, wrong))
    )

    assert result.state is ConstraintState.UNRESOLVED


def test_identity_requires_same_identity_scheme_and_local_name() -> None:
    requirement = SequenceIdentityRequirement(
        id=RequirementId("req-md5"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_name="chr1",
        identity=_MD5_A,
    )
    matching = SequenceIdentityCapability(
        id=CapabilityId("matching"),
        resource_id=_ANCHOR,
        sequence_name="chr1",
        identity=_MD5_A,
        provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    wrong_md5 = SequenceIdentityCapability(
        id=CapabilityId("wrong"),
        resource_id=_ANCHOR,
        sequence_name="chr1",
        identity=_MD5_B,
        provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    refget = SequenceIdentityCapability(
        id=CapabilityId("refget"),
        resource_id=_ANCHOR,
        sequence_name="chr1",
        identity=_REFGET,
        provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    renamed = SequenceIdentityCapability(
        id=CapabilityId("renamed"),
        resource_id=_ANCHOR,
        sequence_name="1",
        identity=_MD5_A,
        provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
    )

    satisfied = evaluate_constraint(build_constraint(ConstraintId("ok"), requirement, (matching,)))
    unsatisfied = evaluate_constraint(
        build_constraint(ConstraintId("bad"), requirement, (wrong_md5,))
    )
    different_scheme = evaluate_constraint(
        build_constraint(ConstraintId("scheme"), requirement, (refget,))
    )
    different_name = evaluate_constraint(
        build_constraint(ConstraintId("name"), requirement, (renamed,))
    )

    assert satisfied.state is ConstraintState.SATISFIED
    assert satisfied.satisfaction_mode is SatisfactionMode.VERIFIED_SEQUENCE_IDENTITY
    assert unsatisfied.state is ConstraintState.UNSATISFIED
    assert different_scheme.state is ConstraintState.UNRESOLVED
    assert different_name.state is ConstraintState.UNRESOLVED


def test_order_is_exact_and_does_not_ignore_reordering() -> None:
    requirement = SequenceOrderRequirement(
        id=RequirementId("req-order"),
        resource_id=_REQUIRED,
        origin=RequirementOrigin.CORE_FORMAT,
        level=RequirementLevel.MANDATORY,
        sequence_names=("chr1", "chr2"),
    )
    matching = SequenceOrderCapability(
        id=CapabilityId("matching"), resource_id=_ANCHOR, sequence_names=("chr1", "chr2")
    )
    reordered = SequenceOrderCapability(
        id=CapabilityId("reordered"), resource_id=_ANCHOR, sequence_names=("chr2", "chr1")
    )

    satisfied = evaluate_constraint(build_constraint(ConstraintId("ok"), requirement, (matching,)))
    unsatisfied = evaluate_constraint(
        build_constraint(ConstraintId("bad"), requirement, (reordered,))
    )

    assert satisfied.state is ConstraintState.SATISFIED
    assert unsatisfied.state is ConstraintState.UNSATISFIED


def test_requirement_level_does_not_change_constraint_truth() -> None:
    present = SequencePresenceCapability(
        id=CapabilityId("present"), resource_id=_ANCHOR, sequence_name="chr1", present=True
    )

    mandatory = evaluate_constraint(
        build_constraint(
            ConstraintId("constraint"),
            _presence_requirement(RequirementLevel.MANDATORY),
            (present,),
        )
    )
    advisory = evaluate_constraint(
        build_constraint(
            ConstraintId("constraint"),
            _presence_requirement(RequirementLevel.ADVISORY),
            (present,),
        )
    )

    assert mandatory == advisory
