"""
End-to-end tests for the ontology inference engine.

Uses a mock e-commerce lineage graph:
  raw.customers ──► silver.customers ──► gold.customers (entity)
  raw.orders    ──► silver.orders    ──► gold.order_summary_agg (aggregation)
  raw.products  ──► silver.products
  silver.orders × silver.order_items ──► gold.order_line_fact (fact)
"""
import pytest
from dashontology.inference import infer_ontology
from dashontology.models import OntologyGraph, ObjectType, Link


def _col(name, type_="string", nullable=True):
    return {"name": name, "type": type_, "nullable": nullable}


def _ecommerce_lineage():
    tables = {
        "cat.raw.customers":    {"columns": [_col("id", "bigint"), _col("email"), _col("name")]},
        "cat.raw.orders":       {"columns": [_col("id", "bigint"), _col("customer_id", "bigint"), _col("total", "double")]},
        "cat.raw.products":     {"columns": [_col("id", "bigint"), _col("name"), _col("price", "double")]},
        "cat.silver.customers": {"columns": [_col("id", "bigint"), _col("email"), _col("name")]},
        "cat.silver.orders":    {"columns": [_col("id", "bigint"), _col("customer_id", "bigint"), _col("total", "double")]},
        "cat.silver.products":  {"columns": [_col("id", "bigint"), _col("name"), _col("price", "double")]},
        "cat.silver.order_items_map": {"columns": [_col("order_id", "bigint"), _col("product_id", "bigint"), _col("qty", "int")]},
        "cat.gold.customers":        {"columns": [_col("id", "bigint"), _col("email"), _col("name")]},
        "cat.gold.order_summary_agg":{"columns": [_col("month"), _col("customer_id", "bigint"), _col("revenue", "double")]},
    }
    table_edges = [
        {"source": "cat.raw.customers",    "target": "cat.silver.customers"},
        {"source": "cat.raw.orders",        "target": "cat.silver.orders"},
        {"source": "cat.raw.products",      "target": "cat.silver.products"},
        {"source": "cat.silver.customers",  "target": "cat.gold.customers"},
        {"source": "cat.silver.orders",     "target": "cat.gold.order_summary_agg"},
        {"source": "cat.silver.customers",  "target": "cat.gold.order_summary_agg"},
    ]
    column_edges = [
        # customers.id → silver.customers.id
        {"source_table": "cat.raw.customers", "source_column": "id",
         "target_table": "cat.silver.customers", "target_column": "id"},
        # orders.customer_id ← silver.customers.id (FK relationship)
        {"source_table": "cat.silver.customers", "source_column": "id",
         "target_table": "cat.silver.orders", "target_column": "customer_id"},
    ]
    return {"tables": tables, "table_edges": table_edges, "column_edges": column_edges}


# ── Basic inference ───────────────────────────────────────────────────────────

def test_infer_returns_ontology_graph():
    g = infer_ontology(_ecommerce_lineage())
    assert isinstance(g, OntologyGraph)


def test_infer_produces_object_types():
    g = infer_ontology(_ecommerce_lineage())
    assert len(g.object_types) > 0


def test_infer_produces_metrics_for_agg_tables():
    g = infer_ontology(_ecommerce_lineage())
    metric_names = [m.name for m in g.metrics]
    assert any("Summary" in n or "Agg" in n or "Order" in n for n in metric_names)


def test_infer_detects_entity_tables():
    g = infer_ontology(_ecommerce_lineage())
    roles = {o.role for o in g.object_types}
    assert "entity" in roles


def test_infer_detects_junction_table():
    g = infer_ontology(_ecommerce_lineage())
    junction_types = [o for o in g.object_types if o.role == "junction"]
    assert len(junction_types) >= 1


# ── Name normalization applied ────────────────────────────────────────────────

def test_normalized_names_are_camel_case():
    g = infer_ontology(_ecommerce_lineage())
    for o in g.object_types:
        assert o.name[0].isupper(), f"Expected CamelCase: {o.name}"
        assert "_" not in o.name, f"Snake case not stripped: {o.name}"


def test_customer_entity_inferred():
    g = infer_ontology(_ecommerce_lineage())
    names = {o.name for o in g.object_types}
    assert "Customer" in names


# ── Links ─────────────────────────────────────────────────────────────────────

