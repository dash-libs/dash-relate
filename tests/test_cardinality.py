"""Tests for cardinality inference heuristics."""
import pytest
from dashontology.cardinality import infer_cardinality, infer_cardinality_from_ratio, cardinality_label


# ── infer_cardinality ────────────────────────────────────────────────────────

def test_one_to_one():
    # Both sides fully unique
    card, conf = infer_cardinality(
        from_unique=1000, from_total=1000,
        to_unique=1000, to_total=1000,
    )
    assert card == "1:1"
    assert conf >= 0.80


def test_one_to_many():
    # FK side has duplicates (many orders per customer)
    card, conf = infer_cardinality(
        from_unique=200, from_total=1000,  # 200 unique customers in 1000 orders
        to_unique=200, to_total=200,       # 200 customers
    )
    assert card == "1:N"
    assert conf >= 0.65


def test_many_to_many_non_unique_pk():
    card, conf = infer_cardinality(
        from_unique=500, from_total=1000,
        to_unique=400, to_total=500,   # PK side not unique → N:M
    )
    assert card == "N:M"
    assert conf >= 0.50


def test_zero_rows_returns_default():
    card, conf = infer_cardinality(
        from_unique=0, from_total=0,
        to_unique=100, to_total=100,
    )
    assert card == "1:N"   # safe default


def test_nearly_unique_fk_is_one_to_one():
    # 98 % unique FK → still 1:1 if above threshold
    card, _ = infer_cardinality(
        from_unique=980, from_total=1000,
        to_unique=1000, to_total=1000,
        one_to_one_threshold=0.95,
    )
    assert card == "1:1"


def test_slightly_below_threshold_is_one_to_n():
    card, _ = infer_cardinality(
        from_unique=900, from_total=1000,
        to_unique=1000, to_total=1000,
        one_to_one_threshold=0.95,
    )
    assert card == "1:N"


def test_confidence_in_valid_range():
    for fu, ft, tu, tt in [
        (100, 100, 100, 100),
        (50, 100, 100, 100),
        (50, 100, 80, 100),
    ]:
        _, conf = infer_cardinality(fu, ft, tu, tt)
        assert 0.0 <= conf <= 1.0


# ── infer_cardinality_from_ratio ─────────────────────────────────────────────

def test_ratio_one_to_one():
    card, conf = infer_cardinality_from_ratio(1.0)
    assert card == "1:1"
    assert conf >= 0.75


def test_ratio_one_to_many():
    card, _ = infer_cardinality_from_ratio(5.0)
    assert card == "1:N"


def test_ratio_borderline():
    card, conf = infer_cardinality_from_ratio(1.3)
    assert card == "1:N"
    assert conf < 0.75   # borderline, lower confidence


def test_ratio_high_multiplicity():
    card, conf = infer_cardinality_from_ratio(20.0)
    assert card == "1:N"
    assert conf >= 0.70


# ── cardinality_label ─────────────────────────────────────────────────────────

def test_label_1_1():
    assert cardinality_label("1:1") == "one-to-one"

def test_label_1_n():
    assert cardinality_label("1:N") == "one-to-many"

def test_label_n_m():
    assert cardinality_label("N:M") == "many-to-many"

def test_label_unknown():
    assert cardinality_label("???") == "???"
