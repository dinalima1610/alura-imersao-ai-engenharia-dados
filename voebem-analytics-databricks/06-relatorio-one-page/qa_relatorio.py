#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QA do HTML gerado. Uso: python qa_relatorio.py relatorio.html [pasta_screenshots]"""
import sys, re, os, json, asyncio, html as H, unicodedata

def norm(s):
    s = unicodedata.normalize('NFKD', s or ''); s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()

JS = """() => {
  const o = {}; const de = document.documentElement;
  o.pageOverflow = de.scrollWidth - de.clientWidth;
  o.openDetails = document.querySelectorAll('details[open]').length;
  o.clipped = []; o.minFont = 999; o.charts = 0;
  document.querySelectorAll('svg.viz').forEach(svg => {
    const cs = getComputedStyle(svg); if (cs.display === 'none') return;
    o.charts++;
    const vb = svg.viewBox.baseVal, r = svg.getBoundingClientRect(), sc = r.width / vb.width;
    svg.querySelectorAll('text').forEach(t => {
      const b = t.getBBox(); const fs = parseFloat(t.getAttribute('font-size')) * sc;
      o.minFont = Math.min(o.minFont, fs);
      let tx = 0, ty = 0; const tr = t.getAttribute('transform');
      if (b.x < -1 || b.x + b.width > vb.width + 1 || b.y < -1 || b.y + b.height > vb.height + 1) {
        if (!tr) o.clipped.push((svg.getAttribute('aria-label') || '').slice(0, 40) + ' :: ' + t.textContent.slice(0, 30));
      }
    });
    // sobreposição simples entre rótulos de mesma classe
    const ts = [...svg.querySelectorAll('text.svg-label, text.svg-value')].filter(t => !t.getAttribute('transform')).map(t => t.getBBox());
    let ov = 0; for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) {
      const a = ts[i], b = ts[j];
      if (a.x < b.x + b.width - 1 && b.x < a.x + a.width - 1 && a.y < b.y + b.height - 3 && b.y < a.y + a.height - 3) ov++; }
    o.overlaps = (o.overlaps || 0) + ov;
  });
  return o; }"""

async def run(path, outdir):
    from playwright.async_api import async_playwright
    os.makedirs(outdir, exist_ok=True)
    res = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, (w, h) in {'mobile390': (390, 844), 'tablet768': (768, 1024), 'desktop1366': (1366, 900)}.items():
            pg = await b.new_page(viewport={'width': w, 'height': h})
            await pg.goto('file://' + os.path.abspath(path)); await pg.wait_for_timeout(400)
            r = await pg.evaluate(JS)
            h1 = await pg.evaluate("(()=>{const e=document.querySelector('h1');const r=e.getBoundingClientRect();return {lines:Math.round(r.height/parseFloat(getComputedStyle(e).lineHeight)),align:getComputedStyle(e).textAlign}})()")
            r['h1'] = h1; res[name] = r
            await pg.screenshot(path=os.path.join(outdir, f'{name}_topo.png'))
            figs = await pg.query_selector_all('figure.svg-card')
            for i in (0, 3, 6):
                if i < len(figs): await figs[i].screenshot(path=os.path.join(outdir, f'{name}_fig{i + 1}.png'))
            if name == 'desktop1366':
                # tema escuro + abrir fonte por hash e por clique
                await pg.click('#theme-toggle'); await pg.wait_for_timeout(150)
                res['tema_escuro'] = await pg.evaluate("document.documentElement.getAttribute('data-theme')")
                if figs: await figs[1].screenshot(path=os.path.join(outdir, 'desktop_dark_fig2.png'))
                n_src = await pg.evaluate("document.querySelectorAll('details[id^=src-]').length")
                ok = []
                for i in range(1, n_src + 1):
                    await pg.evaluate('window.scrollTo(0,document.body.scrollHeight)')
                    await pg.click(f'.sources-list a[href="#src-{i}"]'); await pg.wait_for_timeout(60)
                    ok.append(await pg.evaluate(f"document.getElementById('src-{i}').open"))
                res['fontes_abrem'] = f'{sum(ok)}/{n_src}'
                pg2 = await b.new_page(viewport={'width': w, 'height': h})
                await pg2.goto('file://' + os.path.abspath(path) + '#src-9'); await pg2.wait_for_timeout(300)
                res['hash_abre_src9'] = await pg2.evaluate("document.getElementById('src-9').open")
            await pg.close()
        await b.close()
    return res

def coverage(path, pdf_texts):
    h = open(path, encoding='utf-8').read()
    body = re.sub(r'<details.*?</details>', ' ', h, flags=re.S)
    body = re.sub(r'<(script|style|svg).*?</\1>', ' ', body, flags=re.S)
    vis = norm(H.unescape(re.sub(r'<[^>]+>', ' ', body)))
    miss = [t for t in pdf_texts if norm(t)[:120] not in vis]
    return len(pdf_texts), miss

if __name__ == '__main__':
    path = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else 'qa_shots'
    r = asyncio.run(run(path, out))
    print(json.dumps(r, indent=1, ensure_ascii=False))
