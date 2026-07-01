"""
Cardinality inference for object type links.

Uses column statistics (unique counts vs total counts) from both sides
of a join to determine whether the relationship is 1:1, 1:N, or N:M.
All pure Python — no Spark required.
"""
from __future__ import annotations


def infer_cardinality(
    from_unique: int,
    from_total: int,
    to_unique: int,
    to_total: int,
    one_to_one_threshold: float = 0.95,
) -> tuple[str, float]:
    """
    Infer cardinality from column uniqueness stats.

    Parameters
    ----------
    from_unique : distinct values in the FK column of the *from* table
    from_total  : total non-null rows in the FK column
    to_unique   : distinct values in the PK column of the *to* table
    to_total    : total non-null rows in the PK column

    Returns
    -------
    (cardinality: str, confidence: float)
    cardinality ∈ {"1:1", "1:N", "N:M"}

    Heuristics
    ----------
    - to_unique ≈ to_total   → PK side is truly unique (good PK)
    - from_unique ≈ from_total → FK side is also unique → 1:1
    - from_unique < from_total → many FK rows per PK value → 1:N
    - from_unique ≈ from_total AND to_unique < to_total → N:M or data quality issue
    """
    if from_total <= 0 or to_total <= 0:
        return "1:N", 0.40   # can't tell, default to most common

    from_uniq_rate = from_unique / from_total
    to_uniq_rate   = to_unique / to_total

    pk_is_unique = to_uniq_rate >= one_to_one_threshold

    if not pk_is_unique:
        # PK side has duplicates — likely N:M or a bad join
        return "N:M", 0.55

    fk_is_unique = from_uniq_rate >= one_to_one_threshold

    if fk_is_unique:
        # Both sides are unique → 1:1
        return "1:1", 0.85

    # FK has duplicates, PK is unique → 1:N (one PK row → many FK rows)
    # Confidence scales with how non-unique the FK side is
    spread = 1.0 - from_uniq_rate   # 0 = all unique, 1 = all same value
    confidence = min(0.95, 0.65 + spread * 0.3)
    return "1:N", round(confidence, 3)


def infer_cardinality_from_ratio(avg_fk_per_pk: float) -> tuple[str, float]:
    """
    Simpler heuristic when only the average FK-per-PK ratio is known.

    avg_fk_per_pk — average number of FK rows per unique PK value

    Examples:
        1.0  → 1:1
        3.5  → 1:N
        12.0 → 1:N (strong)
    """
    if avg_fk_per_pk <= 1.05:
        return "1:1", 0.80
    if avg_fk_per_pk <= 1.5:
        return "1:N", 0.60   # borderline
    return "1:N", min(0.95, 0.70 + min(avg_fk_per_pk, 20) / 100)


def cardinality_label(card: str) -> str:
    """Human-readable cardinality label."""
    return {
        "1:1": "one-to-one",
        "1:N": "one-to-many",
        "N:M": "many-to-many",
    }.get(card, card)
