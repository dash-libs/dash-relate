# Databricks notebook source
# MAGIC %md
# MAGIC # dash-relate — Ontology and Lineage
# MAGIC
# MAGIC Define entity relationships and lineage for AI/LLM consumption.
# MAGIC
# MAGIC **Install and launch:**

# COMMAND ----------

# MAGIC %pip install dash-relate

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import dashrelate
dashrelate.launch()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Python API (optional — for automation)
# MAGIC
# MAGIC ```python
# MAGIC import dashrelate
# MAGIC # See docs/api/ for full API reference
# MAGIC ```
