"""
Ontology inference engine.

Takes a lineage graph (as a plain dict, compatible with dashgov.LineageGraph.to_dict())
plus table schemas and produces an OntologyGraph with confidence-scored
ObjectTypes, Links, and Metrics.

No AI, no LLM, no Spark — pure deterministic heuristics.
"""
from __future__ import annotations

from dashontology.models import ObjectType, Link, Metric, OntologyGraph, Property
from dashontology.naming import normalize_name

# Column names that are almost certainly primary keys
_PK_NAMES = {"id", "pk", "key", "uuid", "guid"}
# Suffixes that mark foreign key columns
_FK_SUFFIXES = ("_id", "_pk", "_key", "_fk", "_ref", "_uuid")
# Roles to include as primary object types (exclude staging/unknown by default)
_ENTITY_ROLES = {"entity", "fact", "junction"}
# Metric table roles
_METRIC_ROLES = {"aggregation"}
# PII column name patterns
_PII_PATTERNS = {
    "email", "mail", "phone", "mobile", "ssn", "social_security",
    "dob", "birth", "address", "postcode", "zipcode", "zip",
    "passport", "license", "national_id", "tax_id", "credit_card",
    "card_number", "iban", "salary", "income",
}


def _is_pk(col_name: str) -> bool:
    lower = col_name.lower()
    return lower in _PK_NAMES or lower == "id"


def _is_fk(col_name: str) -> bool:
    lower = col_name.lower()
    return lower.endswith(_FK_SUFFIXES) and lower not in _PK_NAMES


def _is_pii(col_name: str) -> bool:
    lower = col_name.lower()
    return any(pat in lower for pat in _PII_PATTERNS)


def _build_properties(columns: list[dict], fk_cols: set[str]) -> list[Property]:
    return [
        Property(
            name=c["name"],
            column=c["name"],
            data_type=c.get("type", "unknown"),
            is_nullable=c.get("nullable", True),
            is_primary_key=_is_pk(c["name"]),
            is_foreign_key=c["name"] in fk_cols or _is_fk(c["name"]),
            is_pii=_is_pii(c["name"]),
        )
        for c in columns
    ]


def _column_edge_to_fk_map(
    column_edges: list[dict],
) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """
    Build {(target_table, target_column): [(source_table, source_column), ...]}
    from the column lineage edges.
    """
    fk_map: dict = {}
    for e in column_edges:
        key = (e["target_table"], e["target_column"])
        fk_map.setdefault(key, []).append((e["source_table"], e["source_column"]))
    return fk_map


def _infer_links_from_column_edges(
    column_edges: list[dict],
    name_map: dict[str, str],          # {table_full_name: object_type_name}
    table_roles: dict[str, str],
    glossary: dict[str, str],
) -> list[Link]:
    """
    Derive Link objects from column-level lineage.

    Each column edge that goes from a PK column to an FK column in a different
    table (or vice versa) represents a foreign key relationship → a Link.
    """
    links: list[Link] = []
    seen: set[tuple] = set()

    for e in column_edges:
        src_tbl = e["source_table"]
        src_col = e["source_column"]
        tgt_tbl = e["target_table"]
        tgt_col = e["target_column"]

        if src_tbl == tgt_tbl:
            continue  # same-table transformation, not a relationship

        # We're interested in cases where target column is an FK-looking column
        # tracing back to a PK-looking column in the source table
        src_looks_pk = _is_pk(src_col)
        tgt_looks_fk = _is_fk(tgt_col)

        if not (src_looks_pk or tgt_looks_fk):
            continue

        from_name = name_map.get(tgt_tbl)
        to_name   = name_map.get(src_tbl)
        if not from_name or not to_name or from_name == to_name:
            continue

        link_key = (from_name, to_name, tgt_col, src_col)
        if link_key in seen:
            continue
        seen.add(link_key)

        # Cardinality: FK column on tgt_tbl → PK on src_tbl → 1:N by default
        # (one src_tbl row → many tgt_tbl rows)
        cardinality = "1:N"
        confidence  = 0.80 if src_looks_pk and tgt_looks_fk else 0.65

        link_name = f"{from_name}_{to_name}"
        links.append(Link(
            name=link_name,
            from_type=from_name,
            to_type=to_name,
            cardinality=cardinality,
            from_column=tgt_col,
            to_column=src_col,
            confidence=confidence,
        ))

    return links


def _infer_links_from_naming(
    tables: dict[str, dict],
    name_map: dict[str, str],
) -> list[Link]:
    """
    Fallback: infer FK links from column naming patterns alone
    (used when column-level lineage is absent).

    e.g. orders.customer_id → customers.id
    """
    links: list[Link] = []
    seen: set[tuple] = set()

    # Build {table_bare_name: full_name}
    bare_to_full = {full.split(".")[-1].lower(): full for full in tables}

    for full_name, tbl_info in tables.items():
        from_type = name_map.get(full_name)
        if not from_type:
            continue
        for col in tbl_info.get("columns", []):
            col_name = col.get("name", "")
            if not _is_fk(col_name):
                continue
            # Strip _id/_fk etc to guess the referenced table name
            for suffix in _FK_SUFFIXES:
                if col_name.lower().endswith(suffix):
                    ref_bare = col_name[: -len(suffix)].lower()
                    break
            else:
                continue

            # Look for a table with that bare name (singular or plural)
            ref_full = bare_to_full.get(ref_bare) or bare_to_full.get(ref_bare + "s")
            if not ref_full or ref_full == full_name:
                continue

            to_type = name_map.get(ref_full)
            if not to_type or to_type == from_type:
                continue

            link_key = (from_type, to_type, col_name)
            if link_key in seen:
                continue
            seen.add(link_key)

            links.append(Link(
                name=f"{from_type}_{to_type}",
                from_type=from_type,
                to_type=to_type,
                cardinality="1:N",
                from_column=col_name,
                to_column="id",
                confidence=0.60,   # lower — inferred from naming only
            ))

    return links


