"""
Core data models for dash-ontology.

All classes are plain dataclasses — no Spark, no UC dependency.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Property:
    name: str            # "customer_id"
    column: str          # source column name (may differ after rename)
    data_type: str       # "bigint", "string", etc.
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_pii: bool = False


@dataclass
class ObjectType:
    name: str                     # "Customer"
    source_table: str             # "cat.silver.customers"
    properties: list[Property]
    role: str                     # entity | fact | junction | aggregation
    confidence: float             # 0.0 – 1.0
    description: str = ""


@dataclass
class Link:
    name: str                     # "Customer_Order"
    from_type: str                # "Customer"
    to_type: str                  # "Order"
    cardinality: str              # "1:1" | "1:N" | "N:M"
    from_column: str              # FK column on the *from* side
    to_column: str                # PK column on the *to* side
    via_table: Optional[str] = None   # junction table for N:M links
    confidence: float = 1.0
    description: str = ""


@dataclass
class Metric:
    name: str            # "monthly_revenue"
    source_table: str
    grain: str           # "month", "day", "customer", etc.
    description: str = ""


class OntologyGraph:
    """Container for an inferred or manually-defined ontology."""

    def __init__(
        self,
        object_types: list[ObjectType] = None,
        links: list[Link] = None,
        metrics: list[Metric] = None,
    ):
        self.object_types: list[ObjectType] = object_types or []
        self.links: list[Link] = links or []
        self.metrics: list[Metric] = metrics or []

    # ── Lookup ───────────────────────────────────────────────────────────────

    def get_object(self, name: str) -> Optional[ObjectType]:
        return next((o for o in self.object_types if o.name == name), None)

    def links_from(self, type_name: str) -> list[Link]:
        return [link for link in self.links if link.from_type == type_name]

    def links_to(self, type_name: str) -> list[Link]:
        return [link for link in self.links if link.to_type == type_name]

    # ── Summary ──────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        return {
            "object_types": len(self.object_types),
            "links": len(self.links),
            "metrics": len(self.metrics),
            "high_confidence_objects": sum(1 for o in self.object_types if o.confidence >= 0.8),
            "high_confidence_links": sum(1 for link in self.links if link.confidence >= 0.8),
        }

    # ── Export ───────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "object_types": [
                {
                    "name": o.name,
                    "source_table": o.source_table,
                    "role": o.role,
                    "confidence": round(o.confidence, 3),
                    "description": o.description,
                    "properties": [
                        {
                            "name": p.name,
                            "column": p.column,
                            "data_type": p.data_type,
                            "is_nullable": p.is_nullable,
                            "is_primary_key": p.is_primary_key,
                            "is_foreign_key": p.is_foreign_key,
                            "is_pii": p.is_pii,
                        }
                        for p in o.properties
                    ],
                }
                for o in self.object_types
            ],
            "links": [
                {
                    "name": link.name,
                    "from": link.from_type,
                    "to": link.to_type,
                    "cardinality": link.cardinality,
                    "from_column": link.from_column,
                    "to_column": link.to_column,
                    "via_table": link.via_table,
                    "confidence": round(link.confidence, 3),
                    "description": link.description,
                }
                for link in self.links
            ],
            "metrics": [
                {
                    "name": m.name,
                    "source_table": m.source_table,
                    "grain": m.grain,
                    "description": m.description,
                }
                for m in self.metrics
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def __repr__(self) -> str:
        s = self.summary()
        return (
            f"OntologyGraph({s['object_types']} objects, "
            f"{s['links']} links, "
            f"{s['metrics']} metrics)"
        )
