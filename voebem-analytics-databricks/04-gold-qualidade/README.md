# 🥇 04 · Qualidade de dados e Gold

Pipeline de qualidade da Silver (marcado → auditado → quarentena), modelagem da Gold em *One Big Table* e linhagem.

- [relatorios/](relatorios/) — validação da Gold em SQL e PySpark (inclui versões geradas pelo Genie).
- Capturas de tela do pipeline e da linhagem estão em [`docs/img/`](../docs/img/) (dados pessoais removidos).

## 📊 Relatórios e versões

Os relatórios SQL e PySpark verificam a mesma pergunta de negócio por abordagens diferentes.

| Arquivo | Finalidade | Situação |
|---|---|---|
| [One Page SQL](https://dinalima1610.github.io/alura-imersao-ai-engenharia-dados/voebem-analytics-databricks/04-gold-qualidade/relatorios/relatorio-notebook-gold-validacao-sql.html) | Versão alternativa de apresentação da consulta em formato One Page | Histórico |
| [One Page PySpark](https://dinalima1610.github.io/alura-imersao-ai-engenharia-dados/voebem-analytics-databricks/04-gold-qualidade/relatorios/relatorio-notebook-gold-validacao-pyspark.html) | Versão alternativa de apresentação da consulta em formato One Page | Histórico |
| [Validação Gold em SQL](https://dinalima1610.github.io/alura-imersao-ai-engenharia-dados/voebem-analytics-databricks/04-gold-qualidade/relatorios/consulta-databricks-gold-validacao-sql.html) | Validação por consulta SQL | Apresentação principal de SQL | Histórico |
| [Validação Gold em PySpark](https://dinalima1610.github.io/alura-imersao-ai-engenharia-dados/voebem-analytics-databricks/04-gold-qualidade/relatorios/consulta-databricks-gold-validacao-pyspark.html) | Validação pela DataFrame API | Apresentação principal de PySpark |  Histórico |
| [Apresentação SQL](https://dinalima1610.github.io/alura-imersao-ai-engenharia-dados/voebem-analytics-databricks/04-gold-qualidade/relatorios/relatorio-notebook-gold-validacao-sql-by-Genie-Agent.html) | Apresentação da consulta em formato One Page gerado pelo Genie Agent | Histórico |
| [Apresentação PySpark](https://dinalima1610.github.io/alura-imersao-ai-engenharia-dados/voebem-analytics-databricks/04-gold-qualidade/relatorios/relatorio-notebook-gold-validacao-pyspark-by-Genie-Agent.html) | Apresentação da consulta em formato One Page gerado pelo Genie Agent | Histórico |

Os notebooks de origem estão disponíveis apenas como relatório HTML.
