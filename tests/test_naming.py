"""Tests for table name → ObjectType name normalization."""
import pytest
from dashontology.naming import normalize_name, singularize, to_camel_case, strip_prefix


# ── strip_prefix ─────────────────────────────────────────────────────────────

def test_strip_dim():
    assert strip_prefix("dim_customer") == "customer"

def test_strip_fact():
    assert strip_prefix("fact_order_items") == "order_items"

def test_strip_stg():
    assert strip_prefix("stg_raw_events") == "raw_events"

def test_strip_bronze():
    assert strip_prefix("bronze_transactions") == "transactions"

def test_no_prefix_unchanged():
    assert strip_prefix("customers") == "customers"

def test_strip_longest_prefix_first():
    # "staging_" should be matched before "stg_"
    assert strip_prefix("staging_orders") == "orders"


# ── singularize ──────────────────────────────────────────────────────────────

def test_singularize_plain_s():
    assert singularize("customers") == "customer"

def test_singularize_ies():
    assert singularize("categories") == "category"

def test_singularize_irregular_people():
    assert singularize("people") == "person"

def test_singularize_invariant_status():
    assert singularize("statuses") == "status"

def test_singularize_short_word_unchanged():
    assert singularize("log") == "log"

def test_singularize_already_singular():
    assert singularize("order") == "order"

def test_singularize_ses():
    assert singularize("addresses") == "address"

def test_singularize_ches():
    assert singularize("batches") == "batch"


# ── to_camel_case ────────────────────────────────────────────────────────────

def test_camel_simple():
    assert to_camel_case("customer") == "Customer"

def test_camel_multi_word():
    assert to_camel_case("order_line_item") == "OrderLineItem"

def test_camel_already_clean():
    assert to_camel_case("product") == "Product"

def test_camel_strips_empty_parts():
    assert to_camel_case("_leading") == "Leading"


# ── normalize_name ───────────────────────────────────────────────────────────

def test_normalize_dim_customer():
    assert normalize_name("cat.silver.dim_customer") == "Customer"

def test_normalize_fact_order_items():
    assert normalize_name("main.gold.fact_order_items") == "OrderItem"

def test_normalize_stg_raw_events():
    result = normalize_name("stg_raw_events")
    assert result == "RawEvent"

def test_normalize_plain_customers():
    assert normalize_name("customers") == "Customer"

def test_normalize_monthly_revenue_agg():
    result = normalize_name("monthly_revenue_agg")
    # Strips no standard prefix, CamelCases with singularize on last part
    assert "Revenue" in result or "Agg" in result

def test_normalize_glossary_override():
    glossary = {"raw_cust": "Customer"}
    assert normalize_name("raw_cust", glossary=glossary) == "Customer"

def test_normalize_glossary_full_name_override():
    glossary = {"cat.raw.tbl_ord": "Order"}
    assert normalize_name("cat.raw.tbl_ord", glossary=glossary) == "Order"

def test_normalize_no_schema():
    assert normalize_name("products") == "Product"

def test_normalize_preserves_case_from_camel():
    result = normalize_name("dim_product_category")
    assert result == "ProductCategory"
