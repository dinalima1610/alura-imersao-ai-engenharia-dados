# ✈️ VoeBem Analytics — estudos de Databricks e IA com dados de aviação

Estudo para complementar conhecimentos em engenharia de dados realizado por **Diná Andrade Lima** a partir da Imersão IA Engenharia de Dados, da Alura. 

Meu foco profissional é desenvolvimento de software; esta experiência amplia meu conhecimento sobre pipelines, qualidade de dados e uso de IA na análise de informações.

O cenário de aviação utiliza dados da ANAC para explorar pontualidade, atrasos e cancelamentos de voos. As atividades acompanham o percurso dos dados pelas camadas Bronze, Silver e Gold, até as consultas com Genie e a apresentação dos resultados.

## 🧭 Por onde começar

- [Notebooks de validação Bronze](02-bronze/notebooks/): arquivos Python no formato Databricks, incluindo células SQL.
- [Análise com o Genie](05-genie-agente/): prompt revisado, resposta e evidências da execução 04.
- [Exploração complementar One Page](06-relatorio-one-page/): relatório final baseado na execução 03 e documentação da sua construção.
- [Jornada de aprendizado](docs/jornada-de-aprendizado.md): percurso pelas atividades e explorações complementares.

## 📁 Estrutura

| Pasta | Conteúdo |
|---|---|
| `01-fundamentos/` | Contexto inicial do estudo |
| `02-bronze/` | Notebooks e relatórios de validação Bronze |
| `03-silver/` | Relatórios de comparação Bronze × Silver |
| `04-gold-qualidade/` | Relatórios de validação Gold |
| `05-genie-agente/` | Análise principal com o Genie: execução 04 |
| `06-relatorio-one-page/` | Exploração complementar: One Page, entradas, gerador e processo de construção |
| `scripts/` | Utilitário de download de dados |
| `docs/` | Arquitetura, jornada de aprendizado e materiais gerais de apoio |

## 🎯 Escopo e participação

O estudo foi desenvolvido acompanhando as atividades da imersão, com exercícios, validações e explorações adicionais. O código de referência para ingestão e transformação dos dados foi fornecido no contexto do curso e não está incluído neste repositório.

Aqui estão reunidos notebooks de validação, prompts, execuções do Genie, relatórios e documentação do percurso de aprendizado.

### 💡 Exploração complementar: relatório One Page

Por iniciativa própria, quis melhorar a forma de apresentar os resultados entregues pelo Genie, transformando sua saída em um relatório HTML do tipo One Page, mais organizado e fácil de consultar. Essa atividade foi além do escopo da imersão.

Durante esse processo, encontrei problemas na interpretação das informações e na composição do relatório. Os ajustes trouxeram aprendizados sobre redação, delimitação do período analisado, bases de cálculo, prioridade entre fontes e fidelidade dos gráficos. As dificuldades e os ajustes estão descritos no [processo de construção do One Page](06-relatorio-one-page/docs/construcao-e-ajustes.md).

## 📊 Relatórios e versões

A execução 04 apresenta o trabalho com o Genie. A exploração complementar One Page utiliza a execução 03, cujas entradas foram mantidas junto do gerador para reprodução.

São resultados com finalidades distintas: o [item 05](05-genie-agente/) reúne a análise com o Genie; o [item 06](06-relatorio-one-page/) reúne uma única demonstração HTML e explica como ela foi construída. Ao comparar números, observe período, filtros e bases de cálculo de cada análise.

## ⚙️ Como explorar

Os relatórios HTML podem ser baixados e abertos localmente no navegador.

Os notebooks de validação Bronze devem ser importados no Databricks e dependem da existência do catálogo e das tabelas utilizados nas atividades. A reprodução completa do pipeline depende também do projeto de referência disponibilizado no contexto da imersão, dos dados e da configuração do ambiente.

As instruções do gerador de relatórios estão em [06-relatorio-one-page](06-relatorio-one-page/README.md).

## 🤝 Créditos e uso de IA

Estudo realizado a partir da **Imersão IA Engenharia de Dados, da Alura**, utilizando dados da **ANAC** e a plataforma **Databricks**.

Genie e outras ferramentas de IA apoiaram as atividades e a elaboração dos relatórios. 

IA foi utilizada na revisão dos materiais, identificando discrepâncias e realizando correções, além de sugerir melhorias na organização e na apresentação dos resultados.
