"""
Lightweight table role classifier — mirrors dashgov.classifier logic
without importing from dashgov (keeping dash-ontology self-contained).
"""
from __future__ import annotations

_STAGING_PREFIXES   = {"stg_", "staging_", "tmp_", "temp_", "raw_", "src_", "landing_", "bronze_"}
_DIMENSION_PREFIXES = {"dim_", "d_"}
_FACT_PREFIXES      = {"fact_", "fct_", "f_"}
_AGG_SUFFIXES       = {
    "_agg", "_aggregated", "_summary", "_report",
    "_metrics", "_stats", "_kpi", "_rollup",
    "_daily", "_weekly", "_monthly", "_yearly",
}
_JUNCTION_SUFFIXES  = {"_map", "_mapping", "_xref", "_bridge", "_link", "_rel", "_assoc"}
_FK_SUFFIXES = ("_id", "_pk", "_key", "_fk", "_ref", "_uuid")


def _name(full: str) -> str:
    return full.split(".")[-1].lower()


def classify_table_role(
    full_name: str,
    columns: list[dict],
    n_upstream: int = 0,
    n_downstream: int = 0,
) -> tuple[str, float]:
    name = _name(full_name)
    n_cols = len(columns)
    n_fk = sum(
        1 for c in columns
        if c.get("name", "").lower() not in ("id",)
        and c.get("name", "").lower().endswith(_FK_SUFFIXES)
    )

    if any(name.startswith(p) for p in _STAGING_PREFIXES):
        return "staging", 0.90
    if any(name.endswith(s) for s in _AGG_SUFFIXES):
        return "aggregation", 0.90
    if any(name.startswith(p) for p in _DIMENSION_PREFIXES):
        return "entity", 0.90
    if any(name.endswith(s) for s in _JUNCTION_SUFFIXES):
        return "junction", 0.88
    if n_cols >= 2 and n_fk >= 2 and n_fk / max(n_cols, 1) >= 0.6:
        return "junction", 0.80
    if n_upstream == 0 and n_cols >= 3:
        return "entity", 0.78
    if n_upstream >= 1 and n_fk >= 1 and n_downstream >= 1:
        return "fact", 0.70
    if n_upstream >= 2 and n_downstream == 0:
        return "aggregation", 0.60
    return "unknown", 0.40
