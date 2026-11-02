#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_relatorio_onepage.py
Gera o relatório HTML One Page (autocontido) a partir de:
  PDF  (conteúdo principal)  +  response.txt (SQL, resultados, Sources)
  CSV/PNG (figuras)          +  HTML de referência (padrão visual)
Nenhuma quantidade (fontes, gráficos, tabelas, seções, linhas, categorias) é fixa:
tudo é derivado dos arquivos de entrada.

Uso:  python gerar_relatorio_onepage.py PASTA_OU_ZIP [-o saida.html] [--notes notas.json]
"""
import re, os, sys, json, csv, glob, html, unicodedata, difflib, argparse, collections
import math, zipfile, tempfile, io

# ----------------------------------------------------------------------------
# Configuração editável (glossário e rótulos). Pode ser sobrescrita por --config
# ----------------------------------------------------------------------------
CONFIG = {
    # rótulos amigáveis para colunas SQL (usados em eixos e legendas)
    "glossario": {
        "pct_atrasados": "% de voos atrasados",
        "pct_pontuais": "% de voos pontuais",
        "pct_cancelados": "% de voos cancelados",
        "atraso_medio_min": "Atraso médio (min)",
        "recuperados_medio_min": "Minutos recuperados em voo (média)",
        "diferenca_pct_atrasados": "Diferença de % atrasados (internacional − doméstico)",
        "hora": "Hora do dia", "dia_semana": "Dia da semana", "mes": "Mês",
        "escopo_voo": "Escopo do voo", "nome_aeroporto_origem": "Aeroporto",
        "nome_companhia": "Companhia", "voos": "Voos",
    },
    # nomes de dias/escopos exibidos com acento
    "valores": {"terca": "terça", "sabado": "sábado", "Domestico": "Doméstico"},
    # rótulos em negrito que abrem caixas de destaque -> tipo de caixa
    "callouts": {
        "excecao": "attention", "ressalva": "attention", "atencao": "attention",
        "importante": "attention", "hipotese": "attention",
        "conclusao": "success", "resultado": "success", "destaque": "success",
        "leitura": "success", "implicacao": "success", "justificativa": "info",
        "observacao": "info", "criterio": "info", "filtros aplicados": "info",
        "padrao": "info", "denominador": "info", "exemplo": "info", "recomendacao": "success",
    },
    "nota_final": ("Fonte complementar: o Response gerado pelo Databricks Genie foi recuperado e utilizado "
                   "para fundamentar consultas SQL, métricas, resultados detalhados e a lista de fontes da análise. "
                   "Para evitar duplicidade ou contradições, o conteúdo final considera apenas a versão consolidada "
                   "revisada do Response."),
    "performance": ("Performance e métricas: os anexos trazem contagens, filtros, denominadores e resultados analíticos. "
                    "Não há no material tempo de execução, custo computacional, duração de consulta ou métrica técnica "
                    "de performance do Databricks/Genie; por isso nenhuma dessas métricas foi exibida."),
    "tema_storage_key": "onepage-report-theme",
}

WARN = []          # avisos de consistência/entrada (vão para o log)
def warn(msg):
    WARN.append(msg); print("AVISO:", msg, file=sys.stderr)

# ----------------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------------
def decode_name(n):
    return re.sub(r'#U([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), n)

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()

def esc(s): return html.escape(s, quote=True)

def fmt_int(n): return f"{int(round(n)):,}".replace(',', '.')
def fmt_dec(x, d=2):
    s = f"{x:,.{d}f}"
    return s.replace(',', '\0').replace('.', ',').replace('\0', '.')
def fmt_g(x):
    s = f"{x:g}"
    return s.replace('.', ',')

NUM_US = re.compile(r'^-?\d{1,3}(,\d{3})+(\.\d+)?$')   # 1,014,664 / 1,234.5
NUM_PLAIN = re.compile(r'^-?\d+(\.\d+)?$')               # 13.42 / 3104
def parse_num(s):
    s = (s or '').strip()
    if NUM_US.match(s): return float(s.replace(',', ''))
    if NUM_PLAIN.match(s): return float(s)
    return None

def slug(s):
    return re.sub(r'\s+', '-', norm(s))[:48] or 'sec'

def find_inputs(path):
    """Aceita pasta ou .zip. Devolve dict com caminhos."""
    tmp = None
    if os.path.isfile(path) and path.lower().endswith('.zip'):
        tmp = tempfile.mkdtemp(prefix='onepage_')
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                name = decode_name(info.filename)
                dest = os.path.join(tmp, os.path.basename(name))
                with z.open(info) as src, open(dest, 'wb') as out: out.write(src.read())
        path = tmp
    files = [os.path.join(path, f) for f in os.listdir(path)]
    by = lambda ext: sorted([f for f in files if f.lower().endswith(ext)])
    pdfs, txts, htmls = by('.pdf'), by('.txt'), by('.html')
    if not pdfs: raise SystemExit("PDF não encontrado")
    txt = next((f for f in txts if decode_name(os.path.basename(f)).lower() == 'response.txt'), None) or \
          next((f for f in txts if 'response' in decode_name(os.path.basename(f)).lower()), None) or \
          (max(txts, key=os.path.getsize) if txts else None)
    ref = next((f for f in htmls if re.search(r'exemplo|padr', decode_name(f).lower())), None) or \
          (max(htmls, key=os.path.getsize) if htmls else None)
    return dict(pdf=pdfs[0], txt=txt, ref=ref, csvs=by('.csv'), pngs=by('.png'), dir=path)

def vocab_from_text(t):
    return set(w.lower() for w in re.findall(r"[^\W_]+(?:-[^\W_]+)*", t, re.U))

# ----------------------------------------------------------------------------
# PDF -> elementos estruturados
# ----------------------------------------------------------------------------
def join_lines(parts, vocab):
    """Junta linhas de um mesmo bloco tratando hifenização de quebra de linha."""
    out = ''
    for ln in parts:
        ln = ln.strip()
        if not ln: continue
        if not out: out = ln; continue
        if re.search(r'[^\W\d_]-$', out) and re.match(r'[a-zà-ÿ]', ln):
            m = re.search(r'([^\W\d_]+)-$', out)
            left = m.group(1); mr = re.match(r'([^\W\d_]+)', ln); right = mr.group(1) if mr else ''
            if (left + right).lower() in vocab:
                out = out[:-1] + ln
            elif (left + '-' + right).lower() in vocab:
                out = out + ln
            else:
                out = out[:-1] + ln
        else:
            out = out + ' ' + ln
    return out

def runs_merge(runs):
    res = []
    for t, b in runs:
        if res and res[-1][1] == b: res[-1] = (res[-1][0] + t, b)
        else: res.append((t, b))
    return res

def join_runs(lines_runs, vocab):
    """lines_runs: lista de listas [(texto,bold)]; devolve runs unidos com dehifenização."""
    out = []
    for runs in lines_runs:
        runs = [(t, b) for t, b in runs if t != '']
        if not runs: continue
        if not out: out = list(runs); continue
        last_t, last_b = out[-1]
        first_t = runs[0][0]
        if re.search(r'[^\W\d_]-$', last_t) and re.match(r'[a-zà-ÿ]', first_t):
            full_left = ''.join(t for t, _ in out)
            m = re.search(r'([^\W\d_]+)-$', full_left)
            left = m.group(1); mr = re.match(r'([^\W\d_]+)', first_t); right = mr.group(1) if mr else ''
            if (left + right).lower() in vocab:      out[-1] = (last_t[:-1], last_b); out.extend(runs)
            elif (left + '-' + right).lower() in vocab: out.extend(runs)
            else: out[-1] = (last_t[:-1], last_b); out.extend(runs)
        else:
            out[-1] = (last_t + ' ', last_b); out.extend(runs)
    return runs_merge(out)

def plain_of(runs): return re.sub(r'\s+', ' ', ''.join(t for t, _ in runs)).strip()

def extract_table(page, t, vocab):
    """Extrai tabela usando o cabeçalho para delimitar colunas e as linhas (bbox) para as células."""
    rows = t.rows
    cols = [(c[0], c[2]) for c in rows[0].cells if c]
    out = []
    for r in rows:
        bb = r.bbox
        ws = page.within_bbox((bb[0] - 1, bb[1] - 1, bb[2] + 1, bb[3] + 1)).extract_words(x_tolerance=1.5)
        cells = []
        for x0, x1 in cols:
            cw = sorted([w for w in ws if x0 - 1 <= (w['x0'] + w['x1']) / 2 <= x1 + 1],
                        key=lambda w: (round(w['top']), w['x0']))
            lines = []
            for w in cw:
                if lines and abs(w['top'] - lines[-1][0]) < 3: lines[-1][1].append(w['text'])
                else: lines.append([w['top'], [w['text']]])
            cells.append(join_lines([' '.join(l[1]) for l in lines], vocab))
        out.append(cells)
    return out

def parse_pdf(path, vocab):
    import pdfplumber
    pdf = pdfplumber.open(path)
    items = []            # sequência de dicts
    n_images = 0
    cur = None            # bloco em construção
    pending_num = None
    def close():
        nonlocal cur
        if cur is not None: items.append(cur); cur = None
    for pno, page in enumerate(pdf.pages):
        tabs = page.find_tables()
        boxes = [t.bbox for t in tabs]
        def keep(o):
            if o['object_type'] != 'char': return True
            cx, cy = (o['x0'] + o['x1']) / 2, (o['top'] + o['bottom']) / 2
            return not any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b in boxes)
        fp = page.filter(keep)
        words = fp.extract_words(extra_attrs=['fontname', 'size'], x_tolerance=1.5, keep_blank_chars=False)
        # agrupa palavras em linhas
        words.sort(key=lambda w: (round(w['top']), w['x0']))
        lines = []
        for w in words:
            if lines and abs(w['top'] - lines[-1]['top']) < 3: lines[-1]['w'].append(w)
            else: lines.append({'top': w['top'], 'w': [w]})
        elems = []   # (top, kind, payload)
        for ln in lines:
            ws = sorted(ln['w'], key=lambda w: w['x0'])
            runs = []; prev = None
            for w in ws:
                bold = 'Bold' in w['fontname']
                gap = (w['x0'] - prev['x1']) if prev else 0
                txt = (' ' if prev is not None and gap > 1.0 else '') + w['text']
                runs.append((txt, bold)); prev = w
            runs = runs_merge(runs)
            size = max(w['size'] for w in ws)
            allbold = all(b for _, b in runs if _.strip())
            elems.append((ln['top'], 'line', dict(runs=runs, size=size, allbold=allbold, top=ln['top'], x0=ws[0]['x0'])))
        for t in tabs:
            elems.append((t.bbox[1], 'table', extract_table(page, t, vocab)))
        for im in page.images:
            elems.append((im['top'], 'img', None))
        elems.sort(key=lambda e: e[0])
        first_line_of_page = True
        for top, kind, pl in elems:
            if kind == 'img':
                close(); items.append({'k': 'img', 'idx': n_images, 'page': pno + 1}); n_images += 1; continue
            if kind == 'table':
                close()
                items.append({'k': 'table', 'rows': pl, 'page': pno + 1}); continue
            L = pl; text = plain_of(L['runs'])
            if not text: continue
            if L['size'] >= 13.8:
                close(); items.append({'k': 'title', 'text': text}); first_line_of_page = False; continue
            if L['size'] >= 12.5 and L['allbold']:
                close(); items.append({'k': 'h', 'text': text}); first_line_of_page = False; continue
            # corpo
            m_b = text.startswith('•')
            m_n = re.match(r'^(\d+)\.\s+(.*)$', text)
            m_n0 = re.match(r'^(\d+)\.$', text)
            if pending_num is not None and cur is not None and cur.get('k') == 'li_n' and not cur['lines']:
                cur['lines'].append(L['runs']); cur['last'] = top; pending_num = None; first_line_of_page = False; continue
            if m_b:
                close()
                body = runs_trim_marker(L['runs'], '•')
                cur = {'k': 'li_b', 'lines': [body], 'last': top, 'page': pno + 1}
            elif m_n0:
                close(); cur = {'k': 'li_n', 'num': int(m_n0.group(1)), 'lines': [], 'last': top, 'page': pno + 1}; pending_num = True
            elif m_n:
                close()
                cur = {'k': 'li_n', 'num': int(m_n.group(1)), 'lines': [runs_trim_marker(L['runs'], m_n.group(1) + '.')], 'last': top, 'page': pno + 1}
            elif L['allbold'] and len(text) <= 90 and (cur is None or (top - cur['last']) > 17.5 or text.endswith(':')):
                close(); items.append({'k': 'p', 'lines': [L['runs']], 'last': top, 'page': pno + 1}); cur = None   # rótulo em negrito isolado
            else:
                cont = cur is not None and cur['k'] in ('p', 'li_b', 'li_n') and \
                       (((top - cur['last']) <= 17.5 and cur['page'] == pno + 1) or
                        (first_line_of_page and cur['page'] != pno + 1 and re.match(r'[a-zà-ÿ]', text)))
                if cont:
                    cur['lines'].append(L['runs']); cur['last'] = top; cur['page'] = pno + 1
                else:
                    close(); cur = {'k': 'p', 'lines': [L['runs']], 'last': top, 'page': pno + 1}
            first_line_of_page = False
        # fim da página: não fecha (permite continuação por minúscula)
    close()
    # finaliza blocos: runs unidos
    out = []
    for it in items:
        if it['k'] in ('p', 'li_b', 'li_n'):
            it['runs'] = join_runs(it.pop('lines'), vocab)
            it['plain'] = plain_of(it['runs'])
            if not it['plain']: continue
        out.append(it)
    return out, n_images, len(pdf.pages)

def runs_trim_marker(runs, marker):
    runs = list(runs)
    t, b = runs[0]
    t = t.lstrip()
    if t.startswith(marker): t = t[len(marker):].lstrip()
    runs[0] = (t, b)
    return [(x, y) for x, y in runs if x != '']

def split_inline_bullets(runs):
    """Divide runs que contêm '•' no meio do texto (lista aninhada colapsada pelo PDF)."""
    full = ''.join(t for t, _ in runs)
    if '•' not in full: return [runs]
    parts, cur, curb = [], [], None
    for t, b in runs:
        segs = t.split('•')
        for i, sgm in enumerate(segs):
            if i > 0: parts.append(runs_merge(cur)); cur = []
            if sgm: cur.append((sgm, b))
    parts.append(runs_merge(cur))
    res = []
    for p in parts:
        if p:
            p[0] = (p[0][0].lstrip(), p[0][1]); p[-1] = (p[-1][0].rstrip(), p[-1][1])
            if plain_of(p): res.append(p)
    return res

def structure(items):
    """Transforma itens lineares em seções com listas agrupadas/aninhadas."""
    tl = []
    for i in items:                      # o título pode quebrar em mais de uma linha
        if i['k'] == 'title': tl.append(i['text'])
        elif tl: break
    title = ' '.join(tl)
    sections = []; cur = None; seen_numbered = False
    def new_section(text, level):
        m = re.match(r'^(\d+)\.\s+(.*)$', text)
        return {'title': m.group(2) if m else text, 'num': int(m.group(1)) if m else None,
                'raw_title': text, 'elems': []}
    last_list = None   # (tipo, lista) para agrupamento
    for it in items:
        k = it['k']
        if k == 'title': continue
        if k == 'h':
            text = it['text']
            if re.match(r'^\d+\.\d+', text): level = 3
            elif re.match(r'^\d+\.\s', text): level = 2
            else: level = 2 if (cur is None or not seen_numbered) else 3
            if level == 2:
                cur = new_section(text, 2); sections.append(cur)
                if cur['num'] is not None: seen_numbered = True
            else:
                if cur is None: cur = new_section('Introdução', 2); sections.append(cur)
                cur['elems'].append({'k': 'h3', 'text': text})
            last_list = None; continue
        if cur is None: cur = new_section('Introdução', 2); sections.append(cur)
        E = cur['elems']
        if k in ('li_b', 'li_n'):
            if k == 'li_b':
                subs = split_inline_bullets(it['runs'])
                li_items = [{'runs': s, 'plain': plain_of(s)} for s in subs]
                prev = E[-1] if E else None
                if prev and prev['k'] == 'ol' and prev['items'] and \
                   prev['items'][-1]['plain'].rstrip().endswith(':') and 'sub' not in prev['items'][-1]:
                    prev['items'][-1]['sub'] = li_items          # sub-lista aninhada
                elif prev and prev['k'] == 'ul':
                    prev['items'].extend(li_items)
                else:
                    E.append({'k': 'ul', 'items': li_items})
            else:
                prev = E[-1] if E else None
                item = {'runs': it['runs'], 'plain': it['plain'], 'num': it['num']}
                if prev and prev['k'] == 'ol' and (prev['items'][-1].get('num', 0) + 1 == it['num']):
                    prev['items'].append(item)
                else:
                    E.append({'k': 'ol', 'items': [item], 'start': it['num']})
            continue
        # qualquer outro elemento "sela" listas anteriores
        if E and E[-1]['k'] == 'ul': E[-1]['_sealed'] = True
        if k == 'p':
            full = plain_of(it['runs'])
            allbold = all(b for t, b in it['runs'] if t.strip())
            if allbold and len(full) <= 90 and '\n' not in full:
                E.append({'k': 'h4', 'text': full})
            else:
                E.append({'k': 'p', 'runs': it['runs'], 'plain': full})
        elif k == 'table': E.append({'k': 'table', 'rows': it['rows']})
        elif k == 'img': E.append({'k': 'img', 'idx': it['idx']})
    for s in sections:
        for e in s['elems']:
            for key in ('_last_page', '_sealed', 'closed_nest', 'open_after_nest'): e.pop(key, None)
    return title, sections
# ----------------------------------------------------------------------------
# response.txt -> versão final consolidada, Sources, blocos SQL, figuras, citações
# ----------------------------------------------------------------------------
SQL_START = re.compile(r'^\s*(SELECT|WITH)\b')

def sqlnorm(s): return re.sub(r'\s+', ' ', s or '').strip().lower()

def parse_table_md(lines):
    rows = []
    for l in lines:
        l = l.strip()
        if not l.startswith('|'): continue
        cells = [c.strip() for c in l.strip('|').split('|')]
        if all(re.match(r'^:?-{2,}:?$', c) for c in cells): continue
        rows.append(cells)
    if not rows: return None
    return {'header': rows[0], 'rows': rows[1:]}

def parse_query_blocks(lines):
    """Todos os blocos 'Used tables: ...' + SQL + tabela de resultado em qualquer versão do Response."""
    blocks = []
    for i, l in enumerate(lines):
        if not l.startswith('Used tables:'): continue
        j = i - 1
        while j >= 0 and not lines[j].strip(): j -= 1
        title = lines[j].strip() if j >= 0 else None
        if title and norm(title) in ('executed query',): title = None
        k = i + 1
        while k < len(lines) and not lines[k].strip(): k += 1
        sql = []
        while k < len(lines) and lines[k].strip(): sql.append(lines[k].rstrip()); k += 1
        while k < len(lines) and not lines[k].strip(): k += 1
        tab = []
        while k < len(lines) and lines[k].strip().startswith('|'): tab.append(lines[k]); k += 1
        blocks.append({'title': title, 'tables': l.split(':', 1)[1].strip(), 'sql': '\n'.join(sql),
                       'table': parse_table_md(tab) if tab else None, 'line': i})
    return blocks

def parse_txt(path, doc_title):
    t = open(path, encoding='utf-8-sig').read().replace('\r\n', '\n').replace('\r', '\n')
    lines = t.split('\n')
    # versão final = última ocorrência do título do documento; termina em "Sources (N)"
    starts = [i for i, l in enumerate(lines) if norm(l) == norm(doc_title)]
    if not starts: raise SystemExit("Título do relatório não encontrado no TXT")
    start = starts[-1]
    end = next((i for i in range(start, len(lines)) if re.match(r'^\s*Sources\s*\(\d+\)', lines[i])), len(lines))
    declared = int(re.search(r'\((\d+)\)', lines[end]).group(1)) if end < len(lines) else None
    # lista Sources (conferência item a item)
    sources = []
    k = end + 1
    while k < len(lines) and not lines[k].strip(): k += 1
    while k < len(lines):
        m = re.match(r'^\s*(\d+)\.\s+(.+?)\s*$', lines[k])
        if not m: break
        sources.append({'n': int(m.group(1)), 'title': m.group(2)}); k += 1
    if not sources and declared:           # formato antigo: itens sem numeração, um por linha
        k = end + 1
        while len(sources) < declared and k < len(lines):
            if lines[k].strip(): sources.append({'n': len(sources) + 1, 'title': lines[k].strip()})
            k += 1
        if sources: warn("Lista Sources sem numeração: itens numerados pela ordem de aparição")
    if declared is not None and declared != len(sources):
        warn(f"Sources declara {declared} itens, mas {len(sources)} foram identificados no TXT")
    if [s['n'] for s in sources] != list(range(1, len(sources) + 1)):
        warn("Numeração da lista Sources não é sequencial 1..N")
    final = [l for l in lines[start:end] if not re.match(r'^\s*_{3,}\s*$', l)]
    blocks = parse_query_blocks(lines)
    return dict(lines=lines, final=final, sources=sources, declared=declared, blocks=blocks)

def find_source_idx(sources, label):
    nl = norm(label)
    for s in sources:
        if norm(s['title']) == nl: return s['n']
    best = max(sources, key=lambda s: difflib.SequenceMatcher(None, norm(s['title']), nl).ratio(), default=None)
    if best and difflib.SequenceMatcher(None, norm(best['title']), nl).ratio() >= 0.8: return best['n']
    return None

def parse_final(final, sources):
    """Figuras (título + [tabela tsv] + 'Source: X'), SQL inline e citações numéricas de fim de linha."""
    figs, cites, inline_sql = [], [], []
    i = 0; n = len(final)
    last_sql = None   # (texto, linha_fim)
    in_tsv = False
    text_lines = []
    while i < n:
        l = final[i]
        if SQL_START.match(l) and not l.startswith('\t'):
            j = i; buf = []
            while j < n and final[j].strip(): buf.append(final[j].rstrip()); j += 1
            last_sql = ('\n'.join(buf), j); i = j; continue
        if l.strip().startswith('Source:'):
            label = l.split(':', 1)[1].strip()
            # sobe: tabela tsv?
            j = i - 1
            while j >= 0 and not final[j].strip(): j -= 1
            tsv = []
            while j >= 0 and '\t' in final[j]: tsv.insert(0, final[j]); j -= 1
            while j >= 0 and not final[j].strip(): j -= 1
            ftitle = final[j].strip() if j >= 0 else ''
            sql = None
            if last_sql and all(not final[x].strip() for x in range(last_sql[1], j)): sql = last_sql[0]
            fig = {'title': ftitle, 'src': find_source_idx(sources, label), 'src_label': label,
                   'kind': 'table' if tsv else 'chart', 'order': len(figs), 'line': i}
            if tsv:
                hdr = [c.strip() for c in re.split(r'\t+', tsv[0].strip()) if c.strip()]
                rows = [[c.strip() for c in re.split(r'\t+', r.strip()) if c.strip()] for r in tsv[1:]]
                fig['tsv'] = {'header': hdr, 'rows': rows}
            if sql: fig['sql'] = sql; inline_sql.append((fig['src'], sql))
            figs.append(fig)
            # as linhas do título/tsv já consumidas não devem virar citação
            for x in range(j, i + 1): final[x] = ''
            i += 1; continue
        text_lines.append((i, l)); i += 1
    # citações: "texto. 5" no fim da linha
    for idx, l in enumerate(final):
        if not l.strip() or '\t' in l or SQL_START.match(l): continue
        m = re.match(r'^(.*[\.\:\)\!\?%])\s+(\d{1,3})\s*$', l.rstrip())
        if m and 1 <= int(m.group(2)) <= len(sources):
            body = re.sub(r'^\s*[°•\-\*]\s*', '', m.group(1)).strip()
            cites.append({'text': body, 'src': int(m.group(2)), 'line': idx})
    return figs, cites, inline_sql

def assign_blocks(sources, blocks, figs, inline_sql):
    """Associa cada fonte ao seu bloco (SQL + resultado), sem misturar fontes."""
    result = {}
    for s in sources:
        n, title = s['n'], s['title']
        cand = [b for b in blocks if b['title'] and norm(b['title']) == norm(title)]
        how = 'título'
        if not cand:
            sqls = {sqlnorm(q) for sn, q in inline_sql if sn == n}
            cand = [b for b in blocks if sqlnorm(b['sql']) in sqls] if sqls else []
            how = 'SQL idêntico à consulta do relatório final'
        if not cand:
            scored = [(difflib.SequenceMatcher(None, norm(b['title'] or ''), norm(title)).ratio(), b) for b in blocks if b['title']]
            scored = [x for x in scored if x[0] >= 0.75]
            cand = [b for _, b in sorted(scored, key=lambda x: -x[0])[:1]]
            how = 'título aproximado'
        if cand:
            with_tab = [b for b in cand if b['table']]
            b = (with_tab or cand)[-1]
            result[n] = dict(b, how=how)
        else:
            result[n] = None
            warn(f"Fonte {n} ('{title}'): trecho não pôde ser isolado com segurança no TXT")
    return result
# ----------------------------------------------------------------------------
# Gráficos: inferência (PNG original x colunas do resultado SQL) e SVG responsivo
# ----------------------------------------------------------------------------
def col_values(table, j):
    return [parse_num(r[j]) if j < len(r) else None for r in table['rows']]

def numeric_cols(table, skip=(0,)):
    out = []
    for j in range(len(table['header'])):
        if j in skip: continue
        v = col_values(table, j)
        if v and all(x is not None for x in v): out.append(j)
    return out

def analyze_png(path):
    """Tipo do gráfico e medidas dos elementos a partir dos pixels do PNG original."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    im = np.array(Image.open(path).convert('RGB')).astype(int)
    H, W, _ = im.shape
    mx, mn = im.max(2), im.min(2)
    cand = (mx > 130) & ((mx - mn) >= 12) & ((mx - mn) <= 70) & (mn > 90)
    if cand.sum() < 50: return None
    cols = collections.Counter(map(tuple, (im[cand] // 8 * 8).tolist()))
    base = np.array(cols.most_common(1)[0][0]) + 4
    mask = (np.abs(im - base).max(2) <= 16)
    lab, nl = ndimage.label(mask, structure=np.ones((3, 3)))
    comps = []
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        h = sl[0].stop - sl[0].start; w = sl[1].stop - sl[1].start
        area = int((lab[sl] == k).sum())
        comps.append(dict(x0=sl[1].start, x1=sl[1].stop, y0=sl[0].start, y1=sl[0].stop, w=w, h=h, area=area, fill=area / (w * h)))
    bars = [c for c in comps if c['area'] >= 150 and c['fill'] > 0.8 and c['w'] >= 6 and c['h'] >= 6]
    res = {'W': W, 'H': H}
    if len(bars) >= 2:
        left = np.array([b['x0'] for b in bars]); bot = np.array([b['y1'] for b in bars])
        if np.std(bot) <= 3 and np.std(left) > 3:
            bars.sort(key=lambda b: b['x0']); res.update(type='bar_v', m=[b['h'] for b in bars])
        else:
            bars.sort(key=lambda b: b['y0'])
            zero = collections.Counter(b['x0'] for b in bars).most_common(1)[0][0]
            # barras negativas terminam no zero
            m = []
            for b in bars:
                if abs(b['x0'] - zero) <= 2: m.append(b['w'])
                elif abs(b['x1'] - zero) <= 2: m.append(-b['w'])
                else: m.append(b['w'])
            res.update(type='bar_h', m=m)
        return res
    # linha fina com anti-aliasing: usa máscara ampla + dilatação para ligar fragmentos
    wide = ndimage.binary_dilation(cand, structure=np.ones((3, 3)), iterations=2)
    lab2, _ = ndimage.label(wide, structure=np.ones((3, 3)))
    boxes = ndimage.find_objects(lab2)
    k = max(range(len(boxes)), key=lambda i: boxes[i][1].stop - boxes[i][1].start)
    sl = boxes[k]
    big = dict(x0=sl[1].start, x1=sl[1].stop, y0=sl[0].start, y1=sl[0].stop)
    sub = (cand & (lab2 == k + 1))[:, big['x0']:big['x1']]
    ys = [(np.nonzero(sub[:, x])[0].mean() if sub[:, x].any() else np.nan) for x in range(sub.shape[1])]
    res.update(type='line', ys=ys, x0=big['x0'], x1=big['x1'], y0=big['y0'], y1=big['y1'], img=im)
    return res

def match_series(an, table):
    """Escolhe a coluna cujos valores reproduzem a geometria medida. Devolve (idx, erro)."""
    import numpy as np
    cands = numeric_cols(table)
    if not cands: return None, None
    best = (None, 9e9)
    if an['type'] in ('bar_h', 'bar_v'):
        m = np.array(an['m'], float); n = len(m)
        mm = m / np.abs(m).max()
        for j in cands:
            v = np.array(col_values(table, j)[:n], float)
            if len(v) < n or np.abs(v).max() == 0: continue
            e = np.abs(v / np.abs(v).max() - mm).mean()
            if e < best[1]: best = (j, e)
    else:
        ys = np.array(an['ys'], float)
        ok = ~np.isnan(ys)
        for j in cands:
            v = np.array(col_values(table, j), float); n = len(v)
            if n < 3 or ok.sum() < 3: continue
            xs = np.linspace(0, len(ys) - 1, n)
            s = np.interp(xs, np.nonzero(ok)[0], ys[ok])
            if np.std(v) == 0 or np.std(s) == 0: continue
            e = 1 - abs(np.corrcoef(-s, v)[0, 1])
            if e < best[1]: best = (j, e)
    return best

def detect_reflines(an, table, jval):
    """Linhas horizontais de referência (ex.: média geral) em gráficos de linha."""
    import numpy as np
    out = []
    if an['type'] != 'line' or jval is None: return out
    im = an['img']; H, W, _ = im.shape
    mx, mn = im.max(2), im.min(2)
    gray = ((mx - mn) < 10) & (mx > 110) & (mx < 215)
    rows = np.nonzero(gray.sum(1) > 0.6 * W)[0]
    if not len(rows): return out
    # agrupa linhas consecutivas
    groups, cur = [], [rows[0]]
    for r in rows[1:]:
        if r - cur[-1] <= 1: cur.append(r)
        else: groups.append(cur); cur = [r]
    groups.append(cur)
    v = np.array(col_values(table, jval), float); n = len(v)
    ys = np.array(an['ys'], float); ok = ~np.isnan(ys)
    xs = np.linspace(0, len(ys) - 1, n); s = np.interp(xs, np.nonzero(ok)[0], ys[ok])
    a, b = np.polyfit(v, s, 1)         # y_pix = a*v + b
    for g in groups:
        y = float(np.mean(g))
        if not (an['y0'] - 3 <= y <= an['y1'] + 3): continue   # o eixo inferior fica fora da faixa dos dados
        val = (y - b) / a
        out.append({'value': val, 'y': y})
    return out

def ocr_refinement(an, ref, png_path):
    """Tenta ler 'NN%' perto da linha de referência; devolve (valor, tem_rotulo_media)."""
    try:
        import pytesseract
        from PIL import Image, ImageOps
        im = Image.open(png_path).convert('L'); W, H = im.size
        y = int(ref['y'])
        crop = im.crop((int(W * 0.78), max(0, y - 22), W, min(H, y + 10)))
        crop = ImageOps.invert(crop).resize((crop.width * 4, crop.height * 4))
        txt = pytesseract.image_to_string(crop, config='--psm 7')
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', txt)
        val = float(m.group(1).replace(',', '.')) if m else None
        return val, bool(re.search(r'g[ea]r', txt.lower()))
    except Exception:
        return None, False

def infer_chart(fig, table, png_path):
    """Monta a especificação do gráfico. Tudo vem dos dados + geometria do PNG."""
    spec = {'title': fig['title'], 'src': fig['src'], 'warnings': []}
    if table is None: spec['warnings'].append('sem resultado SQL associado'); return spec
    an = analyze_png(png_path) if png_path else None
    cat = 0
    if an is None:
        spec['warnings'].append('PNG ausente/ilegível: usando heurística (barras horizontais)')
        j = (numeric_cols(table) or [1])[0]; typ = 'bar_h'; err = None
    else:
        j, err = match_series(an, table); typ = an['type']
        if j is None or err is None or err > (0.12 if typ != 'line' else 0.08):
            spec['warnings'].append(f'correspondência fraca entre PNG e colunas (erro={err})')
            if j is None: j = (numeric_cols(table) or [1])[0]
    vals = col_values(table, j)
    n_png = len(an['m']) if an and 'm' in an else None
    if n_png and n_png != len(vals):
        mxv = max(abs(v) for v in vals) or 1
        tiny = sum(1 for v in vals if abs(v) / mxv < 0.03)      # barras quase nulas não são detectadas no PNG
        if not (0 < len(vals) - n_png <= tiny):
            spec['warnings'].append(f'PNG tem {n_png} elementos e o resultado tem {len(vals)} linhas')
    # rótulos de categoria
    cats = [r[cat] for r in table['rows']]
    spec.update(type=typ, cat_idx=cat, val_idx=j, cats=cats, vals=vals, cat_name=table['header'][cat],
                val_name=table['header'][j], err=err, n=len(vals), refs=[])
    raw = [r[j] for r in table['rows']]
    spec['dec'] = min(2, max((len(x.split('.')[1]) if '.' in x else 0) for x in raw))
    if typ == 'line' and an:
        for rf in detect_reflines(an, table, j):
            ov, avg = ocr_refinement(an, rf, png_path)
            val = ov if (ov is not None and abs(ov - rf['value']) <= 1.5) else round(rf['value'])
            spec['refs'].append({'value': val, 'label': ('Média geral' if avg else 'Referência')})
    return spec

# ---------------------------- formatação e SVG ------------------------------
MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
def pretty_cat(v):
    m = re.match(r'^(\d{4})-(\d{2})(?:-\d{2})?', v)
    if m and 1 <= int(m.group(2)) <= 12 and len(v) >= 7: return f"{MESES[int(m.group(2)) - 1]}/{m.group(1)[2:]}"
    return CONFIG['valores'].get(v, v)

def unit_of(colname):
    c = colname.lower()
    if 'pct' in c and 'diferenca' in c: return 'p.p.'
    if c.startswith('pct') or c.startswith('%') or 'pct' in c: return '%'
    if c.endswith('_min'): return 'min'
    return ''

def label_of(colname):
    return CONFIG['glossario'].get(colname, colname.replace('_', ' ').capitalize())

def fmt_val(v, unit, dec, sign=False):
    s = fmt_dec(abs(v), dec) if (dec or unit) else fmt_int(abs(v))
    if v < 0: s = '−' + s
    elif sign and v > 0: s = '+' + s
    return {'%': s + '%', 'p.p.': s + ' p.p.', 'min': s + ' min'}.get(unit, s)

def nice_ticks(lo, hi, target=5):
    if hi <= lo: hi = lo + 1
    raw = (hi - lo) / target; mag = 10 ** math.floor(math.log10(raw)); step = mag
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag + 1e-12: step = m * mag; break
    a = math.floor(lo / step + 1e-9) * step; b = math.ceil(hi / step - 1e-9) * step
    t, out = a, []
    while t <= b + step * 1e-6: out.append(round(t, 10)); t += step
    return out, step

def fmt_tick(t, step, unit):
    d = max(0, -math.floor(math.log10(step) + 1e-9)) if step < 1 else 0
    s = fmt_dec(abs(t), d); s = ('−' + s) if t < 0 else s
    return {'%': s + '%', 'p.p.': s + ' p.p.'}.get(unit, s)

def tw(s, fs): return len(s) * fs * 0.57

def wrap(text, maxc, maxlines=3):
    maxc = max(6, int(maxc)); words = text.split(); lines = []; cur = ''
    for w in words:
        while len(w) > maxc: 
            if cur: lines.append(cur); cur = ''
            lines.append(w[:maxc - 1] + '-'); w = w[maxc - 1:]
        if not cur: cur = w
        elif len(cur) + 1 + len(w) <= maxc: cur += ' ' + w
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    if len(lines) > maxlines:
        lines = lines[:maxlines]; lines[-1] = lines[-1][:max(1, maxc - 1)].rstrip() + '…'
    return lines or ['']

FS = {'wide': dict(title=16, lab=12.5, tick=12, val=12.5, axt=12.5),
      'stack': dict(title=14, lab=12, tick=11.5, val=12, axt=12)}

def T(x, y, s, cls='svg-label', fs=12, anchor='start', extra=''):
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{fs}" text-anchor="{anchor}"{extra}>{esc(s)}</text>'

def chart_svg(spec, W, mode, cls):
    fs = FS[mode]; unit = unit_of(spec['val_name']); dec = spec['dec']
    cats = [pretty_cat(c) for c in spec['cats']]; vals = spec['vals']; n = len(vals)
    sign = unit == 'p.p.'
    vlab = [fmt_val(v, unit, dec, sign) for v in vals]
    ylabel = label_of(spec['val_name']); xlabel = label_of(spec['cat_name'])
    tl = wrap(spec['title'], (W - 24) / (fs['title'] * .57), 2)
    top = 14 + len(tl) * (fs['title'] + 5) + 6
    parts = []; typ = spec['type']
    for i, l in enumerate(tl): parts.append(T(12, 14 + fs['title'] + i * (fs['title'] + 5) - 3, l, 'svg-title', fs['title']))
    body = []
    if typ == 'bar_h':
        lo, hi = min(0, min(vals)), max(0, max(vals))
        if mode == 'wide':
            longest = max(len(c) for c in cats)
            Lw = min(max(longest * fs['lab'] * .57 + 14, 90), W * 0.40)
            wl = [wrap(c, (Lw - 14) / (fs['lab'] * .57), 3) for c in cats]
            rowh = max(30, max(len(x) for x in wl) * (fs['lab'] + 3) + 12)
            px0 = 22 + Lw + 10
            vw = max(tw(v, fs['val']) for v in vlab) + 10
            if min(vals) < 0: px0 += tw(vlab[vals.index(min(vals))], fs['val']) + 8
            px1 = W - vw - 12; rows = [rowh] * n
        else:
            wl = [wrap(c, (W - 16) / (fs['lab'] * .57), 2) for c in cats]
            vw = max(tw(v, fs['val']) for v in vlab) + 10
            px0 = 12 + (tw(vlab[vals.index(min(vals))], fs['val']) + 8 if min(vals) < 0 else 0); px1 = W - vw - 10
            rows = [len(x) * (fs['lab'] + 3) + 14 + 14 for x in wl]
        target = 5 if mode == 'wide' else 4
        while True:     # número de marcações adaptado à largura útil (evita rótulos colados)
            ticks, step = nice_ticks(lo, hi, target); d0, d1 = ticks[0], ticks[-1]
            need = max(tw(fmt_tick(t, step, unit), fs['tick']) for t in ticks) + 14
            if need * len(ticks) <= (px1 - px0) or target <= 2: break
            target -= 1
        X = lambda v: px0 + (v - d0) / (d1 - d0) * (px1 - px0)
        ybot = top + sum(rows)
        for t in ticks:
            body.append(f'<line class="svg-grid" x1="{X(t):.1f}" y1="{top}" x2="{X(t):.1f}" y2="{ybot:.1f}"/>')
            body.append(T(X(t), ybot + 16, fmt_tick(t, step, unit), 'svg-label', fs['tick'], 'middle'))
        y = top
        for i in range(n):
            if mode == 'wide':
                bh = rows[i] * 0.58; by = y + (rows[i] - bh) / 2
                ly = y + rows[i] / 2 - (len(wl[i]) - 1) * (fs['lab'] + 3) / 2 + fs['lab'] * .35
                for k, l in enumerate(wl[i]): body.append(T(22 + Lw, ly + k * (fs['lab'] + 3), l, 'svg-label', fs['lab'], 'end'))
            else:
                for k, l in enumerate(wl[i]): body.append(T(px0 if min(vals) >= 0 else 12, y + fs['lab'] + 1 + k * (fs['lab'] + 3), l, 'svg-label', fs['lab']))
                bh = 14; by = y + len(wl[i]) * (fs['lab'] + 3) + 4
            xv, x0 = X(vals[i]), X(0)
            body.append(f'<rect class="svg-bar" x="{min(x0, xv):.1f}" y="{by:.1f}" width="{max(abs(xv - x0), 1):.1f}" height="{bh:.1f}" rx="2"><title>{esc(cats[i])}: {esc(vlab[i])}</title></rect>')
            if vals[i] >= 0: body.append(T(xv + 6, by + bh / 2 + fs['val'] * .35, vlab[i], 'svg-value', fs['val']))
            else: body.append(T(xv - 6, by + bh / 2 + fs['val'] * .35, vlab[i], 'svg-value', fs['val'], 'end'))
            y += rows[i]
        body.append(f'<line class="svg-axis" x1="{X(0):.1f}" y1="{top}" x2="{X(0):.1f}" y2="{ybot:.1f}"/>')
        body.append(T((px0 + px1) / 2, ybot + 36, ylabel, 'svg-axt', fs['axt'], 'middle'))
        if mode == 'wide':
            cy = top + sum(rows) / 2
            body.append(f'<text class="svg-axt" font-size="{fs["axt"]}" text-anchor="middle" transform="translate(13 {cy:.1f}) rotate(-90)">{esc(xlabel)}</text>')
        H = ybot + 48
    elif typ == 'bar_v':
        lo, hi = 0, max(vals)
        ticks, step = nice_ticks(lo, hi, 5 if mode == 'wide' else 4); d0, d1 = ticks[0], ticks[-1]
        left = (24 + max(tw(fmt_tick(t, step, unit), fs['tick']) for t in ticks) + 8); right = 14
        pw = W - left - right; band = pw / n
        maxc = int((band - 4) / (fs['tick'] * .57)); rot = maxc < max(len(c) for c in cats) and maxc < 9
        if rot: lw = max(tw(c, fs['tick']) for c in cats); lblh = lw * 0.64 + 14; wl = [[c] for c in cats]
        else: wl = [wrap(c, maxc, 3) for c in cats]; lblh = max(len(x) for x in wl) * (fs['tick'] + 3) + 8
        ph = (240 if mode == 'wide' else 200)
        vmaxw = max(tw(v, fs['val']) for v in vlab); vrot = vmaxw > band - 4      # rótulos de valor verticais se não couberem lado a lado
        ytop = top + (vmaxw + 10 if vrot else 22); ybot = ytop + ph
        Y = lambda v: ybot - (v - d0) / (d1 - d0) * ph
        for t in ticks:
            body.append(f'<line class="svg-grid" x1="{left}" y1="{Y(t):.1f}" x2="{W - right}" y2="{Y(t):.1f}"/>')
            body.append(T(left - 6, Y(t) + 4, fmt_tick(t, step, unit), 'svg-label', fs['tick'], 'end'))
        bw = min(band * 0.66, 110)
        for i in range(n):
            cx = left + band * (i + .5)
            body.append(f'<rect class="svg-bar" x="{cx - bw / 2:.1f}" y="{Y(vals[i]):.1f}" width="{bw:.1f}" height="{ybot - Y(vals[i]):.1f}" rx="2"><title>{esc(cats[i])}: {esc(vlab[i])}</title></rect>')
            if vrot: body.append(f'<text class="svg-value" font-size="{fs["val"]}" text-anchor="start" transform="translate({cx + fs["val"] * .35:.1f} {Y(vals[i]) - 6:.1f}) rotate(-90)">{esc(vlab[i])}</text>')
            else: body.append(T(cx, Y(vals[i]) - 6, vlab[i], 'svg-value', fs['val'], 'middle'))
            if rot: body.append(f'<text class="svg-label" font-size="{fs["tick"]}" text-anchor="end" transform="translate({cx + 4:.1f} {ybot + 14:.1f}) rotate(-40)">{esc(cats[i])}</text>')
            else:
                for k, l in enumerate(wl[i]): body.append(T(cx, ybot + 15 + k * (fs['tick'] + 3), l, 'svg-label', fs['tick'], 'middle'))
        body.append(f'<line class="svg-axis" x1="{left}" y1="{ybot}" x2="{W - right}" y2="{ybot}"/>')
        body.append(T(left + pw / 2, ybot + lblh + 18, xlabel, 'svg-axt', fs['axt'], 'middle'))
        body.append(f'<text class="svg-axt" font-size="{fs["axt"]}" text-anchor="middle" transform="translate(13 {(ytop + ybot) / 2:.1f}) rotate(-90)">{esc(ylabel)}</text>')
        H = ybot + lblh + 30
    else:   # line
        allv = vals + [r['value'] for r in spec['refs']]
        lo, hi = min(allv), max(allv); pad = (hi - lo) * 0.08 or 1
        ticks, step = nice_ticks(lo - pad, hi + pad, 5 if mode == 'wide' else 4); d0, d1 = ticks[0], ticks[-1]
        left = 24 + max(tw(fmt_tick(t, step, unit), fs['tick']) for t in ticks) + 8; right = 26 if mode == 'wide' else 18
        pw = W - left - right; ph = 250 if mode == 'wide' else 200
        legend_h = 24 if spec['refs'] else 0
        lx = 12
        for r in spec['refs']:
            lbl = f"{r['label']}: {fmt_g(r['value'])}{'%' if unit == '%' else ''}"
            body.append(f'<line class="svg-ref" x1="{lx}" y1="{top + 6}" x2="{lx + 26}" y2="{top + 6}"/>')
            body.append(T(lx + 32, top + 10, lbl, 'svg-label', fs['tick']))
            lx += 32 + tw(lbl, fs['tick']) + 22
        ytop = top + 12 + legend_h; ybot = ytop + ph
        Y = lambda v: ybot - (v - d0) / (d1 - d0) * ph
        X = lambda i: left + (pw * i / (n - 1) if n > 1 else pw / 2)
        for t in ticks:
            body.append(f'<line class="svg-grid" x1="{left}" y1="{Y(t):.1f}" x2="{W - right}" y2="{Y(t):.1f}"/>')
            body.append(T(left - 6, Y(t) + 4, fmt_tick(t, step, unit), 'svg-label', fs['tick'], 'end'))
        for r in spec['refs']:
            body.append(f'<line class="svg-ref" x1="{left}" y1="{Y(r["value"]):.1f}" x2="{W - right}" y2="{Y(r["value"]):.1f}"/>')
        pts = ' '.join(f'{X(i):.1f},{Y(v):.1f}' for i, v in enumerate(vals))
        body.append(f'<polyline class="svg-line" points="{pts}"/>')
        for i, v in enumerate(vals):
            body.append(f'<circle class="svg-dot" cx="{X(i):.1f}" cy="{Y(v):.1f}" r="{3.8 if mode == "wide" else 3.2}"><title>{esc(cats[i])}: {esc(vlab[i])}</title></circle>')
        imax, imin = vals.index(max(vals)), vals.index(min(vals))
        for idx, up in ((imax, True), (imin, False)):
            x = X(idx); anc = 'middle'
            if x > W - right - 34: anc = 'end'
            elif x < left + 34: anc = 'start'
            body.append(T(x, Y(vals[idx]) + (-9 if up else 19), vlab[idx], 'svg-value', fs['val'], anc))
        labw = max(tw(c, fs['tick']) for c in cats) + 10
        sp = pw / (n - 1) if n > 1 else pw; stp = max(1, math.ceil(labw / sp))
        shown = [i for i in range(n) if i % stp == 0]
        if shown and shown[-1] != n - 1 and (n - 1 - shown[-1]) >= stp * 0.7: shown.append(n - 1)
        rot = labw > sp * stp * 1.0 and False
        for i in shown: body.append(T(X(i), ybot + 17, cats[i], 'svg-label', fs['tick'], 'middle'))
        body.append(f'<line class="svg-axis" x1="{left}" y1="{ybot}" x2="{W - right}" y2="{ybot}"/>')
        body.append(T(left + pw / 2, ybot + 38, xlabel, 'svg-axt', fs['axt'], 'middle'))
        body.append(f'<text class="svg-axt" font-size="{fs["axt"]}" text-anchor="middle" transform="translate(13 {(ytop + ybot) / 2:.1f}) rotate(-90)">{esc(ylabel)}</text>')
        H = ybot + 50
    desc = '; '.join(f'{c}: {v}' for c, v in zip(cats, vlab))
    alt = f"{spec['title']}. {ylabel} por {xlabel.lower()}."
    return (f'<svg class="viz viz-{cls}" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="{esc(alt)}" xmlns="http://www.w3.org/2000/svg">'
            f'<title>{esc(alt)}</title><desc>{esc(desc)}</desc>' + ''.join(parts) + ''.join(body) + '</svg>')

def chart_all_layouts(spec):
    return ''.join([chart_svg(spec, 330, 'stack', 'm'), chart_svg(spec, 620, 'wide', 't'), chart_svg(spec, 900, 'wide', 'd')])
# ----------------------------------------------------------------------------
# Montagem do HTML
# ----------------------------------------------------------------------------
CODE_RE = re.compile(r"(\b[a-z]+(?:_[a-z0-9]+)+\b(?:\s*=\s*&#x27;[^&]*&#x27;)?|\b[a-z_]+(?:\.[a-z_]+){2,}\b)")

def inline_html(runs):
    out = ''
    for t, b in runs:
        s = CODE_RE.sub(lambda m: f'<code>{m.group(1)}</code>', esc(t))
        out += f'<strong>{s}</strong>' if b and t.strip() else s
    return out

def cite_link(n, sources, label=None):
    title = sources[n - 1]['title']
    return (f'<a class="source-inline" href="#src-{n}" data-open-detail="src-{n}" '
            f'title="Fonte {n}: {esc(title)}">{label or f"Fonte {n}"}</a>')

def table_html(rows, cls='compact-table', header=True):
    if not rows: return ''
    ncol = len(rows[0])
    isnum = [all(re.match(r'^[+\-−]?[\d.,]+\s*(%|p\.p\.|min|mil)?$', (r[j] if j < len(r) else '').strip()) for r in rows[1:] if (r[j] if j < len(r) else '').strip()) and any((r[j] if j < len(r) else '').strip() for r in rows[1:]) for j in range(ncol)]
    h = f'<div class="table-wrap"><table class="{cls}">'
    if header:
        h += '<thead><tr>' + ''.join(f'<th{" class=num" if isnum[j] else ""} scope="col">{esc(c)}</th>' for j, c in enumerate(rows[0])) + '</tr></thead>'
        body = rows[1:]
    else: body = rows
    h += '<tbody>' + ''.join('<tr>' + ''.join(f'<td{" class=num" if isnum[j] else ""}>{esc(c)}</td>' for j, c in enumerate(r)) + '</tr>' for r in body) + '</tbody></table></div>'
    return h

def fmt_cell(s):
    """Formata célula de resultado SQL (formato numérico brasileiro, datas ISO sem horário)."""
    s = (s or '').strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}T00:00:00', s): return s[:10]
    v = parse_num(s)
    if v is None: return s
    if NUM_US.match(s) and '.' not in s: return fmt_int(v)
    if '.' in s and NUM_PLAIN.match(s) or NUM_US.match(s):
        d = len(s.split('.')[1]) if '.' in s else 0
        return fmt_dec(v, d)
    if abs(v) >= 1000 and float(v).is_integer() and not re.match(r'^0\d', s) and len(s) <= 9: return fmt_int(v)
    return s

# ---- tabelas-figura a partir do CSV (formato de exibição inferido do TXT) ----
def tokens(s):
    t = [w for w in norm(s).split() if w not in ('pct', 'min', 'nome', 'de', 'da', 'do')]
    return {w[:5] for w in t}

def map_columns(tsv_header, csv_header):
    used, mapping = set(), []
    for h in tsv_header:
        best, bs = None, -9
        for j, c in enumerate(csv_header):
            if j in used: continue
            a, b = tokens(h), tokens(c.replace('_', ' '))
            sc = len(a & b) / max(1, len(a | b))
            if h.strip().startswith('%') != ('pct' in c): sc -= 0.6
            if ('(min)' in h) != c.endswith('_min'): sc -= 0.3
            if sc > bs: best, bs = j, sc
        used.add(best); mapping.append(best)
    return mapping

def make_formatter(sample):
    sample = (sample or '').strip()
    if 'mil' in sample: return lambda v: (fmt_dec(v / 1000, 1) + ' mil') if abs(v) >= 1000 else fmt_int(v)
    if sample.endswith('%'): return lambda v: fmt_g(v) + '%'
    m = re.match(r'^-?\d+,(\d+)$', sample)
    if m: return lambda v, d=len(m.group(1)): fmt_dec(v, d)
    return lambda v: fmt_int(v) if float(v).is_integer() else fmt_g(v)

def csv_table_rows(fig, csv_path):
    raw = list(csv.reader(open(csv_path, encoding='utf-8-sig')))
    ch, data = raw[0], raw[1:]
    tsv = fig.get('tsv')
    if tsv and len(tsv['header']) <= len(ch):
        order = map_columns(tsv['header'], ch); disp = tsv['header']
        samples = tsv['rows'][0] if tsv['rows'] else [''] * len(disp)
    else:
        order = list(range(len(ch))); disp = [label_of(c) for c in ch]; samples = [''] * len(ch)
        if tsv: warn(f"Tabela '{fig['title']}': cabeçalho do TXT e do CSV têm tamanhos diferentes")
    fm = [make_formatter(s) for s in samples]
    rows = [disp]
    for r in data:
        row = []
        for k, j in enumerate(order):
            cell = r[j] if j < len(r) else ''
            v = parse_num(cell)
            row.append(pretty_cat(cell) if v is None else fm[k](v))
        rows.append(row)
    return rows

# ---- detalhes de fonte ----
def source_detail(n, title, blk):
    if not blk:
        body = '<p>Esta fonte consta na lista Sources do Response, mas o trecho correspondente não pôde ser isolado com segurança.</p>'
    else:
        body = f'<p class="src-meta">Tabelas usadas: <code>{esc(blk["tables"])}</code></p>'
        body += f'<div class="code-shell"><span class="code-label">SQL</span><pre><code>{esc(blk["sql"])}</code></pre></div>'
        if blk['table']:
            rows = [blk['table']['header']] + [[fmt_cell(c) for c in r] for r in blk['table']['rows']]
            body += f'<p class="src-meta">Resultado ({len(blk["table"]["rows"])} {"linha" if len(blk["table"]["rows"]) == 1 else "linhas"}):</p>' + table_html(rows, 'compact-table')
    return (f'<details id="src-{n}"><summary><span>Fonte {n} · {esc(title)}</span></summary>'
            f'<div class="details-body">{body}</div></details>')

# ---- vinculação de citações do TXT aos blocos do PDF ----
def link_citations(secs, cites):
    flat = []
    for si, s in enumerate(secs):
        for ei, e in enumerate(s['elems']):
            if e['k'] == 'p': flat.append(((si, ei, None), e['plain']))
            elif e['k'] == 'h4': flat.append(((si, ei, None), e['text']))
            elif e['k'] in ('ul', 'ol'):
                for ii, it in enumerate(e['items']):
                    flat.append(((si, ei, ii), it['plain']))
                    for ji, sub in enumerate(it.get('sub', [])): flat.append(((si, ei, (ii, ji)), sub['plain']))
    fn = [norm(t)[:200] for _, t in flat]
    res = {}; unmatched = []; ptr = 0
    for c in cites:
        ct = norm(c['text'])[:200]
        def best(rng):
            b = (0, None)
            for i in rng:
                r = difflib.SequenceMatcher(None, ct, fn[i]).ratio()
                if r > b[0]: b = (r, i)
            return b
        r, i = best(range(max(0, ptr - 2), len(flat)))
        if r < 0.85: r, i = best(range(len(flat)))
        if r >= 0.85:
            res.setdefault(flat[i][0], []).append(c['src']); ptr = i
        else: unmatched.append(c)
    return res, unmatched

LEAD_COUNT = {'dois': 2, 'duas': 2, 'três': 3, 'tres': 3, 'quatro': 4, 'cinco': 5, 'seis': 6, 'sete': 7}

def auto_notes(secs, figs_spec):
    notes = []
    for sp in figs_spec:
        m = re.search(r'\bTop\s*(\d+)\b', sp['title'], re.I)
        if m and int(m.group(1)) != sp['n']:
            notes.append(f"A figura “{sp['title']}” apresenta {sp['n']} itens, não {m.group(1)} como o título sugere; o gráfico reproduz os {sp['n']} itens do resultado.")
    for s in secs:
        E = s['elems']
        for k, e in enumerate(E[:-1]):
            if e['k'] in ('p', 'h4') and E[k + 1]['k'] == 'ol':
                lead = e.get('plain') or e.get('text', '')
                m = re.match(r'^(\w+)\s', lead.lower())
                if m and m.group(1) in LEAD_COUNT and LEAD_COUNT[m.group(1)] != len(E[k + 1]['items']):
                    notes.append(f"O texto “{lead[:60]}” anuncia {LEAD_COUNT[m.group(1)]} itens, mas a lista tem {len(E[k + 1]['items'])}.")
    return notes

# ---- cabeçalho / metadados derivados do PDF ----
def doc_meta(title, secs, npages):
    ctx = next((s for s in secs if norm(s['title']).startswith('contexto')), secs[0])
    full = ' '.join([e['plain'] for s in secs for e in s['elems'] if e['k'] == 'p'] +
                    [i['plain'] for s in secs for e in s['elems'] if e['k'] in ('ul', 'ol') for i in e['items']])
    m = {}
    for key, pat in (('voos', r'([\d]{1,3}(?:\.\d{3})+)\s+voos'), ('companhias', r'(\d[\d.]*)\s+companhias'), ('rotas', r'(\d[\d.]*)\s+rotas')):
        mm = re.search(pat, ' '.join(e['plain'] for e in ctx['elems'] if e['k'] == 'p'))
        if mm: m[key] = mm.group(1)
    vs = re.findall(r'([\d]{1,3}(?:\.\d{3})+)\s+voos', ' '.join(e['plain'] for e in ctx['elems'] if e['k'] == 'p'))
    m['voos_analisados'] = next((v for v in vs[1:] if v != m.get('voos')), None)
    src = re.search(r'(Dados públicos [^\n.]+?)\s+(?:via|na tabela|\.|$)', full)
    m['fonte'] = src.group(1).strip() if src else None
    first = next((e['plain'] for e in ctx['elems'] if e['k'] == 'p'), '')
    mm = re.match(r'^(.*?\.)(\s|$)', first)
    m['subtitulo'] = mm.group(1) if mm else first[:200]
    m['paginas'] = npages
    return m

def summary_items(secs):
    sec = next((s for s in secs if 'conclus' in norm(s['title'])), None)
    out = []
    if sec:
        E = sec['elems']
        start = next((i for i, e in enumerate(E) if e['k'] in ('h3', 'h4') and 'critic' in norm(e['text'])), 0)
        for e in E[start:]:
            if e['k'] == 'ol':
                for it in e['items']:
                    t = it['plain']
                    if it.get('sub'): t = t.rstrip(':') + ': ' + '; '.join(s['plain'] for s in it['sub'])
                    out.append(t)
                break
    if not out:
        for s in secs:
            p = next((e['plain'] for e in s['elems'] if e['k'] == 'p'), None)
            if p:
                m = re.match(r'^(.*?[.!?])(\s|$)', p)
                out.append(m.group(1) if m else p[:220])
    return out

# ----------------------------------------------------------------------------
def build(inputs, out_path, notes_file=None):
    raw_txt = open(inputs['txt'], encoding='utf-8-sig').read()
    vocab = vocab_from_text(raw_txt)
    items, nimg, npages = parse_pdf(inputs['pdf'], vocab)
    title, secs = structure(items)
    TX = parse_txt(inputs['txt'], title)
    sources = TX['sources']
    figs, cites, inline_sql = parse_final(TX['final'], sources)
    blkmap = assign_blocks(sources, TX['blocks'], figs, inline_sql)
    if nimg != len(figs): warn(f"PDF tem {nimg} imagens e o TXT descreve {len(figs)} figuras; a associação é feita pela ordem")
    # assets
    pngs = {norm(decode_name(os.path.basename(f))[:-4]): f for f in inputs['pngs']}
    csvs = {norm(decode_name(os.path.basename(f))[:-4]): f for f in inputs['csvs']}
    def asset(d, t):
        nt = norm(t)
        if nt in d: return d[nt]
        if not d: return None
        b = max(d, key=lambda k: difflib.SequenceMatcher(None, k, nt).ratio())
        return d[b] if difflib.SequenceMatcher(None, b, nt).ratio() >= 0.8 else None
    fig_html, specs_report = {}, []
    for f in figs:
        n_src = f['src']; blk = blkmap.get(n_src)
        link = cite_link(n_src, sources, 'Ver fonte da análise') if n_src else ''
        if f['kind'] == 'chart':
            spec = infer_chart(f, blk['table'] if blk else None, asset(pngs, f['title']))
            for w in spec['warnings']: warn(f"Gráfico '{f['title']}': {w}")
            if 'type' not in spec: fig_html[f['order']] = ''; continue
            cap = f"{label_of(spec['val_name'])} por {label_of(spec['cat_name']).lower()}."
            fig_html[f['order']] = (f'<figure class="figure-card svg-card">{chart_all_layouts(spec)}'
                                    f'<figcaption>{esc(cap)} {link}</figcaption></figure>')
            specs_report.append({k: spec[k] for k in ('title', 'type', 'val_name', 'cat_name', 'n', 'refs', 'err', 'warnings')})
        else:
            cp = asset(csvs, f['title'])
            if cp: rows = csv_table_rows(f, cp); srcname = 'CSV'
            elif f.get('tsv'): rows = [f['tsv']['header']] + f['tsv']['rows']; srcname = 'TXT'; warn(f"Tabela '{f['title']}': CSV ausente, usando valores do TXT")
            else: rows = None
            if rows:
                fig_html[f['order']] = (f'<figure class="figure-card table-figure"><figcaption class="fig-title">{esc(f["title"])}</figcaption>'
                                        f'{table_html(rows, "fig-table")}<figcaption>{len(rows) - 1} linhas. {link}</figcaption></figure>')
                specs_report.append({'title': f['title'], 'type': 'table', 'rows': len(rows) - 1, 'cols': len(rows[0]), 'origem': srcname})
            else: fig_html[f['order']] = ''
    # citações -> blocos
    cmap, unmatched = link_citations(secs, cites)
    for c in unmatched: warn(f"Citação da fonte {c['src']} não vinculada a um trecho do PDF: {c['text'][:60]}…")
    # seção de origem de cada fonte
    pos = {}
    for (si, ei, ii), ns in cmap.items():
        for n in ns: pos.setdefault(n, []).append((si, ei))
    for si, s in enumerate(secs):
        for ei, e in enumerate(s['elems']):
            if e['k'] == 'img' and e['idx'] < len(figs) and figs[e['idx']]['src']:
                pos.setdefault(figs[e['idx']]['src'], []).append((si, ei))
    home = {}
    for s_ in sources:
        n = s_['n']
        if n in pos: home[n] = min(pos[n])[0]
        else: home[n] = len(secs) - 1; warn(f"Fonte {n} sem citação/figura no PDF; anexada à última seção")
    specs_titles = [r for r in specs_report if r.get('type') not in (None, 'table')]
    notes = auto_notes(secs, specs_titles)
    if notes_file and os.path.exists(notes_file):
        notes += [str(x) for x in json.load(open(notes_file, encoding='utf-8'))]
    meta = doc_meta(title, secs, npages)

    # --------------------------- seções ---------------------------
    def ids(si):
        s = secs[si]; return f"s{s['num']}" if s['num'] is not None else slug(s['title'])
    def callout_type(runs):
        if not runs or not runs[0][1]: return None
        lab = norm(runs[0][0]).rstrip()
        for k, v in CONFIG['callouts'].items():
            if lab.startswith(k): return v
        return None
    def li_html(it, cite_ns):
        h = inline_html(it['runs']) + ''.join(' ' + cite_link(n, sources) for n in cite_ns)
        if it.get('sub'):
            h += '<ul class="subtle-list">' + ''.join(f'<li>{inline_html(s["runs"])}</li>' for s in it['sub']) + '</ul>'
        return f'<li>{h}</li>'
    sec_html = []
    for si, s in enumerate(secs):
        body = []
        for ei, e in enumerate(s['elems']):
            k = e['k']
            if k == 'h3': body.append(f'<h3>{esc(e["text"])}</h3>')
            elif k == 'h4':
                links = ''.join(' ' + cite_link(n, sources) for n in cmap.get((si, ei, None), []))
                body.append(f'<h4>{esc(e["text"])}{links}</h4>')
            elif k == 'p':
                links = ''.join(' ' + cite_link(n, sources) for n in cmap.get((si, ei, None), []))
                ct = callout_type(e['runs'])
                inner = f'<p>{inline_html(e["runs"])}{links}</p>'
                body.append(f'<div class="callout {ct}">{inner}</div>' if ct else inner)
            elif k in ('ul', 'ol'):
                lis = ''.join(li_html(it, cmap.get((si, ei, ii), [])) for ii, it in enumerate(e['items']))
                st = f' start="{e["start"]}"' if k == 'ol' and e.get('start', 1) != 1 else ''
                body.append(f'<{k}{st}>{lis}</{k}>')
            elif k == 'table': body.append(table_html(e['rows']))
            elif k == 'img': body.append(fig_html.get(e['idx'], ''))
        dets = ''.join(source_detail(x['n'], x['title'], blkmap.get(x['n'])) for x in sources if home[x['n']] == si)
        if si == len(secs) - 1:
            body.append(f'<div class="callout info"><p>{esc(CONFIG["performance"])}</p></div>')
            if notes:
                body.append('<details id="consistencia"><summary><span>Observações de consistência</span></summary><div class="details-body"><ul>'
                            + ''.join(f'<li>{esc(x)}</li>' for x in notes) + '</ul></div></details>')
        num = f'<span class="section-number">{s["num"]}</span> ' if s['num'] is not None else ''
        sec_html.append(f'<section id="{ids(si)}" class="card" aria-labelledby="t-{ids(si)}">'
                        f'<h2 class="section-title" id="t-{ids(si)}">{num}{esc(s["title"])}</h2><div class="section-rule"></div>'
                        f'<div class="pdf-body">{"".join(body)}</div>{dets}'
                        f'<a class="top-link" href="#topo">↑ Voltar ao topo</a></section>')
    # --------------------------- resumo / fontes ---------------------------
    cards = []
    for key, lab in (('voos', 'voos no conjunto de dados'), ('companhias', 'companhias aéreas'), ('rotas', 'rotas'), ('voos_analisados', 'voos nas análises temporais')):
        if meta.get(key): cards.append(f'<div class="metric"><span class="value">{esc(meta[key])}</span><span class="label">{lab}</span></div>')
    sitems = summary_items(secs)
    resumo = ('<section id="resumo" class="card" aria-labelledby="t-resumo"><h2 class="section-title" id="t-resumo">Resumo Executivo</h2>'
              '<div class="section-rule"></div>' + (f'<div class="metric-grid">{"".join(cards)}</div>' if cards else '') +
              (f'<ol>{"".join(f"<li>{esc(t)}</li>" for t in sitems)}</ol>' if sitems else '') +
              '<a class="top-link" href="#topo">↑ Voltar ao topo</a></section>')
    fontes = ('<section id="fontes" class="card" aria-labelledby="t-fontes"><h2 class="section-title" id="t-fontes">Fontes das Análises</h2>'
              '<div class="section-rule"></div><p>Cada link abre o grupo recolhível correspondente, com a consulta SQL e o resultado que fundamentam a análise.</p>'
              '<ol class="sources-list">' + ''.join(f'<li><a href="#src-{x["n"]}" data-open-detail="src-{x["n"]}">{esc(x["title"])}</a></li>' for x in sources) +
              '</ol><a class="top-link" href="#topo">↑ Voltar ao topo</a></section>')
    toc = ['<li><a href="#resumo">Resumo Executivo</a></li>'] + \
          [f'<li><a href="#{ids(i)}">{esc(s["raw_title"])}</a></li>' for i, s in enumerate(secs)] + \
          ['<li><a href="#fontes">Fontes das Análises</a></li>']
    badges = []
    if meta['fonte']: badges.append(f'Fonte: {meta["fonte"]}')
    badges += [f'{len([s for s in secs if s["num"] is not None])} seções analíticas', f'{len(sources)} fontes SQL', f'Documento de origem: {npages} páginas']
    eyebrow = 'Relatório analítico' + (f' · {meta["fonte"]}' if meta['fonte'] else '')
    page = render_page(title=esc(title), css=BASE_CSS + CSS_TAIL, eyebrow=esc(eyebrow), h1=esc(title), subtitle=esc(meta['subtitulo']),
                       badges=''.join(f'<span class="badge">{esc(b)}</span>' for b in badges), toc=''.join(toc),
                       sections=resumo + ''.join(sec_html) + fontes, note=esc(CONFIG['nota_final']), key=CONFIG['tema_storage_key'])
    open(out_path, 'w', encoding='utf-8').write(page)
    return dict(sections=len(secs), sources=len(sources), figures=len(figs), charts=sum(1 for f in figs if f['kind'] == 'chart'),
                tables_fig=sum(1 for f in figs if f['kind'] == 'table'), cites=len(cites), specs=specs_report, notes=notes,
                pdf_blocks=[(s['raw_title'], [e for e in s['elems']]) for s in secs])

# ----------------------------------------------------------------------------
# CSS-base (idêntico ao padrão visual de referência) e página
# ----------------------------------------------------------------------------
BASE_CSS = r'''
    :root {
      color-scheme: light;
      --bg: #F5F1E8;
      --bg-secondary: #ECE5D6;
      --card: #FFFCF6;
      --header-start: #3F5646;
      --header-mid: #6F8064;
      --header-end: #C8AE7D;
      --primary: #6F8064;
      --primary-strong: #556B55;
      --accent: #C8AE7D;
      --accent-secondary: #A7B59B;
      --text: #2E352D;
      --text-secondary: #697065;
      --header-text: #FFFDF7;
      --header-muted: #EDE6D8;
      --border: #D8CDB8;
      --link: #526B50;
      --code-bg: #EFE8DB;
      --code-text: #2E352D;
      --code-border: #D4C7AF;
      --table-head: #E5DDCC;
      --row-odd: #FAF6EE;
      --row-even: #FFFCF6;
      --info-bg: #EEF2E7;
      --info-border: #6F8064;
      --attention-bg: #F6E9D3;
      --attention-border: #C8AE7D;
      --success-bg: #E7EDE0;
      --success-border: #7F9270;
      --success-text: #3F5646;
      --footer: #E9E1D1;
      --shadow: 0 10px 28px rgba(63, 86, 70, .12);
      --soft-shadow: 0 4px 14px rgba(63, 86, 70, .08);
      --badge-bg: #E5DDCC;
      --badge-text: #3F5646;
      --focus: #C8AE7D;
      --hover-row: rgba(200, 174, 125, .20);
    }

    html[data-theme="dark"] {
      color-scheme: dark;
      --bg: #252D27;
      --bg-secondary: #2F3830;
      --card: #627161;/*#2A332C;*/
      --header-start: #2D3B32;
      --header-mid: #465744;
      --header-end: #7F704F;
      --primary: #B8C6AC;
      --primary-strong: #D1DABE;
      --accent: #D8C49A;
      --accent-secondary: #C0B17D;
      --text: #F0ECE3;
      --text-secondary: #CEC7B7;
      --header-text: #FFFDF7;
      --header-muted: #EFE6D4;
      --border: #b8c6ac;/*#59624F*/;
      --link: #E0CCA1;
      --code-bg: #242C25;
      --code-text: #EEE7DA;
      --code-border: #616A56;
      --table-head: #3A4639;
      --row-odd: #283029;
      --row-even: #2E372F;
      --info-bg: #556b55;/*#303A30;*/
      --info-border: #B8C6AC;
      --attention-bg: #3D3529;
      --attention-border: #D8C49A;
      --success-bg: #556b55;/*#303B2C;*/
      --success-border: #B8C6AC;
      --success-text: #E8EEDC;
      --footer: #242C25;
      --shadow: 0 10px 28px rgba(0, 0, 0, .12);
      --soft-shadow: 0 4px 14px rgba(0, 0, 0, .08);
      --badge-bg: #3A4639;
      --badge-text: #EFE6D4;
      --focus: #D8C49A;
      --hover-row: rgba(216, 196, 154, .20);
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; scroll-padding-top: 1rem; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: 'Segoe UI', Inter, -apple-system, BlinkMacSystemFont, sans-serif;
      font-size: 16px;
      line-height: 1.65;
      overflow-wrap: break-word;
      transition: background-color .2s ease, color .2s ease;
    }
    a { color: var(--link); text-decoration-thickness: .09em; text-underline-offset: .18em; }
    a:hover { text-decoration-thickness: .16em; }
    a:focus-visible, button:focus-visible, summary:focus-visible {
      outline: 3px solid var(--focus);
      outline-offset: 3px;
      border-radius: 6px;
    }
    .skip-link {
      position: fixed; left: 1rem; top: -5rem; z-index: 100;
      padding: .7rem 1rem; background: var(--card); color: var(--text); border-radius: 8px;
    }
    .skip-link:focus { top: 1rem; }
    .container { width: min(1240px, calc(100% - 3rem)); margin-inline: auto; }
    
    header {
      position: relative;
      background-image:
        linear-gradient(125deg, color-mix(in srgb, var(--header-start) 92%, transparent), color-mix(in srgb, var(--header-mid) 90%, transparent) 55%, color-mix(in srgb, var(--header-end) 88%, transparent)),
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='900' height='420' viewBox='0 0 900 420'%3E%3Cg fill='none' stroke='%23ffffff' stroke-opacity='.16'%3E%3Cpath d='M40 330 C190 250 260 370 410 270 S650 230 820 105' stroke-width='2'/%3E%3Cpath d='M95 120 C210 80 290 170 430 130 S620 75 770 165' stroke-width='1.5'/%3E%3C/g%3E%3Cg fill='%23ffffff' fill-opacity='.10'%3E%3Ccircle cx='145' cy='105' r='46'/%3E%3Ccircle cx='760' cy='98' r='72'/%3E%3Ccircle cx='595' cy='315' r='52'/%3E%3C/g%3E%3C/svg%3E");
      background-size: cover;
      background-position: center;
      color: var(--header-text);
      padding: clamp(2.4rem, 7vw, 5.5rem) 0 3.2rem;
      overflow: hidden;
    }
    header::after {
      content: ""; position: absolute; inset: auto -7rem -10rem auto; width: 26rem; height: 26rem;
      border-radius: 50%; background: rgba(255,255,255,.06); pointer-events: none;
    }
    .header-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 2rem; }
    .eyebrow { margin: 0 0 .7rem; color: var(--header-muted); font-size: .87rem; font-weight: 400; letter-spacing: 0; text-transform: none; }
    h1 { max-width: 950px; margin: 0; font-size: 2.18rem; line-height: 1.15; letter-spacing: -.6px; font-weight: 700; }
    .subtitle { max-width: 820px; margin: 1rem 0 0; color: var(--header-muted); font-size: 1.08rem; line-height: 1.65; }
    .badges { display: flex; flex-wrap: wrap; gap: .65rem; margin-top: 1.6rem; }
    .badge { display: inline-flex; align-items: center; gap: .42rem; padding: .42rem .72rem; border: 1px solid rgba(255,255,255,.23); border-radius: 999px; background: rgba(255,255,255,.1); color: var(--header-text); font-size: .84rem; font-weight: 700; }
    .theme-toggle {
      position: fixed; top: 1rem; right: 1rem; z-index: 50;
      display: inline-flex; align-items: center; gap: .55rem; min-height: 44px;
      padding: .68rem .95rem; color: var(--header-text);
      background: color-mix(in srgb, var(--header-start) 82%, transparent);
      border: 1px solid rgba(255,255,255,.35); border-radius: 999px; cursor: pointer;
      font: inherit; font-weight: 700; backdrop-filter: blur(8px); box-shadow: var(--shadow);
    }
    .theme-toggle:hover { background: color-mix(in srgb, var(--header-start) 94%, transparent); }
    .theme-toggle #theme-icon { display: inline-grid; place-items: center; width: 1.15rem; }

    main { padding: 2rem 0 4.5rem; }
    .card {
      background: var(--card); border: 1px solid var(--border); border-radius: 15px;
      box-shadow: var(--shadow); padding: clamp(1.25rem, 3vw, 2rem);
      margin-bottom: 1rem;
    }
    .toc { margin-top: -3.5rem; position: relative; z-index: 2; }
    .toc h2 { margin: 0 0 1rem; font-size: 1.15rem; }
    .toc ol { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: .65rem 1.5rem; margin: 0; padding-left: 1.25rem; }
    .toc a { display: inline-block; padding: .18rem 0; font-weight: 400; text-decoration: none; }
    .toc a:hover { text-decoration: underline; }

    section { margin-top: 2rem; scroll-margin-top: 1rem; }
    .section-title { display: flex; align-items: center; gap: .75rem; margin: 0; font-size: 1.48rem; line-height: 1.65; }
    .section-number { flex: 0 0 auto; display: inline-grid; place-items: center; width: 2.15rem; height: 2.15rem; border-radius: 50%; background: var(--primary); color: #fff; font-size: .92rem; font-weight: 700; }
    .section-rule { height: 1px; margin: .9rem 0 1.3rem; background: linear-gradient(90deg, var(--primary), var(--border) 40%, transparent); }
    h3 { margin: 1.4rem 0 .5rem; font-size: 1.17rem; }
    p { margin: .55rem 0 1rem; }
    ul, ol { padding-left: 1.35rem; }
    li + li { margin-top: .35rem; }
    code { font-family: 'Cascadia Code', 'JetBrains Mono', 'Fira Code', Consolas, monospace; font-size: .88em; }
    p code, li code { padding: .12em .35em; background: var(--code-bg); border: 1px solid var(--code-border); border-radius: 5px; font-size: .88em; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 1rem; }
    .mini-card { padding: 1.15rem; border: 1px solid var(--border); border-radius: 13px; background: var(--bg-secondary); box-shadow: var(--soft-shadow); }
    .mini-card h3 { margin-top: 0; }
    .callout { padding: 1rem 1.15rem; border-left: 4px solid var(--info-border); border-radius: 8px; background: var(--info-bg); }
    .callout.attention, .highlight { border-left: 4px solid var(--attention-border); background: var(--attention-bg); border-radius: 8px; padding: 14px 18px; margin: 15px 0; }
    .highlight strong { color: var(--primary-strong); }
    .callout.success { border-left-color: var(--success-border); background: var(--success-bg); color: var(--success-text); }
    .callout > :last-child { margin-bottom: 0; }
    blockquote { margin: 1rem 0; padding: 1rem 1.2rem; border-left: 4px solid var(--accent-secondary); background: var(--bg-secondary); border-radius: 0 10px 10px 0; font-size: 1rem; }
    .metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: .9rem; margin: 1rem 0; }
    .metric { min-height: 125px; padding: 1rem; border: 1px solid var(--border); border-radius: 13px; background: var(--bg-secondary); box-shadow: var(--soft-shadow); }
    .metric .value { display: block; color: var(--primary-strong); font-size: 1.75rem; font-weight: 800; line-height: 1.2; }
    .metric .label { display: block; margin-top: .35rem; color: var(--text-secondary); font-size: .82rem; font-weight: 400; }

    .table-wrap { width: 100%; overflow-x: auto; border: 1px solid var(--border); border-radius: 12px; }
    table { width: 100%; min-width: 900px; border-collapse: collapse; font-size: .84rem; font-variant-numeric: tabular-nums; }
    th, td { padding: .78rem .85rem; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
    th { background: var(--table-head); color: var(--text); font-size: .84rem; font-weight: 700; letter-spacing: 0; }
    tbody tr:nth-child(odd) { background: var(--row-odd); }
    tbody tr:nth-child(even) { background: var(--row-even); }
    tbody tr:last-child td { border-bottom: 0; }
    tbody tr:hover td { background: var(--hover-row); }
    td.num, th.num { text-align: right; white-space: nowrap; }
    .rank { font-weight: 400; color: var(--primary-strong); }

    details { margin-top: 1rem; border: 1px solid var(--border); border-radius: 12px; background: var(--card); overflow: hidden; }
    summary { display: flex; align-items: center; gap: .75rem; position: relative; list-style: none; cursor: pointer; padding: .9rem 1rem .9rem 2.35rem; font-weight: 400; background: var(--bg-secondary); }
    summary span:first-of-type { flex: 1; }
    summary::-webkit-details-marker { display: none; }
    summary::before { content: "▸"; position: absolute; left: 1rem; top: 50%; translate: 0 -50%; color: var(--primary); font-size: 1rem; transition: transform .18s ease; }
    details[open] summary::before { content: "▾"; }
    details[open] summary { border-bottom: 1px solid var(--border); }
    .details-body { padding: 1rem; }
    .code-shell { position: relative; margin-top: .75rem; }
    .code-label { position: absolute; right: .75rem; top: .65rem; padding: .18rem .5rem; border-radius: 999px; background: var(--badge-bg); color: var(--badge-text); font-size: .76rem; font-weight: 600; }
    pre { margin: 0; padding: 2.8rem 1.15rem 1.15rem; overflow-x: auto; background: var(--code-bg); color: var(--code-text); border: 1px solid var(--code-border); border-radius: 12px; font: .84rem/1.52 'Cascadia Code', 'JetBrains Mono', 'Fira Code', Consolas, monospace; white-space: pre; tab-size: 2; }
    .top-link { display: block; width: max-content; margin: 1rem 0 0 auto; font-size: .82rem; font-weight: 700; text-decoration: none; }
    .top-link:hover { text-decoration: underline; }
    .muted { color: var(--text-secondary); }
    .figure-card { margin: 1.1rem 0; padding: .7rem; border: 1px solid var(--border); border-radius: 13px; background: var(--bg-secondary); box-shadow: var(--soft-shadow); }
    .figure-card img { display: block; width: 100%; height: auto; border-radius: 8px; }
    .figure-card figcaption { padding: .7rem .35rem .15rem; color: var(--text-secondary); font-size: .82rem; }
    .kicker { color: var(--primary-strong); font-size: .84rem; font-weight: 700; letter-spacing: 0; text-transform: none; }
    .recommendation { border-top: 4px solid var(--primary); }
    .compact-table { min-width: 680px; }
    .pill { display: inline-flex; align-items: center; padding: .2rem .55rem; border-radius: 999px; background: var(--badge-bg); color: var(--badge-text); font-size: .84rem; font-weight: 700; }
    .not-found { font-style: italic; color: var(--text-secondary); }

    footer { padding: 2rem 0; background: var(--footer); border-top: 1px solid var(--border); color: var(--text-secondary); font-size: .86rem; }
    footer p { margin: .2rem 0; }
    footer .source-note { margin-top: .75rem; font-size: .78rem; line-height: 1.5; color: var(--text-secondary); }

    @media (max-width: 900px) {
      .toc ol { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .metric-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .header-row { flex-direction: column-reverse; }
      .theme-toggle { align-self: flex-end; }
    }
    @media (max-width: 620px) {
      .container { width: min(100% - 1.25rem, 1240px); }
      header { padding-top: 1.2rem; }
      .toc { margin-top: -2rem; }
      .toc ol, .grid, .metric-grid { grid-template-columns: 1fr; }
      .theme-toggle { top: .75rem; right: .75rem; justify-content: center; }
      .card { padding: 1rem; border-radius: 12px; }
      .section-title { align-items: flex-start; }
      h1 { font-size: 1.75rem; }
      .badges { gap: .45rem; }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { transition-duration: .01ms !important; animation-duration: .01ms !important; }
    }
    @media print {
      :root, html[data-theme="dark"] { color-scheme: light; }
      .theme-toggle, .top-link, .skip-link { display: none !important; }
      body { background: #FFFCF6; color: #2E352D; }
      .card, .mini-card, details { box-shadow: none; break-inside: avoid; }
      header { background: #6F8064 !important; print-color-adjust: exact; }
      details > * { display: block !important; }
    }
  
    '''
CSS_TAIL = r'''
/* ---- ajustes do gerador ---- */
.header-row { display: block; }
header h1 { max-width: none; width: 100%; text-align: center; text-wrap: balance; }
.toc ol { list-style: none; padding-left: 0; }
.theme-toggle #theme-icon { font-size: 1.1rem; filter: saturate(1.2); }
table { min-width: 0; }
.compact-table { min-width: 520px; }
.fig-table { min-width: 560px; }
.table-wrap th.num, .table-wrap td.num { text-align: right; }
.figure-card .fig-title { padding: .2rem .35rem .6rem; color: var(--text); font-size: .95rem; font-weight: 700; }
.fig-note, .src-meta { margin: .7rem 0 .4rem; color: var(--text-secondary); font-size: .84rem; }
.viz { display: none; width: 100%; height: auto; margin-inline: auto; }
.viz-d { display: block; max-width: 1000px; }
.svg-title { fill: var(--text); font-weight: 700; }
.svg-label, .svg-value { paint-order: stroke; stroke: var(--bg-secondary); stroke-width: 4px; stroke-linejoin: round; }
.svg-label { fill: var(--text-secondary); font-family: 'Segoe UI', Inter, sans-serif; }
.svg-value { fill: var(--text); font-weight: 700; font-family: 'Segoe UI', Inter, sans-serif; }
.svg-axt { fill: var(--text); font-weight: 600; font-family: 'Segoe UI', Inter, sans-serif; }
.svg-axis { stroke: var(--text-secondary); stroke-width: 1.2; }
.svg-grid { stroke: var(--border); stroke-width: 1; opacity: .8; }
.svg-bar { fill: var(--primary); }
.svg-line { fill: none; stroke: var(--primary); stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }
.svg-dot { fill: var(--primary); stroke: var(--card); stroke-width: 2; }
.svg-ref { stroke: var(--attention-border); stroke-width: 1.6; stroke-dasharray: 6 5; }
.source-inline { display: inline-block; margin-left: .35rem; font-size: .78rem; font-weight: 700; text-decoration: none; white-space: nowrap; }
.source-inline:hover { text-decoration: underline; }
.sources-list a { text-decoration: none; }
.sources-list a:hover { text-decoration: underline; }
.pdf-body h3 { margin-top: 1.2rem; }
.pdf-body h4 { margin: 1rem 0 .35rem; font-size: 1rem; color: var(--primary-strong); }
.subtle-list { margin-top: .35rem; }
.callout { margin: .9rem 0; }
.source-note-final { font-size: .78rem; line-height: 1.5; color: var(--text-secondary); }
@media (max-width: 900px) { .viz-d { display: none; } .viz-t { display: block; max-width: 760px; } }
@media (max-width: 600px) { .viz-t { display: none; } .viz-m { display: block; max-width: 420px; } .figure-card { padding: .5rem; } }
'''
PAGE_TPL = r'''<!DOCTYPE html>
<html lang="pt-BR" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatório @@TITLE@@</title>
<script>(function(){var t='light';try{if(localStorage.getItem('@@KEY@@')==='dark')t='dark';}catch(e){}document.documentElement.setAttribute('data-theme',t);}());</script>
<style>
@@CSS@@
</style>
</head>
<body id="topo">
<a class="skip-link" href="#conteudo">Ir para o conteúdo principal</a>
<header>
  <div class="container header-row">
    <div>
      <p class="eyebrow">@@EYEBROW@@</p>
      <h1>@@H1@@</h1>
      <p class="subtitle">@@SUBTITLE@@</p>
      <div class="badges" aria-label="Informações do relatório">@@BADGES@@</div>
    </div>
    <button class="theme-toggle" id="theme-toggle" type="button" aria-label="Dark Mode" aria-pressed="false" title="Dark Mode"><span id="theme-icon" aria-hidden="true">🌙</span><span id="theme-label">Dark Mode</span></button>
  </div>
</header>
<main id="conteudo" class="container">
<nav class="toc card" aria-labelledby="toc-title"><h2 id="toc-title">Sumário</h2><ol>@@TOC@@</ol></nav>
@@SECTIONS@@
</main>
<footer><div class="container"><p class="source-note-final"><strong>Fonte complementar:</strong> @@NOTE@@</p></div></footer>
<script>
(function(){
  var root=document.documentElement,btn=document.getElementById('theme-toggle'),lab=document.getElementById('theme-label'),ic=document.getElementById('theme-icon');
  function upd(){var d=root.getAttribute('data-theme')==='dark',a=d?'Light Mode':'Dark Mode';lab.textContent=a;ic.textContent=d?'☀️':'🌙';btn.setAttribute('aria-label',a);btn.setAttribute('title',a);btn.setAttribute('aria-pressed',String(d));}
  btn.addEventListener('click',function(){var n=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',n);try{localStorage.setItem('@@KEY@@',n);}catch(e){}upd();});
  upd();
  function openFor(id,scroll){var el=id&&document.getElementById(id);if(!el)return;var d=el.tagName==='DETAILS'?el:el.closest('details');if(d){d.open=true;}if(scroll){el.scrollIntoView({behavior:'smooth',block:'start'});}}
  document.addEventListener('click',function(e){var a=e.target.closest('a[data-open-detail]');if(!a)return;e.preventDefault();var id=a.getAttribute('data-open-detail');openFor(id,true);if(history.replaceState)history.replaceState(null,'','#'+id);});
  window.addEventListener('hashchange',function(){openFor(location.hash.slice(1),true);});
  if(location.hash)openFor(location.hash.slice(1),false);
})();
</script>
</body>
</html>
'''

def render_page(**kw):
    p = PAGE_TPL
    for k, v in kw.items(): p = p.replace('@@%s@@' % k.upper(), v)
    return p

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('entrada', help='pasta (ou .zip) com PDF, response.txt, CSVs, PNGs e HTML de referência')
    ap.add_argument('-o', '--saida', default='relatorio_onepage.html')
    ap.add_argument('--notes', help='JSON (lista de textos) com observações de consistência verificadas manualmente')
    ap.add_argument('--config', help='JSON para sobrescrever CONFIG (glossário, rótulos, textos fixos)')
    a = ap.parse_args()
    if a.config:
        for k, v in json.load(open(a.config, encoding='utf-8')).items():
            CONFIG[k] = {**CONFIG[k], **v} if isinstance(CONFIG.get(k), dict) else v
    inputs = find_inputs(a.entrada)
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    r = build(inputs, a.saida, a.notes)
    base = os.path.splitext(a.saida)[0]
    json.dump({k: r[k] for k in ('sections', 'sources', 'figures', 'charts', 'tables_fig', 'cites', 'specs', 'notes')},
              open(base + '_inferencias.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    open(base + '_avisos.log', 'w', encoding='utf-8').write('\n'.join(WARN) or 'sem avisos')
    print('OK:', {k: r[k] for k in ('sections', 'sources', 'figures', 'charts', 'tables_fig', 'cites')}, '| avisos:', len(WARN))

if __name__ == '__main__':
    main()
