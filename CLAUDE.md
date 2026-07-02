# CLAUDE.md — dash-ontology

Part of the **Dashlibs** suite. See ~/dashlibs for the full context.

## Purpose
Auto-infers a data ontology (object types, links, metrics) from lineage
graphs — no AI tokens required. `inference.py`=`infer_ontology()`,
`models.py`=`ObjectType`/`Link`/`Metric`/`Property`/`OntologyGraph`.

## Structure
- `/ui.py`         — ipywidgets UI, `launch()` entrypoint
- `/inference.py`  — core inference engine
- `/models.py`      — dataclasses for the ontology graph
- `/cardinality.py`, `/naming.py`, `/_classifier_bridge.py` — inference helpers
- `tests/`           — pytest, no Spark dependency for unit tests

## Key Design Rules
- Never import Spark at module level — always inside functions
- UI calls core classes; never contains business logic
- `launch()` is always the public entrypoint for business users

## CI
- `ci.yml`    — PR gate: lint → test → build
- `daily.yml` — 06:00 UTC: tests + .health/log.txt commit
- `release.yml`— Monday 09:00 UTC: patch bump + GitHub release
