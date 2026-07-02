"""DashOntology — Auto-inferred data ontology from lineage graphs."""
from dashontology.models import ObjectType, Link, Metric, Property, OntologyGraph
from dashontology.naming import normalize_name, singularize, to_camel_case
from dashontology.cardinality import infer_cardinality, infer_cardinality_from_ratio
from dashontology.inference import infer_ontology
from dashontology.ui import launch

__version__ = "0.1.3"
__all__ = [
    "ObjectType", "Link", "Metric", "Property", "OntologyGraph",
    "normalize_name", "singularize", "to_camel_case",
    "infer_cardinality", "infer_cardinality_from_ratio",
    "infer_ontology",
    "launch",
]
