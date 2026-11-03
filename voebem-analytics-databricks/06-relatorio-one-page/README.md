# 📊 06 · Relatório One Page — exploração complementar

Por iniciativa própria, quis melhorar a forma de apresentar os resultados entregues pelo Genie em um HTML One Page. Esta atividade foi além do escopo da imersão.

- [Abrir o relatório final](https://dinalima1610.github.io/alura-imersao-ai-engenharia-dados/voebem-analytics-databricks/06-relatorio-one-page/relatorio/index.html): baixe o HTML e abra no navegador.
E:\workspace\alura-imersao-ai-engenharia-dados\voebem-analytics-databricks\06-relatorio-one-page\relatorio\index.html
- [Entender a construção e os ajustes](docs/construcao-e-ajustes.md).
- [Consultar o prompt de apresentação](prompts/prompt-one-page.txt).

## 📁 Organização

| Local | Finalidade |
|---|---|
| `relatorio/index.html` | Única demonstração final publicada nesta etapa |
| `entradas/execucao-03/` | PDF, Response, PNGs, CSVs e prompts da análise que sustentam a demonstração |
| `prompts/` | Prompt utilizado para solicitar o One Page |
| `referencia-visual/` | Um exemplo de aparência, sem representar outra execução analítica |
| `docs/` | Processo de construção, dificuldades e ajustes |
| `gerar_relatorio_onepage.py` | Gerador do HTML autocontido |
| `qa_relatorio.py` | Utilitário opcional de inspeção visual |

## ⚙️ Gerar o relatório

Com Python disponível, execute a partir da raiz do repositório:

```bash
cd 06-relatorio-one-page
python -m pip install -r ../requirements.txt
python gerar_relatorio_onepage.py entradas/execucao-03 -o saida/relatorio.html --notes notas_consistencia.json
```

O gerador cria a pasta de saída. Abra `saida/relatorio.html` no navegador. Também são gravados `*_inferencias.json` e `*_avisos.log`.

As entradas da execução 03 são a referência de reprodução deste gerador: 15 fontes, 7 gráficos e 3 tabelas provenientes de figuras. A execução 04 está no item 05 para apresentar o trabalho com o Genie e não substitui estas entradas.

## 🧪 Inspeção visual opcional

Na mesma pasta:

```bash
python -m playwright install chromium
python qa_relatorio.py saida/relatorio.html saida/qa
```

O utilitário salva capturas e imprime medições de layout em três larguras de tela. Os resultados precisam ser conferidos: o script não emite aprovação automática nem calcula a cobertura completa do texto do PDF.

## 📌 Limitações

O gerador depende do formato do PDF e da estrutura do Response da execução 03, dos gráficos originais e de suas fontes SQL. Outras entradas podem exigir adaptação. As observações de `notas_consistencia.json` pertencem à execução 03 e precisam ser revistas para outros dados ou períodos. A geração do HTML não exige navegador; a inspeção visual com Playwright exige Chromium instalado.
