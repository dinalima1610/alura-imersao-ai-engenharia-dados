# 🥉 02 · Bronze

Validação da camada Bronze (ingestão fiel dos CSVs da ANAC): contagens, esquema e amostras.

- [notebooks/](notebooks/) — duas versões do mesmo notebook: [SQL](notebooks/bronze_validacao_sql.py) e [PySpark](notebooks/bronze_validacao_pyspark.py), em formato de notebook Databricks (.py). Foram escritos com o Genie Code e conferidos manualmente.
- [relatorios/](relatorios/) — relatórios HTML de uma página gerados a partir dos notebooks (primeira versão do conceito *One Page* que evoluiu para o [gerador](../06-relatorio-one-page/)).

## 📊 Relatórios e versões

Os HTMLs apresentam os resultados registrados nos notebooks. Para começar, consulte os dois relatórios principais:

| Arquivo | Finalidade | Situação |
|---|---|---|
| [Validação PySpark](relatorios/relatorio-notebook-bronze-validacao-pyspark.html) | Contagens, esquemas, amostras e métricas registradas | Apresentação principal de PySpark |
| [Validação SQL](relatorios/relatorio-notebook-bronze-validacao-sql.html) | Consultas SQL, contagens, esquemas, amostras e métricas registradas | Apresentação principal de SQL |
| [Apresentação PySpark](relatorios/consulta-databricks-bronze-validacao-pyspark.html) | Versão alternativa de apresentação | Histórico |
| [Apresentação SQL](relatorios/consulta-databricks-bronze-validacao-sql.html) | Versão alternativa de apresentação | Histórico |
| [One Page PySpark original](relatorios/relatorio-notebook-bronze-validacao-one-page-historico.html) | Versão alternativa de apresentação | Histórico |
| [One Page PySpark corrigida](relatorios/relatorio-notebook-bronze-validacao-one-page.html) | Versão alternativa de apresentação; descrições das colunas de auditoria corrigidas conforme os esquemas exibidos |

As versões anteriores registram a evolução da apresentação dos resultados. Essa exploração contribuiu para o [gerador One Page](../06-relatorio-one-page/).

