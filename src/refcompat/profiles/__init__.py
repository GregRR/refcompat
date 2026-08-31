"""Consumer/ecosystem-specific compatibility requirements. Profiles do not rewrite facts."""

from refcompat.profiles.ucsc import (
    UcscDatabaseId,
    UcscNameResolution,
    UcscNameResolutionMethod,
    UcscNameResolutionReason,
    UcscNameResolutionState,
    UcscProviderCompleteness,
    UcscProviderContextId,
    UcscProviderDimension,
    UcscProviderSnapshot,
    UcscProviderSource,
    UcscProviderSourceId,
    UcscSequence,
    UcscSequenceAlias,
    UcscTargetBinding,
    UcscTargetBindingId,
    UcscTargetResolution,
    UcscTargetResolutionReason,
    UcscTargetResolutionState,
)
from refcompat.profiles.ucsc_reasoning import (
    resolve_ucsc_sequence_name,
    resolve_ucsc_target,
)

__all__ = [
    "UcscDatabaseId",
    "UcscNameResolution",
    "UcscNameResolutionMethod",
    "UcscNameResolutionReason",
    "UcscNameResolutionState",
    "UcscProviderCompleteness",
    "UcscProviderContextId",
    "UcscProviderDimension",
    "UcscProviderSnapshot",
    "UcscProviderSource",
    "UcscProviderSourceId",
    "UcscSequence",
    "UcscSequenceAlias",
    "UcscTargetBinding",
    "UcscTargetBindingId",
    "UcscTargetResolution",
    "UcscTargetResolutionReason",
    "UcscTargetResolutionState",
    "resolve_ucsc_sequence_name",
    "resolve_ucsc_target",
]
