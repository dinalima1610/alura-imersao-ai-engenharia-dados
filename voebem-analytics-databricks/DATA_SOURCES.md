# 🗂️ Fontes de dados

Este repositório **não redistribui** os arquivos da ANAC (≈ 138 MB para 12 meses de VRA mais cadastros). Eles podem ser baixados do portal oficial (veja nas informações a seguir).

| Conjunto | Conteúdo | Origem |
|---|---|---|
| VRA — Voo Regular Ativo | Um arquivo CSV por mês (ago/2025 a jul/2026 neste estudo) | <https://sistemas.anac.gov.br/dadosabertos/> → *Voos e operações aéreas / Voo Regular Ativo (VRA)* |
| Aeródromos públicos | Cadastro de aeródromos | *Aerodromos / Aeródromos Públicos / Lista de aeródromos públicos* |
| Empresas aéreas nacionais | Cadastro de operadores | *Operador Aéreo / Empresas Aereas Nacionais* |
| Empresas aéreas estrangeiras | Cadastro de operadores | *Operador Aéreo / Empresas Aereas Estrangeiras* |

## 🔎 Cuidados conhecidos com a fonte

Observados no material-base da turma e úteis para quem for reproduzir:

- O mês no **nome do arquivo** não tem zero à esquerda (`VRA_20258.csv`), mas a **pasta** tem (`08 - Agosto`).
- A URL contém espaços e acentos e precisa de *percent-encoding*.
- A primeira linha do CSV de VRA **não é o cabeçalho** (traz `Atualizado em: <data>`).
- O portal mantém um repositório antigo de VRA (congelado em 2024, menos colunas); use o de `sistemas.anac.gov.br`.
- Na pasta de operadores nacionais existe uma cópia grande e corrompida do cadastro; use a da subpasta *Empresas Aereas Nacionais*.

## 📄 Termos de uso

Consulte os termos de uso e a licença de cada conjunto de dados no portal de dados abertos da ANAC e em dados.gov.br antes de redistribuir qualquer arquivo. Ao publicar resultados derivados, cite a ANAC como fonte e informe a data de coleta.

Script de download: [`scripts/baixar_dados_anac.py`](scripts/baixar_dados_anac.py).
