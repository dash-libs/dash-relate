"""DashOntology interactive UI for Databricks notebooks."""
from __future__ import annotations

_LIBRARY = "dashontology"


def env_setup() -> None:
    """Open the environment setup panel — where should dashontology
    read/write its configs? Defaults to the notebook's current working
    directory if never called."""
    try:
        import dashui
        from IPython.display import display
    except ImportError:
        raise RuntimeError("ipywidgets required. Run: %pip install ipywidgets") from None

    display(dashui.card([
        dashui.header("DashOntology — Environment Setup", library=_LIBRARY),
        dashui.env_setup_panel(_LIBRARY).widget,
    ]))


def _ontology_html(ontology_dict: dict) -> str:
    """Render an ontology graph as a simple HTML entity-relationship diagram."""
    objects = ontology_dict.get("object_types", [])
    links = ontology_dict.get("links", [])
    metrics = ontology_dict.get("metrics", [])

    role_colors = {
        "entity":      "#2563eb",
        "fact":        "#16a34a",
        "junction":    "#7c3aed",
        "aggregation": "#d97706",
        "unknown":     "#9ca3af",
    }

    def _card(obj: dict) -> str:
        color = role_colors.get(obj.get("role", "unknown"), "#9ca3af")
        conf = obj.get("confidence", 0)
        props = obj.get("properties", [])
        pk = next((p["name"] for p in props if p.get("is_primary_key")), "—")
        fks = [p["name"] for p in props if p.get("is_foreign_key")]
        piis = [p["name"] for p in props if p.get("is_pii")]
        return (
            f"<div style='border:2px solid {color};border-radius:8px;padding:10px 14px;"
            f"margin:6px;min-width:160px;background:#fafafa;display:inline-block;vertical-align:top'>"
            f"<div style='color:{color};font-weight:700;font-size:13px'>{obj['name']}</div>"
            f"<div style='font-size:10px;color:#6b7280;margin-bottom:4px'>"
            f"{obj.get('role','?')} · {conf:.0%} confidence</div>"
            f"<div style='font-size:11px;color:#374151'>"
            f"PK: <b>{pk}</b><br/>"
            + (f"FK: {', '.join(fks)}<br/>" if fks else "")
            + (f"<span style='color:#dc2626'>PII: {', '.join(piis)}</span>" if piis else "")
            + "</div></div>"
        )

    def _link_row(lnk: dict) -> str:
        card_map = {"1:1": "─────", "1:N": "──<──", "N:M": "──<─>──"}
        arrow = card_map.get(lnk.get("cardinality", "1:N"), "→")
        conf = lnk.get("confidence", 0)
        return (
            f"<tr><td style='padding:2px 8px;font-family:monospace;font-size:12px'>"
            f"<b>{lnk['from']}</b> {arrow} <b>{lnk['to']}</b></td>"
            f"<td style='padding:2px 8px;font-size:11px;color:#6b7280'>"
            f"{lnk.get('cardinality','?')} via {lnk.get('from_column','?')}</td>"
            f"<td style='padding:2px 8px;font-size:11px;color:#6b7280'>{conf:.0%}</td></tr>"
        )

    obj_html = "".join(_card(o) for o in objects)
    link_rows = "".join(_link_row(link) for link in links)
    metric_names = ", ".join(m["name"] for m in metrics) if metrics else "none"

    return f"""
    <div style='font-family:monospace;padding:12px;background:#fff;
                border-radius:8px;border:1px solid #e5e7eb'>
      <div style='font-weight:600;font-size:13px;margin-bottom:8px;color:#374151'>
        Object Types ({len(objects)})
      </div>
      <div style='margin-bottom:16px'>{obj_html}</div>

      <div style='font-weight:600;font-size:13px;margin-bottom:6px;color:#374151'>
        Links ({len(links)})
      </div>
      <table style='border-collapse:collapse;font-size:12px;margin-bottom:16px'>
        <tr style='background:#f3f4f6'>
          <th style='padding:4px 8px;text-align:left'>Relationship</th>
          <th style='padding:4px 8px;text-align:left'>Cardinality</th>
          <th style='padding:4px 8px;text-align:left'>Confidence</th>
        </tr>
        {link_rows}
      </table>

      <div style='font-size:11px;color:#6b7280'>Metrics: {metric_names}</div>
    </div>
    """


