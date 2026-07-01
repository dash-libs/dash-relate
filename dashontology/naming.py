"""
Table name → Object Type name normalization.

Pipeline: strip catalog/schema → strip known prefixes → singularize → CamelCase.
Accepts an optional glossary dict for custom mappings and abbreviation expansion.
"""
from __future__ import annotations

_STRIP_PREFIXES = [
    "dim_", "fact_", "fct_", "stg_", "staging_",
    "raw_", "src_", "bronze_", "silver_", "gold_",
    "d_", "f_", "t_", "v_",
]

_IRREGULAR_PLURALS: dict[str, str] = {
    "people": "person",
    "children": "child",
    "criteria": "criterion",
    "data": "datum",
    "analyses": "analysis",
    "statuses": "status",
    "matrices": "matrix",
    "indices": "index",
    "vertices": "vertex",
    "aliases": "alias",
    "series": "series",
    "species": "species",
}


def strip_prefix(name: str) -> str:
    """Remove known data lake prefixes (dim_, fact_, stg_, etc.)."""
    lower = name.lower()
    for prefix in sorted(_STRIP_PREFIXES, key=len, reverse=True):
        if lower.startswith(prefix):
            return name[len(prefix):]
    return name


def singularize(word: str) -> str:
    """
    Naive English singularizer. Handles the most common patterns
    found in data lake table naming conventions.
    """
    lower = word.lower()

    if lower in _IRREGULAR_PLURALS:
        # Preserve original case pattern
        singular = _IRREGULAR_PLURALS[lower]
        return singular.capitalize() if word[0].isupper() else singular

    # Already singular guard — short words or known invariants
    if len(lower) <= 3:
        return word

    # ies → y (categories → category)
    if lower.endswith("ies") and len(lower) > 4:
        return word[:-3] + "y"

    # sses → ss (addresses → address — NOT address+s → addres)
    if lower.endswith("sses"):
        return word[:-2]

    # xes / zes / ches / shes → remove es
    if lower.endswith(("xes", "zes", "ches", "shes")):
        return word[:-2]

    # ses — status/statuses edge case handled by irregular; otherwise try -es
    if lower.endswith("ses") and len(lower) > 5:
        return word[:-2]

    # Ends in 's' but not 'ss' or known ok endings
    if lower.endswith("s") and not lower.endswith("ss"):
        return word[:-1]

    return word


def to_camel_case(snake: str) -> str:
    """customer_order_item → CustomerOrderItem"""
    return "".join(part.capitalize() for part in snake.split("_") if part)


def normalize_name(
    full_table_name: str,
    glossary: dict[str, str] = None,
) -> str:
    """
    Convert a table name into a CamelCase object type name.

    full_table_name — may include catalog/schema (e.g. "cat.schema.dim_customer")
    glossary        — optional {table_name: object_type} override map

    Examples:
        "cat.silver.dim_customer"  → "Customer"
        "fact_order_items"         → "OrderItem"
        "stg_raw_events"           → "RawEvent"
    """
    bare = full_table_name.split(".")[-1]

    # Glossary takes priority
    if glossary:
        if full_table_name in glossary:
            return glossary[full_table_name]
        if bare in glossary:
            return glossary[bare]
        if bare.lower() in glossary:
            return glossary[bare.lower()]

    stripped = strip_prefix(bare)
    # CamelCase the snake_case segments, then singularize the last word
    parts = [p for p in stripped.split("_") if p]
    if not parts:
        return to_camel_case(bare)

    # Singularize the last part (e.g. customers → customer → Customer)
    parts[-1] = singularize(parts[-1])
    return "".join(p.capitalize() for p in parts)