def infer_ontology(
    lineage_graph: dict,
    schemas: dict[str, list[dict]] = None,
    glossary: dict[str, str] = None,
    min_confidence: float = 0.50,
    include_staging: bool = False,
) -> OntologyGraph:
    """
    Infer an OntologyGraph from a lineage graph dict.

    Parameters
    ----------
    lineage_graph
        Dict from LineageGraph.to_dict() (or equivalent).
        Keys: "tables", "table_edges", "column_edges"
    schemas
        Optional {table_full_name: [{name, type, nullable}]} override.
        If provided, these columns take priority over lineage_graph["tables"].
    glossary
        Optional {table_name: ObjectType_name} for custom name mappings.
    min_confidence
        Drop inferences below this threshold.
    include_staging
        Whether to include staging/temp tables as ObjectTypes.

    Returns
    -------
    OntologyGraph with ObjectType, Link, and Metric lists.
    """
    from dashontology.models import ObjectType, Metric, OntologyGraph

    tables_raw = lineage_graph.get("tables", {})
    table_edges = lineage_graph.get("table_edges", [])
    column_edges = lineage_graph.get("column_edges", [])

    # Compute upstream counts for role classification
    upstream_counts: dict[str, int] = {}
    downstream_counts: dict[str, int] = {}
    for e in table_edges:
        downstream_counts[e["source"]] = downstream_counts.get(e["source"], 0) + 1
        upstream_counts[e["target"]] = upstream_counts.get(e["target"], 0) + 1

    # Classify table roles using dashgov-style heuristics (inlined to avoid import)
    from dashontology._classifier_bridge import classify_table_role
    table_roles: dict[str, str] = {}
    table_confidences: dict[str, float] = {}
    for full_name, tbl_info in tables_raw.items():
        cols = schemas.get(full_name, tbl_info.get("columns", [])) if schemas else tbl_info.get("columns", [])
        role, conf = classify_table_role(
            full_name=full_name,
            columns=cols,
            n_upstream=upstream_counts.get(full_name, 0),
            n_downstream=downstream_counts.get(full_name, 0),
        )
        table_roles[full_name] = role
        table_confidences[full_name] = conf

    # ── Build name_map for ALL tables ───────────────────────────────────────
    # All tables need normalized names for link inference even if they don't
    # become ObjectTypes (e.g. silver pass-through tables with low confidence).
    name_map: dict[str, str] = {
        full_name: normalize_name(full_name, glossary)
        for full_name in tables_raw
    }

    # ── Build ObjectTypes and Metrics ────────────────────────────────────────
    object_types: list[ObjectType] = []
    metrics: list[Metric] = []

    for full_name, tbl_info in tables_raw.items():
        role = table_roles.get(full_name, "unknown")
        conf = table_confidences.get(full_name, 0.4)

        if conf < min_confidence:
            continue

        cols = schemas.get(full_name, tbl_info.get("columns", [])) if schemas else tbl_info.get("columns", [])
        obj_name = name_map[full_name]

        if role in _METRIC_ROLES:
            grain = _guess_grain(cols)
            metrics.append(Metric(
                name=obj_name,
                source_table=full_name,
                grain=grain,
            ))
        elif role in _ENTITY_ROLES or (include_staging and role == "staging"):
            fk_cols = {c["name"] for c in cols if _is_fk(c.get("name", ""))}
            props = _build_properties(cols, fk_cols)
            object_types.append(ObjectType(
                name=obj_name,
                source_table=full_name,
                properties=props,
                role=role,
                confidence=conf,
            ))

    # ── Build Links ──────────────────────────────────────────────────────────
    links: list[Link] = []
    if column_edges:
        links = _infer_links_from_column_edges(column_edges, name_map, table_roles, glossary or {})
    if not links:
        links = _infer_links_from_naming(tables_raw, name_map)

    links = [link for link in links if link.confidence >= min_confidence]

    return OntologyGraph(object_types=object_types, links=links, metrics=metrics)


def _guess_grain(columns: list[dict]) -> str:
    """Guess the time/entity grain of an aggregation table from its columns."""
    col_names = [c.get("name", "").lower() for c in columns]
    for grain in ("hour", "day", "week", "month", "quarter", "year", "date", "period"):
        if any(grain in n for n in col_names):
            return grain
    # Look for entity grain
    for name in col_names:
        if _is_fk(name):
            return name.rstrip("_id").rstrip("_fk")
    return "unknown"