def launch():
    try:
        import ipywidgets as w
        from IPython.display import display
    except ImportError:
        raise RuntimeError("ipywidgets required. Run: %pip install ipywidgets")

    import dashui

    saved = dashui.load_config(_LIBRARY, defaults={"min_confidence": 0.6, "include_staging": False, "glossary": ""})

    # ── From lineage graph dict (paste JSON) ──────────────────────────────────
    json_input = w.Textarea(
        description="Lineage JSON:",
        placeholder='Paste the output of dashgov.LineageGraph.to_json() here ...',
        layout=w.Layout(width="100%", height="150px"),
    )
    min_conf_slider = w.FloatSlider(
        description="Min confidence:", value=saved["min_confidence"], min=0.0, max=1.0, step=0.05,
        readout_format=".0%",
    )
    include_staging_cb = w.Checkbox(value=saved["include_staging"], description="Include staging tables")
    glossary_input = w.Textarea(
        description="Glossary (JSON):",
        placeholder='{"raw_cust": "Customer", "tbl_ord": "Order"}',
        layout=w.Layout(width="100%", height="60px"),
        value=saved["glossary"],
    )
    infer_btn = dashui.action_button("Infer Ontology", style="success")
    infer_output = dashui.output_panel()
    ontology_viz = w.HTML(value="")
    json_export = w.Textarea(
        description="Export (JSON):",
        layout=w.Layout(width="100%", height="120px"),
        disabled=True,
    )

    _last_ontology: list = [None]

    def on_infer(b):
        with infer_output:
            infer_output.clear_output()
            ontology_viz.value = ""
            json_export.value = ""
            raw = json_input.value.strip()
            if not raw:
                print("Paste a lineage JSON above")
                return
            try:
                dashui.save_config(_LIBRARY, {
                    "min_confidence": min_conf_slider.value,
                    "include_staging": include_staging_cb.value,
                    "glossary": glossary_input.value.strip(),
                })
            except Exception:
                pass  # persistence is a convenience, never block the actual operation on it
            try:
                import json as _json
                from dashontology.inference import infer_ontology
                lineage = _json.loads(raw)
                glossary = {}
                if glossary_input.value.strip():
                    glossary = _json.loads(glossary_input.value.strip())
                ontology = infer_ontology(
                    lineage_graph=lineage,
                    glossary=glossary or None,
                    min_confidence=min_conf_slider.value,
                    include_staging=include_staging_cb.value,
                )
                _last_ontology[0] = ontology
                s = ontology.summary()
                print(f"Object types : {s['object_types']} ({s['high_confidence_objects']} high-confidence)")
                print(f"Links        : {s['links']} ({s['high_confidence_links']} high-confidence)")
                print(f"Metrics      : {s['metrics']}")
                ontology_viz.value = _ontology_html(ontology.to_dict())
                json_export.value = ontology.to_json()
            except Exception as e:
                print(f"Error: {e}")

    infer_btn.on_click(on_infer)

    env_accordion = w.Accordion(children=[dashui.env_setup_panel(_LIBRARY).widget])
    env_accordion.set_title(0, "Environment setup")
    env_accordion.selected_index = None

    ui = dashui.card([
        dashui.header("DashOntology — Auto-Inferred Data Ontology", library="dashontology"),
        env_accordion,

        dashui.section("Step 1: Paste lineage graph"),
        dashui.html(
            "<div style='font-size:12px;color:#666;margin-bottom:4px'>"
            "Run <code>dashgov.build_lineage_graph(...).to_json()</code> in another cell "
            "and paste the result here. Or use the UC fetch in DashGov.</div>"
        ),
        json_input,

        dashui.section("Step 2: Configure inference"),
        w.HBox([min_conf_slider, include_staging_cb]),
        glossary_input,
        infer_btn,
        infer_output,

        dashui.section("Inferred ontology"),
        ontology_viz,

        dashui.section("JSON export"),
        json_export,
    ])
    display(ui)
