# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Validação da Camada Bronze
# MAGIC
# MAGIC Consultas **somente leitura** que validam a ingestão das cinco tabelas da camada Bronze:
# MAGIC `aerodromos`, `codigos_operacao`, `empresas_estrangeiras`, `empresas_nacionais` e `vra`.
# MAGIC
# MAGIC Três verificações por tabela:
# MAGIC 1. **Contagem de registros** — `COUNT(*)` em cada tabela.
# MAGIC 2. **Esquema** — colunas, tipos de dados e propriedades via `information_schema`.
# MAGIC 3. **Amostra** — até 10 primeiros registros via `SELECT * LIMIT 10`.
# MAGIC
# MAGIC Nenhum dado é inserido, atualizado ou excluído.

# COMMAND ----------

# DBTITLE 1,Verificação 1 — Contagem
# MAGIC %md
# MAGIC ## 1. Contagem de registros
# MAGIC
# MAGIC Verifica se cada tabela tem dados e qual o volume total ingerido.
# MAGIC Consulta única com `UNION ALL` sobre as cinco tabelas.

# COMMAND ----------

# DBTITLE 1,Contagem de linhas por tabela
# MAGIC %sql
# MAGIC -- Validação 1: total de registros em cada tabela da Bronze
# MAGIC -- Retorna o nome da tabela e sua contagem de linhas.
# MAGIC SELECT 'aerodromos'            AS tabela, COUNT(*) AS total_linhas FROM voebem.bronze.aerodromos
# MAGIC UNION ALL
# MAGIC SELECT 'codigos_operacao'       AS tabela, COUNT(*) AS total_linhas FROM voebem.bronze.codigos_operacao
# MAGIC UNION ALL
# MAGIC SELECT 'empresas_estrangeiras'  AS tabela, COUNT(*) AS total_linhas FROM voebem.bronze.empresas_estrangeiras
# MAGIC UNION ALL
# MAGIC SELECT 'empresas_nacionais'     AS tabela, COUNT(*) AS total_linhas FROM voebem.bronze.empresas_nacionais
# MAGIC UNION ALL
# MAGIC SELECT 'vra'                    AS tabela, COUNT(*) AS total_linhas FROM voebem.bronze.vra
# MAGIC ORDER BY tabela

# COMMAND ----------

# DBTITLE 1,Verificação 2 — Esquema
# MAGIC %md
# MAGIC ## 2. Esquema: colunas, tipos e propriedades
# MAGIC
# MAGIC Lista nome da coluna, tipo de dado, nulabilidade e comentário de cada tabela,
# MAGIC via `information_schema.columns`.

# COMMAND ----------

# DBTITLE 1,Esquema das tabelas Bronze
# MAGIC %sql
# MAGIC -- Validação 2: esquema completo das cinco tabelas da Bronze
# MAGIC -- Retorna tabela, coluna, tipo de dado, se aceita nulo e comentário.
# MAGIC SELECT
# MAGIC     table_name   AS tabela,
# MAGIC     column_name  AS coluna,
# MAGIC     data_type    AS tipo,
# MAGIC     is_nullable  AS permite_nulo,
# MAGIC     comment
# MAGIC FROM voebem.information_schema.columns
# MAGIC WHERE table_schema = 'bronze'
# MAGIC   AND table_name IN (
# MAGIC       'aerodromos',
# MAGIC       'codigos_operacao',
# MAGIC       'empresas_estrangeiras',
# MAGIC       'empresas_nacionais',
# MAGIC       'vra'
# MAGIC   )
# MAGIC ORDER BY table_name, ordinal_position

# COMMAND ----------

# DBTITLE 1,Verificação 3 — Amostra
# MAGIC %md
# MAGIC ## 3. Amostra de dados (até 10 registros)
# MAGIC
# MAGIC Para cada tabela, `SELECT * LIMIT 10` mostra os primeiros registros armazenados,
# MAGIC permitindo inspecionar o conteúdo real sem modificar a tabela.

# COMMAND ----------

# DBTITLE 1,Amostra — aerodromos
# MAGIC %sql
# MAGIC -- Validação 3a: amostra de voebem.bronze.aerodromos
# MAGIC SELECT * FROM voebem.bronze.aerodromos LIMIT 10

# COMMAND ----------

# DBTITLE 1,Amostra — codigos_operacao
# MAGIC %sql
# MAGIC -- Validação 3b: amostra de voebem.bronze.codigos_operacao
# MAGIC SELECT * FROM voebem.bronze.codigos_operacao LIMIT 10

# COMMAND ----------

# DBTITLE 1,Amostra — empresas_estrangeiras
# MAGIC %sql
# MAGIC -- Validação 3c: amostra de voebem.bronze.empresas_estrangeiras
# MAGIC SELECT * FROM voebem.bronze.empresas_estrangeiras LIMIT 10

# COMMAND ----------

# DBTITLE 1,Amostra — empresas_nacionais
# MAGIC %sql
# MAGIC -- Validação 3d: amostra de voebem.bronze.empresas_nacionais
# MAGIC SELECT * FROM voebem.bronze.empresas_nacionais LIMIT 10

# COMMAND ----------

# DBTITLE 1,Amostra — vra
# MAGIC %sql
# MAGIC -- Validação 3e: amostra de voebem.bronze.vra
# MAGIC SELECT * FROM voebem.bronze.vra LIMIT 10