"""Smoke tests for dashontology package (no Spark, no UC required)."""


def test_import():
    import dashontology
    assert hasattr(dashontology, "__version__")


def test_launch_importable():
    from dashontology import launch
    assert callable(launch)


def test_public_api_importable():
    from dashontology import (
        ObjectType, Link, Metric, Property, OntologyGraph,
        normalize_name, infer_cardinality, infer_ontology,
    )
    assert callable(infer_ontology)
    assert callable(normalize_name)
    assert callable(infer_cardinality)
