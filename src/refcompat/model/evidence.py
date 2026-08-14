"""Evidence vocabulary used by later compatibility reasoning.

The first identity slice defines the stable evidence tiers without inventing a
full finding/report model before observations and constraints exist. The tier
ordering follows RefCompat's design rule that content-derived identity cannot
be outweighed by larger quantities of weaker metadata or heuristic evidence.
"""

from enum import StrEnum


class EvidenceStrength(StrEnum):
    """Qualitative evidence tiers; these are not numeric compatibility scores."""

    TIER_A_CONCLUSIVE_CONTENT = "tier_a_conclusive_content"
    TIER_B_DIRECT_STRUCTURAL = "tier_b_direct_structural"
    TIER_C_PROVENANCE_METADATA = "tier_c_provenance_metadata"
    TIER_D_HEURISTIC_CONTEXT = "tier_d_heuristic_context"


class EvidencePolarity(StrEnum):
    """Whether a piece of evidence supports or contradicts a proposition."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
