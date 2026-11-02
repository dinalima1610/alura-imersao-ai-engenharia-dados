# 🤖 05 · Agente Genie

Exploração de perguntas de negócio em linguagem natural sobre `voebem.gold.obt_voos`, no cenário de aviação da imersão.

## 🎯 Objetivo

Investigar pontualidade, atrasos, cancelamentos e recuperação de atrasos em voo, relacionando as respostas do Genie às consultas e aos resultados apresentados como fontes.

## 📊 Execução apresentada

A execução 04, com relatório datado de 06/10/2026, foi escolhida para apresentar esta etapa. Ela utiliza o prompt único revisado e inclui cancelamentos e as rotas com maiores atrasos.

| Arquivo | Conteúdo |
|---|---|
| [Prompt de análise](execucao-04/prompts/prompts.txt) | Instruções utilizadas nesta execução |
| [Relatório PDF](execucao-04/genie-saida/analise-completa-de-pontualidade-atrasos-e-cancelamentos-de-voos-no-brasil.pdf) | Resultado principal para consulta |
| [Response](execucao-04/genie-saida/response.txt) | Texto da resposta, consultas e resultados preservados |
| [Gráficos](execucao-04/genie-saida/) | Evidências visuais que acompanham a análise |

## 💡 Aprendizados

Os ajustes do prompt explicitaram o período analisado, o tratamento de meses parciais, as bases de cálculo e o cuidado com afirmações que os resultados não sustentavam. As respostas devem ser lidas junto das consultas e dos filtros utilizados; comparações descritivas não comprovam causalidade.

As validações em [SQL e PySpark da Gold](../04-gold-qualidade/) complementam o percurso de conferência dos resultados.

A melhoria da apresentação em HTML foi uma iniciativa posterior e está separada em [06 · Relatório One Page](../06-relatorio-one-page/). Essa demonstração utiliza as entradas da execução 03, preservadas naquela pasta para reprodução; não é uma conversão da execução 04.
