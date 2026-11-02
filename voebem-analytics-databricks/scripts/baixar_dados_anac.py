#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baixa do portal de dados abertos da ANAC os CSVs do VRA (Voo Regular Ativo) e dos cadastros de referência.

Exemplos:
  python scripts/baixar_dados_anac.py --inicio 2025-08 --fim 2026-07 --destino dados/vra --dry-run
  python scripts/baixar_dados_anac.py --inicio 2025-08 --fim 2026-07 --destino dados/vra
  python scripts/baixar_dados_anac.py --referencias --destino dados/referencias

Observações sobre a fonte (ver DATA_SOURCES.md): o mês no nome do arquivo não tem zero à esquerda
(VRA_20258.csv), mas a pasta tem ("08 - Agosto"); a URL tem espaços e acentos; a primeira linha do
CSV não é o cabeçalho. Use --dry-run primeiro para conferir as URLs com o portal.
"""
import argparse, hashlib, os, sys, urllib.parse, urllib.request

BASE = "https://sistemas.anac.gov.br/dadosabertos"
VRA = f"{BASE}/Voos e operações aéreas/Voo Regular Ativo (VRA)"
MESES = ["01 - Janeiro", "02 - Fevereiro", "03 - Março", "04 - Abril", "05 - Maio", "06 - Junho",
         "07 - Julho", "08 - Agosto", "09 - Setembro", "10 - Outubro", "11 - Novembro", "12 - Dezembro"]
REFERENCIAS = {
    "AerodromosPublicos.csv": f"{BASE}/Aerodromos/Aeródromos Públicos/Lista de aeródromos públicos/AerodromosPublicos.csv",
    "pda_empresas_aereas_nacionais.csv": f"{BASE}/Operador Aéreo/Empresas Aereas Nacionais/pda_empresas_aereas_nacionais.csv",
    "pda_empresas_aereas_estrangeiros.csv": f"{BASE}/Operador Aéreo/Empresas Aereas Estrangeiras/pda_empresas_aereas_estrangeiros.csv",
}

def url_vra(ano, mes):
    return f"{VRA}/{ano}/{MESES[mes - 1]}/VRA_{ano}{mes}.csv"      # mês sem zero no nome do arquivo

def meses(inicio, fim):
    a, m = map(int, inicio.split("-")); a2, m2 = map(int, fim.split("-"))
    while (a, m) <= (a2, m2):
        yield a, m
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)

def baixar(url, destino, dry):
    nome = os.path.basename(urllib.parse.unquote(url))
    caminho = os.path.join(destino, nome)
    print(("[dry-run] " if dry else "") + url)
    if dry: return
    if os.path.exists(caminho): print(f"  já existe: {caminho}"); return
    os.makedirs(destino, exist_ok=True)
    req = urllib.request.Request(urllib.parse.quote(url, safe=":/"), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(caminho, "wb") as f:
        dados = r.read(); f.write(dados)
    print(f"  ok: {caminho} ({len(dados):,} bytes, sha256 {hashlib.sha256(dados).hexdigest()[:16]})")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inicio", help="AAAA-MM"); ap.add_argument("--fim", help="AAAA-MM")
    ap.add_argument("--referencias", action="store_true", help="baixa os 3 cadastros de referência")
    ap.add_argument("--destino", default="dados"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.referencias and not (a.inicio and a.fim): ap.error("informe --inicio e --fim, ou --referencias")
    if a.referencias:
        for url in REFERENCIAS.values(): baixar(url, a.destino, a.dry_run)
    if a.inicio and a.fim:
        for ano, mes in meses(a.inicio, a.fim): baixar(url_vra(ano, mes), a.destino, a.dry_run)

if __name__ == "__main__":
    sys.exit(main())
