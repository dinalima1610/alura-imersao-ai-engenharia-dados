# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Título
# MAGIC %md
# MAGIC # Validação da camada Bronze — leitura apenas
# MAGIC
# MAGIC Script de validação pós-ingestão das cinco tabelas da camada Bronze do pipeline
# MAGIC `voebem.bronze`. Apenas operações de leitura: contagem de registros, esquema de
# MAGIC colunas e amostra dos primeiros 10 registros de cada tabela.

# COMMAND ----------

# DBTITLE 1,Validação das tabelas Bronze
# =============================================================================
# Validação pós-ingestão da camada Bronze
# Apenas leitura: nada é inserido, atualizado, excluído ou criado.
# Para cada tabela, exibe:
#   1. Quantidade de registros
#   2. Colunas e tipos de dados (esquema)
#   3. Até 10 primeiros registros
# =============================================================================

# Lista das cinco tabelas da camada Bronze a validar
TABELAS_BRONZE = [
    "voebem.bronze.aerodromos",
    "voebem.bronze.codigos_operacao",
    "voebem.bronze.empresas_estrangeiras",
    "voebem.bronze.empresas_nacionais",
    "voebem.bronze.vra",
]

for tabela in TABELAS_BRONZE:
    print("=" * 70)
    print(f"TABELA: {tabela}")
    print("=" * 70)

    # Carrega a tabela como DataFrame (somente leitura)
    df = spark.table(tabela)

    # ---------------------------------------------------------------------
    # 1) Quantidade de registros
    # ---------------------------------------------------------------------
    total = df.count()
    print(f"\n[1] Total de registros: {total:,}\n")

    # ---------------------------------------------------------------------
    # 2) Colunas e tipos de dados
    # ---------------------------------------------------------------------
    print("[2] Colunas e tipos de dados:")
    for campo in df.schema:
        print(f"    {campo.name:<30s} -> {campo.dataType.simpleString()}")
    print()

    # ---------------------------------------------------------------------
    # 3) Primeiros registros (até 10)
    # ---------------------------------------------------------------------
    print("[3] Primeiros registros (máximo 10):")
    df.show(10, truncate=False)
    print()