def test_customer_order_link_inferred():
    g = infer_ontology(_ecommerce_lineage())
    link_pairs = {(l.from_type, l.to_type) for l in g.links}
    # Column edge: silver.customers.id → silver.orders.customer_id → Order→Customer link
    assert any("Customer" in pair for pair in link_pairs)


def test_link_cardinality_set():
    g = infer_ontology(_ecommerce_lineage())
    for l in g.links:
        assert l.cardinality in ("1:1", "1:N", "N:M")


def test_link_confidence_in_range():
    g = infer_ontology(_ecommerce_lineage())
    for l in g.links:
        assert 0.0 <= l.confidence <= 1.0


# ── Glossary override ─────────────────────────────────────────────────────────

def test_glossary_overrides_name():
    glossary = {"customers": "Client"}
    g = infer_ontology(_ecommerce_lineage(), glossary=glossary)
    names = {o.name for o in g.object_types}
    assert "Client" in names


# ── min_confidence filter ─────────────────────────────────────────────────────

def test_high_confidence_filter_reduces_objects():
    g_low  = infer_ontology(_ecommerce_lineage(), min_confidence=0.0)
    g_high = infer_ontology(_ecommerce_lineage(), min_confidence=0.90)
    assert len(g_high.object_types) <= len(g_low.object_types)


# ── Properties ───────────────────────────────────────────────────────────────

def test_pk_column_flagged():
    g = infer_ontology(_ecommerce_lineage())
    customer = next((o for o in g.object_types if o.name == "Customer"), None)
    if customer:
        pk_props = [p for p in customer.properties if p.is_primary_key]
        assert len(pk_props) >= 1


def test_fk_column_flagged():
    g = infer_ontology(_ecommerce_lineage())
    # order-like types should have customer_id as FK
    order_type = next(
        (o for o in g.object_types if "Order" in o.name and "order_id" not in o.name.lower()),
        None,
    )
    if order_type:
        fk_props = [p for p in order_type.properties if p.is_foreign_key]
        assert len(fk_props) >= 1


def test_pii_column_flagged():
    g = infer_ontology(_ecommerce_lineage())
    customer = next((o for o in g.object_types if o.name == "Customer"), None)
    if customer:
        pii_props = [p for p in customer.properties if p.is_pii]
        assert any(p.name == "email" for p in pii_props)


# ── OntologyGraph API ─────────────────────────────────────────────────────────

def test_summary_returns_counts():
    g = infer_ontology(_ecommerce_lineage())
    s = g.summary()
    assert "object_types" in s
    assert "links" in s
    assert "metrics" in s
    assert s["object_types"] == len(g.object_types)


def test_to_dict_has_all_keys():
    g = infer_ontology(_ecommerce_lineage())
    d = g.to_dict()
    assert "object_types" in d
    assert "links" in d
    assert "metrics" in d


def test_to_json_is_valid_json():
    import json
    g = infer_ontology(_ecommerce_lineage())
    j = g.to_json()
    parsed = json.loads(j)
    assert isinstance(parsed["object_types"], list)


def test_get_object_by_name():
    g = infer_ontology(_ecommerce_lineage())
    obj = g.get_object("Customer")
    if obj:
        assert obj.name == "Customer"


def test_links_from():
    g = infer_ontology(_ecommerce_lineage())
    for o in g.object_types:
        from_links = g.links_from(o.name)
        assert all(l.from_type == o.name for l in from_links)


def test_repr_contains_counts():
    g = infer_ontology(_ecommerce_lineage())
    r = repr(g)
    assert "OntologyGraph(" in r


# ── Empty graph ───────────────────────────────────────────────────────────────

def test_empty_lineage_returns_empty_ontology():
    g = infer_ontology({"tables": {}, "table_edges": [], "column_edges": []})
    assert g.object_types == []
    assert g.links == []
    assert g.metrics == []


# ── Naming-only link inference (no column edges) ──────────────────────────────

def test_naming_fallback_infers_links():
    lineage = {
        "tables": {
            "cat.raw.orders":    {"columns": [_col("id"), _col("customer_id")]},
            "cat.raw.customers": {"columns": [_col("id"), _col("name")]},
        },
        "table_edges": [],
        "column_edges": [],  # no column lineage → fallback to naming
    }
    g = infer_ontology(lineage, min_confidence=0.0)
    link_pairs = {(l.from_type, l.to_type) for l in g.links}
    assert any("Customer" in str(pair) for pair in link_pairs)
