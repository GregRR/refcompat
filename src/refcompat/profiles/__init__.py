"""Consumer/ecosystem-specific compatibility requirements. Profiles do not rewrite facts."""

from refcompat.profiles.ucsc import (
    UcscDatabaseId,
    UcscProviderCompleteness,
    UcscProviderContextId,
    UcscProviderDimension,
    UcscProviderSnapshot,
    UcscProviderSource,
    UcscProviderSourceId,
    UcscSequence,
    UcscSequenceAlias,
)

__all__ = [
    "UcscDatabaseId",
    "UcscProviderCompleteness",
    "UcscProviderContextId",
    "UcscProviderDimension",
    "UcscProviderSnapshot",
    "UcscProviderSource",
    "UcscProviderSourceId",
    "UcscSequence",
    "UcscSequenceAlias",
]
