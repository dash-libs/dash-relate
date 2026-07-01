# Databricks notebook source
# MAGIC %md
# MAGIC # dash-ontology — Ontology and Lineage
# MAGIC
# MAGIC Define entity relationships and lineage for AI/LLM consumption.
# MAGIC
# MAGIC **Install and launch:**

# COMMAND ----------

# MAGIC %pip install dash-ontology

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import dashontology
dashontology.launch()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Python API (optional — for automation)
# MAGIC
# MAGIC ```python
# MAGIC import dashontology
# MAGIC # See docs/api/ for full API reference
# MAGIC ```
