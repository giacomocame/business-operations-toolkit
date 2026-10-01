"""
╔══════════════════════════════════════════════════════════════════╗
║   INDIRECT MATERIALS DASHBOARD — GLOBAL MANUFACTURING            ║
║   Output: Standalone HTML SPA (Client-side Search & Aggregation) ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import random
import datetime as dt
from datetime import timedelta, date
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
#  CONFIGURAZIONE
# ─────────────────────────────────────────────────────────────────

OUTPUT_DIR_LATEST = "./output"
LATEST_FILENAME   = "index.html"

AREA_META = {
    "MO":  {"name": "MOLDING",       "color": "#F59E0B"},
    "GR":  {"name": "GRANULATION",   "color": "#22C55E"},
    "PO":  {"name": "POLISHING",     "color": "#A855F7"},
    "FI":  {"name": "FINISHING",     "color": "#3B82F6"},
    "ALT": {"name": "OTHER / STAFF", "color": "#8A8F98"},
}
AREA_ORDER = ["MO", "GR", "PO", "FI", "ALT"]

# ─────────────────────────────────────────────────────────────────
#  1) MOCK DATA ENGINE (Sostituisce Excel e i percorsi di rete)
# ─────────────────────────────────────────────────────────────────

def load_mock_data():
    """Genera i movimenti di magazzino simulati e le allocazioni di budget."""
    print("⏳ Generazione mock data (60 giorni di storico + Budget correlato)...")
    
    today = date.today()
    start_date = today - timedelta(days=60)
    random.seed(101) # Seed fisso per consistenza dati
    
    areas = ["MO", "GR", "PO", "FI", "ALT"]
    cdcs = [f"CC-{random.randint(1000, 9999)}" for _ in range(12)]
    cdc_to_area = {cdc: random.choice(areas) for cdc in cdcs}
    
    reparti = ["Maintenance", "Production", "Quality Control", "Logistics"]
    macro_famiglie = ["Consumables", "Spare Parts", "Packaging"]
    mat_groups = ["MG-Alpha", "MG-Beta", "MG-Gamma", "MG-Delta"]
    ragg_merci = ["Hardware", "Chemicals", "Polymers", "Tools"]
    
    materials = [
        {"codice": f"MAT-{i:04d}", "descrizione": f"Industrial Component {i}", "um": random.choice(["PZ", "KG", "L", "M"])} 
        for i in range(30)
    ]
    utenti = [f"OP-{i:02d}" for i in range(1, 8)]
    
    records = []
    budget_records = []
    
    # 1. Generazione Movimenti Effettivi
    for i in range(61):
        d = start_date + timedelta(days=i)
        if d.weekday() >= 5: continue
        
        for _ in range(random.randint(25, 60)):
            mat = random.choice(materials)
            cdc = random.choice(cdcs)
            qta = random.uniform(1, 150)
            euro_pz = random.uniform(1.5, 80.0)
            val = qta * euro_pz
            
            records.append({
                "utente": random.choice(utenti),
                "data": d,
                "cdc": cdc,
                "codice": mat["codice"],
                "descrizione": mat["descrizione"],
                "qta": qta,
                "um": mat["um"],
                "val": val,
                "reparto": random.choice(reparti),
                "mat_group": random.choice(mat_groups),
                "ragg_merci": random.choice(ragg_merci),
                "macro_famiglia": random.choice(macro_famiglie),
                "area_code": cdc_to_area[cdc],
                "euro_pz": euro_pz,
                "varianza": 0.0, # Calcolata dal JS
                "bdg": 0.0       # Calcolata dal JS
            })
            
    # 2. Generazione Tabella Budget Fissa
    for week_offset in range(-8, 2):
        d = today + timedelta(weeks=week_offset)
        year = d.year
        week = d.isocalendar()[1]
        month = d.month
        
        for cdc in cdcs:
            for mg in mat_groups:
                # Simuliamo che non tutte le combinazioni abbiano budget allocato
                if random.random() > 0.4:
                    budget_records.append({
                        "esercizio": year,
                        "settimana": week,
                        "mese": month,
                        "cdc": cdc,
                        "mat_group": mg,
                        "bdg": random.uniform(1000, 8000),
                        "week_key": year * 100 + week,
                        "month_key": year * 100 + month,
                        "area_code": cdc_to_area[cdc]
                    })
                    
    df = pd.DataFrame(records)
    budget_df = pd.DataFrame(budget_records)
    
    print(f"   → {len(df)} movimenti registrati.")
    print(f"   → {len(budget_df)} righe di budget allocate.")
    return df, budget_df

# ─────────────────────────────────────────────────────────────────
#  2) PAYLOAD COMPRESSO E INDICIZZAZIONE
# ─────────────────────────────────────────────────────────────────

def build_payload(df, budget_df=None):
    """Costruisce dizionari per ridurre il peso del JSON, permettendo
    la ricerca client-side in millisecondi."""

    def build_dict(series, extra_series=None):
        values = set(series.unique())
        if extra_series is not None:
            values |= set(extra_series.unique())
        uniques = sorted(values)
        return uniques, {v: i for i, v in enumerate(uniques)}

    reparti, reparti_idx     = build_dict(df["reparto"])
    macrofams, macrofams_idx = build_dict(df["macro_famiglia"])
    raggmerci, raggmerci_idx = build_dict(df["ragg_merci"])
    utenti, utenti_idx       = build_dict(df["utente"])
    matgroups, matgroups_idx = build_dict(df["mat_group"], budget_df["mat_group"] if budget_df is not None and not budget_df.empty else None)
    cdcs, cdcs_idx           = build_dict(df["cdc"], budget_df["cdc"] if budget_df is not None and not budget_df.empty else None)

    materials, materials_idx = [], {}
    for codice, descr, um in zip(df["codice"], df["descrizione"], df["um"]):
        if codice not in materials_idx:
            materials_idx[codice] = len(materials)
            materials.append([codice, descr, um])

    rows = []
    for r in df.itertuples(index=False):
        date_int = r.data.year * 10000 + r.data.month * 100 + r.data.day
        euro_pz = None if pd.isna(r.euro_pz) else round(float(r.euro_pz), 4)
        rows.append([
            date_int,
            r.area_code,
            cdcs_idx[r.cdc],
            reparti_idx[r.reparto],
            matgroups_idx[r.mat_group],
            macrofams_idx[r.macro_famiglia],
            raggmerci_idx[r.ragg_merci],
            materials_idx[r.codice],
            utenti_idx[r.utente],
            round(float(r.qta), 3),
            round(float(r.val), 2),
            euro_pz,
            round(float(r.varianza), 2),
            round(float(r.bdg), 2),
        ])
    rows.sort(key=lambda x: x[0])

    budget_rows = []
    if budget_df is not None and not budget_df.empty:
        for b in budget_df.itertuples(index=False):
            budget_rows.append([
                int(b.week_key),
                b.area_code,
                cdcs_idx[b.cdc],
                matgroups_idx[b.mat_group],
                round(float(b.bdg), 2),
                int(b.month_key),
            ])
        budget_rows.sort(key=lambda x: x[0])

    dicts = {
        "reparti": reparti, "matgroups": matgroups, "macrofams": macrofams,
        "raggmerci": raggmerci, "utenti": utenti, "cdcs": cdcs, "materials": materials,
    }
    min_date_int = rows[0][0] if rows else None
    max_date_int = rows[-1][0] if rows else None
    return dicts, rows, budget_rows, min_date_int, max_date_int

def _date_int_to_iso(n):
    if n is None: return ""
    y, rem = divmod(n, 10000)
    m, d = divmod(rem, 100)
    return f"{y:04d}-{m:02d}-{d:02d}"

# ─────────────────────────────────────────────────────────────────
#  3) GENERAZIONE HTML (Iniezione Backend -> Frontend)
# ─────────────────────────────────────────────────────────────────

def build_dashboard(dicts, rows, budget_rows, min_date_int, max_date_int, latest_dir=OUTPUT_DIR_LATEST):
    gen_ts = dt.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    min_iso = _date_int_to_iso(min_date_int)
    max_iso = _date_int_to_iso(max_date_int)
    default_iso = max_iso

    dicts_json = json.dumps(dicts, ensure_ascii=False)
    rows_json = json.dumps(rows, separators=(",", ":"))
    budget_rows_json = json.dumps(budget_rows, separators=(",", ":"))
    area_meta_json = json.dumps(AREA_META, ensure_ascii=False)
    area_order_json = json.dumps(AREA_ORDER)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Indirect Materials · PLANT OMEGA</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Baloo+2:wght@600;700;800&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin:0; padding:0; }}
:root {{ color-scheme: dark; }}
body.light-mode {{ color-scheme: light; }}
:root {{
  --bg-deep: #0B0D10;
  --ago-hue: rgba(79, 209, 197, 0.10);
  --text-1: #EDEFF2; --text-2: #8A8F98; --text-3: #575C64;
  --good: #3DD68C; --bad: #FF5D5D;
  --glass-border: rgba(255, 255, 255, 0.08);
  --line-hair: #22252B;
  --pill-bg: rgba(13, 16, 21, 0.72);
  --surface: rgba(255, 255, 255, 0.035);
  --surface2: rgba(255, 255, 255, 0.06);
  --border: var(--glass-border);
  --bg: var(--bg-deep); --txt: var(--text-1); --txt-dim: var(--text-2);
  --grid: var(--line-hair); --plot: transparent; --accent: #4FD1C5;
}}
body.light-mode {{
  --bg-deep: #F2F0EA;
  --ago-hue: rgba(62, 124, 177, 0.09);
  --text-1: #17181A; --text-2: #5B5F66; --text-3: #9297A0;
  --good: #1FAE6E; --bad: #E23D3D;
  --glass-border: rgba(0, 0, 0, 0.09);
  --line-hair: #DDE0E6;
  --pill-bg: rgba(255, 255, 255, 0.78);
  --surface: rgba(0, 0, 0, 0.025);
  --surface2: rgba(0, 0, 0, 0.045);
  --border: var(--glass-border);
  --bg: var(--bg-deep); --txt: var(--text-1); --txt-dim: var(--text-2);
  --grid: var(--line-hair); --accent: #2F8F86;
}}
:root, body.light-mode {{ --col-teal: #4FD1C5; --col-orange: #FF9F45; --col-purple: #B98CFF; }}
body {{ background: var(--bg-deep); color: var(--txt); font-family: 'Space Grotesk', sans-serif; transition: background-color .35s ease, color .35s ease; padding-top: 68px; }}
body::before {{ content: ''; position: fixed; inset: 0; z-index: 0; pointer-events: none; background: radial-gradient(circle at 20% 0%, var(--ago-hue), transparent 55%); }}
#wrap {{ max-width: 1400px; margin: 0 auto; padding: 20px 24px 60px; position: relative; z-index: 1; }}
.nav-brand {{ display:flex; flex-direction:column; gap:2px; line-height:1.15; min-width:0; }}
.brand-text {{ font-family:'Baloo 2', sans-serif; font-weight:700; font-size:19px; letter-spacing:-.01em; white-space:nowrap; }}
.brand-sub {{ font-family:'IBM Plex Mono', monospace; font-size:10px; font-weight:600; letter-spacing:.14em; color:var(--text-2); text-transform:uppercase; white-space:nowrap; }}
.nav-timestamp {{ font-family:'IBM Plex Mono', monospace; font-size:10px; letter-spacing:.06em; color:var(--text-2); font-weight:600; white-space:nowrap; }}
#btn-theme {{ background: var(--surface2); color: var(--text-1); border: 1px solid var(--glass-border); width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all .2s ease; }}
#btn-theme:hover {{ border-color: var(--text-3); transform: translateY(-1px); }}
.date-picker {{ background: var(--surface2); color: var(--txt); border: 1px solid var(--glass-border); font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; border-radius: 10px; cursor: pointer; padding: 8px 10px; height: 34px; flex-shrink: 0; transition: all .2s ease; }}
.date-picker:hover {{ border-color: var(--txt-dim); transform: translateY(-1px); }}
.date-picker::-webkit-calendar-picker-indicator {{ filter: var(--date-icon-filter, none); cursor: pointer; }}
body.light-mode .date-picker {{ --date-icon-filter: none; }}
body:not(.light-mode) .date-picker {{ --date-icon-filter: invert(1); }}
.nav-links {{ position: relative; display: inline-flex; width: 380px; padding: 4px; background: var(--surface2); backdrop-filter: blur(4px); border: 1px solid var(--glass-border); border-radius: 999px; flex-shrink: 0; }}
.nav-slider {{ position: absolute; top: 4px; bottom: 4px; left: 4px; width: calc(25% - 2px); border-radius: 999px; background: linear-gradient(135deg, var(--col-teal), var(--good)); transition: transform .3s cubic-bezier(.4, 0, .2, 1); z-index: 0; }}
.nav-link {{ position: relative; z-index: 1; flex: 1; text-align: center; font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; letter-spacing: .05em; padding: 9px 0; border-radius: 999px; border: none; background: transparent; color: var(--txt-dim); text-decoration: none; cursor: pointer; transition: color .2s ease; white-space: nowrap; }}
.nav-link.active {{ color: #0B0D10; }}
body.light-mode .nav-link.active {{ color: #F2F0EA; }}
.live-status {{ display: flex; flex-direction: column; align-items: flex-end; gap: 3px; min-width: 0; }}
.live-dot {{ display: inline-block; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: var(--good); box-shadow: 0 0 8px var(--good); animation: pulse-dot 2s ease-in-out infinite; }}
@keyframes pulse-dot {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .4; }} }}
.section-block {{ margin-bottom:40px; }}
.section-header {{ display:flex; align-items:center; gap:10px; margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--line-hair); }}
.section-icon {{ font-size:18px; opacity:.85; }}
.section-title {{ font-family:'IBM Plex Mono', monospace; font-size:12px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--text-2); }}
.section-note {{ font-family:'IBM Plex Mono', monospace; font-size:10.5px; color:var(--text-3); margin-left:auto; }}
.kpi-bar-inner {{ display:flex; justify-content:space-around; align-items:center; padding:13px 28px; margin-bottom:14px; border-radius:14px; background: var(--pill-bg); backdrop-filter: blur(16px); border:1px solid var(--glass-border); flex-wrap:wrap; gap:10px; }}
.kpi-bar-inner .kpi-block {{ display:flex; flex-direction:column; align-items:center; gap:2px; }}
.kpi-bar-inner .kpi-lbl {{ display:block; font-family:'IBM Plex Mono', monospace; font-size:9.5px; color:var(--text-2); font-weight:600; letter-spacing:.1em; text-align:center; }}
.kpi-bar-inner .kpi-val {{ font-family:'Space Grotesk', sans-serif; font-size:23px; font-weight:700; display:block; }}
.kpi-bar-inner .sep {{ width:1px; height:38px; background:var(--line-hair); }}
.overview-chart-box, .chart-box {{ background: var(--surface); border:1px solid var(--glass-border); border-radius:12px; padding:10px 10px 4px; margin-bottom:18px; backdrop-filter: blur(10px); }}
.chart-box-title {{ font-family:'IBM Plex Mono', monospace; font-size:10px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--text-2); padding:2px 6px 8px; }}
.charts-row {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:18px; }}
@media (max-width: 900px) {{ .charts-row {{ grid-template-columns:1fr; }} }}
.area-card {{ background: var(--surface); border:1px solid var(--glass-border); border-left:3px solid var(--acolor); border-radius:12px; margin-bottom:12px; overflow:hidden; transition: all .2s ease; backdrop-filter: blur(10px); }}
.area-card:hover {{ border-color: var(--text-3); transform: translateY(-1px); }}
.area-header {{ padding:14px 20px; display:flex; align-items:center; gap:9px; border-bottom:1px solid var(--glass-border); cursor:pointer; }}
.area-header:hover {{ background: var(--surface2); }}
.area-dot {{ width:8px; height:8px; border-radius:50%; background:var(--acolor); flex-shrink:0; box-shadow:0 0 8px var(--acolor); }}
.area-name {{ font-family:'IBM Plex Mono', monospace; font-size:13px; font-weight:600; letter-spacing:.08em; }}
.area-cdl {{ font-family:'IBM Plex Mono', monospace; font-size:10px; color:var(--text-2); margin-left:auto; transition:transform .2s; }}
.area-body {{ padding:16px 20px 20px; }}
.area-kpi {{ display:flex; align-items:center; }}
.kpi-item {{ display:flex; flex-direction:column; align-items:center; flex:1; gap:2px; }}
.kpi-sep {{ width:1px; height:34px; background:var(--line-hair); flex-shrink:0; }}
.cdl-table {{ width:100%; border-collapse:collapse; background: var(--surface2); border:1px solid var(--glass-border); border-radius:10px; overflow:hidden; font-size:11px; font-family:'IBM Plex Mono', monospace; }}
.cdl-table th {{ background: var(--surface); color:var(--text-2); font-size:8.5px; font-weight:600; letter-spacing:.06em; padding:6px 8px; border-bottom:1px solid var(--glass-border); text-align:right; position:sticky; top:0; }}
.cdl-table th.cdl-th-name {{ text-align:left; }}
.cdl-table td {{ padding:6px 8px; text-align:right; border-top:1px solid var(--glass-border); font-size:10.5px; }}
.cdl-name {{ text-align:left !important; color:var(--text-2); font-weight:600; }}
.cdl-val {{ font-weight:600; font-family:'Space Grotesk', sans-serif; }}
.cdl-dim {{ color:var(--text-2) !important; font-weight:500 !important; }}
footer {{ text-align:center; font-family:'IBM Plex Mono', monospace; font-size:10px; color:var(--text-3); margin-top:20px; }}

#navbar {{ position: fixed; top: 0; left: 0; right: 0; z-index: 1000; height: 68px; overflow: hidden; display: grid; grid-template-columns: minmax(170px,1fr) minmax(380px,auto) minmax(420px,1fr); align-items: center; column-gap: 16px; padding: 0 24px; background: var(--pill-bg); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid var(--glass-border); }}
.nav-brand {{ justify-self:start; }}
.nav-center {{ justify-self:center; display:flex; align-items:center; gap:10px; min-width:0; }}
.nav-right {{ justify-self:end; display:flex; align-items:center; gap:10px; min-width:0; }}
@media (max-width: 1360px) {{ #navbar {{ grid-template-columns: minmax(140px,1fr) minmax(320px,auto) minmax(300px,1fr); }} .nav-right {{ gap: 8px; }} }}
@media (max-width: 1100px) {{ #navbar {{ grid-template-columns: minmax(90px,1fr) minmax(260px,auto) minmax(280px,1fr); }} .nav-right {{ gap: 6px; }} }}
.date-picker {{ min-width: 124px; flex-shrink: 0; }}
.nav-status-label {{ display:flex; align-items:center; justify-content:flex-end; gap:6px; font-family:'IBM Plex Mono', monospace; font-size:10.5px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:var(--txt-dim); white-space:nowrap; }}
.area-kpi .kpi-lbl {{ font-family:'IBM Plex Mono', monospace; font-size:8.5px; color:var(--txt-dim); font-weight:600; letter-spacing:.1em; }}
.area-kpi .kpi-val {{ font-family:'Space Grotesk', sans-serif; font-size:16px; font-weight:700; }}
.area-detail-wrap {{ border-top:1px solid var(--glass-border); padding:14px 20px 18px; background: rgba(0,0,0,0.08); }}
body.light-mode .area-detail-wrap {{ background: rgba(0,0,0,0.02); }}
.areas-title {{ font-family:'IBM Plex Mono', monospace; font-size:11px; font-weight:600; letter-spacing:.14em; text-transform: uppercase; color: var(--text-3); margin-bottom:12px; padding-left:12px; border-left:2px solid var(--line-hair); }}
.no-data {{ padding:30px; text-align:center; font-family:'IBM Plex Mono', monospace; color:var(--txt-dim); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
.table-scroll {{ max-height:420px; overflow:auto; }}
.grp-row {{ cursor:pointer; }}
.grp-row:hover td {{ background: var(--surface2); }}
.grp-arrow {{ display:inline-block; width:1em; transition:transform .2s; }}
.grp-arrow.open {{ transform:rotate(90deg); }}
tr.grp-detail-row td {{ padding:0 !important; border-top:none !important; }}
tr.grp-detail-row .cdl-table {{ border-radius:0; border-left:none; border-right:none; }}
.ytd-until {{ font-weight:700; text-decoration:underline; }}
.search-wrap {{ position:relative; flex-shrink:1; min-width:0; }}
.search-input {{ background: var(--surface2) !important; color: var(--txt) !important; -webkit-text-fill-color: var(--txt); caret-color: var(--accent); border: 1px solid var(--glass-border); box-sizing: border-box; font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; border-radius: 10px; padding: 0 12px; height: 34px; width: 130px; min-width:80px; max-width: 100%; flex-shrink:1; transition: border-color .2s ease; }}
.search-input:focus {{ outline:none; border-color: var(--accent); }}
.search-input::placeholder {{ color: var(--txt-dim); }}
@media (max-width: 1520px) {{ .live-status {{ display:none; }} }}
@media (max-width: 1360px) {{ .nav-links {{ width: 320px; }} .search-input {{ width: 110px; }} }}
@media (max-width: 1100px) {{ .brand-sub {{ display:none; }} .search-input {{ width: 90px; }} .search-results {{ width: 320px; }} }}
.search-results {{ position:fixed; width:380px; max-height:440px; overflow-y:auto; background: var(--pill-bg); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border:1px solid var(--glass-border); border-radius:12px; box-shadow: 0 12px 32px rgba(0,0,0,.35); z-index:1100; display:none; }}
.search-results.open {{ display:block; }}
.search-results-header {{ padding:9px 14px; font-family:'IBM Plex Mono', monospace; font-size:9.5px; color:var(--txt-dim); font-weight:600; letter-spacing:.1em; text-transform:uppercase; border-bottom:1px solid var(--glass-border); }}
.search-result-item {{ padding:10px 14px; cursor:pointer; border-bottom:1px solid var(--glass-border); }}
.search-result-item:last-child {{ border-bottom:none; }}
.search-result-item:hover {{ background: var(--surface2); }}
.search-result-main {{ font-family:'Space Grotesk', sans-serif; font-size:12.5px; font-weight:600; color:var(--txt); }}
.search-result-sub {{ font-family:'IBM Plex Mono', monospace; font-size:9.5px; color:var(--txt-dim); margin-top:3px; }}
.search-result-empty {{ padding:18px 14px; text-align:center; font-family:'IBM Plex Mono', monospace; font-size:11px; color:var(--txt-dim); }}
@keyframes search-pulse {{ 0% {{ background: rgba(79,209,197,.45); }} 100% {{ background: transparent; }} }}
tr.search-highlight td {{ animation: search-pulse 2.2s ease-out 1; }}
</style>
</head>
<body>

<nav id="navbar">
  <div class="nav-brand">
    <span class="brand-text">TechCorp Global</span>
    <span class="brand-sub">Plant Omega &middot; Indirect Materials</span>
  </div>

  <div class="nav-center">
    <div class="nav-links">
      <div class="nav-slider" id="navSlider"></div>
      <a class="nav-link active" id="nav-day"   href="#section-day">Daily</a>
      <a class="nav-link"        id="nav-week"  href="#section-week">Weekly</a>
      <a class="nav-link"        id="nav-month" href="#section-month">Monthly</a>
      <a class="nav-link"        id="nav-ytd"   href="#section-ytd">YTD</a>
    </div>
  </div>

  <div class="nav-right">
    <div class="live-status">
      <span class="nav-status-label"><span class="live-dot"></span>INDIRECT MATERIALS</span>
      <span class="nav-timestamp">Generato: {gen_ts}</span>
    </div>
    <div class="search-wrap">
      <input type="text" id="search-input" class="search-input" placeholder="&#128269; Cerca..." autocomplete="off">
    </div>
    <input type="date" id="date-picker" class="date-picker"
           min="{min_iso}" max="{max_iso}" value="{default_iso}" title="Scegli una data">
    <button id="btn-theme" onclick="toggleTheme()" title="Cambia tema">&#9728;&#65039;</button>
  </div>
</nav>

<div class="search-results" id="search-results"></div>

<div id="wrap">
  <div class="section-block" id="section-day">
    <div class="section-header">
      <span class="section-icon">&#128197;</span>
      <span class="section-title" id="period-title-day">&nbsp;</span>
      <span class="section-note" id="period-note-day">&nbsp;</span>
    </div>
    <div class="kpi-bar-inner" id="kpi-bar-day"></div>
    <div class="charts-row" id="charts-row-day">
      <div class="overview-chart-box"><div class="chart-box-title">Ripartizione Costi per Area (&euro;)</div><div id="pie-cdc-day" style="min-height:320px;"></div></div>
      <div class="overview-chart-box"><div class="chart-box-title">Top Categorie (Material Groups)</div><div id="pie-cat-day" style="min-height:320px;"></div></div>
    </div>
    <div class="areas-title">Dettaglio per area produttiva (clicca per espandere)</div>
    <div id="areas-grid-day"></div>
  </div>

  <div class="section-block" id="section-week">
    <div class="section-header">
      <span class="section-icon">&#128198;</span>
      <span class="section-title" id="period-title-week">&nbsp;</span>
      <span class="section-note" id="period-note-week">&nbsp;</span>
    </div>
    <div class="kpi-bar-inner" id="kpi-bar-week"></div>
    <div class="charts-row" id="charts-row-week">
      <div class="overview-chart-box"><div class="chart-box-title">Ripartizione Costi per Area (&euro;)</div><div id="pie-cdc-week" style="min-height:320px;"></div></div>
      <div class="overview-chart-box"><div class="chart-box-title">Top Categorie (Material Groups)</div><div id="pie-cat-week" style="min-height:320px;"></div></div>
    </div>
    <div class="areas-title">Dettaglio per area produttiva (clicca per espandere)</div>
    <div id="areas-grid-week"></div>
  </div>

  <div class="section-block" id="section-month">
    <div class="section-header">
      <span class="section-icon">&#128197;</span>
      <span class="section-title" id="period-title-month">&nbsp;</span>
      <span class="section-note" id="period-note-month">&nbsp;</span>
    </div>
    <div class="kpi-bar-inner" id="kpi-bar-month"></div>
    <div class="charts-row" id="charts-row-month">
      <div class="overview-chart-box"><div class="chart-box-title">Ripartizione Costi per Area (&euro;)</div><div id="pie-cdc-month" style="min-height:320px;"></div></div>
      <div class="overview-chart-box"><div class="chart-box-title">Top Categorie (Material Groups)</div><div id="pie-cat-month" style="min-height:320px;"></div></div>
    </div>
    <div class="areas-title">Dettaglio per area produttiva (clicca per espandere)</div>
    <div id="areas-grid-month"></div>
  </div>

  <div class="section-block" id="section-ytd">
    <div class="section-header">
      <span class="section-icon">&#128200;</span>
      <span class="section-title" id="period-title-ytd">&nbsp;</span>
      <span class="section-note" id="period-note-ytd">&nbsp;</span>
    </div>
    <div class="kpi-bar-inner" id="kpi-bar-ytd"></div>
    <div class="charts-row" id="charts-row-ytd">
      <div class="overview-chart-box"><div class="chart-box-title">Ripartizione Costi per Area (&euro;)</div><div id="pie-cdc-ytd" style="min-height:320px;"></div></div>
      <div class="overview-chart-box"><div class="chart-box-title">Top Categorie (Material Groups)</div><div id="pie-cat-ytd" style="min-height:320px;"></div></div>
    </div>
    <div class="areas-title">Dettaglio per area produttiva (clicca per espandere)</div>
    <div id="areas-grid-ytd"></div>
  </div>
</div>

<footer>Source: In-Memory ERP Mock Data &middot; Generated {gen_ts}</footer>

<script>
const DICTS = {dicts_json};
const ROWS  = {rows_json};
const BUDGET_ROWS = {budget_rows_json};
const AREA_META  = {area_meta_json};
const AREA_ORDER = {area_order_json};
const MIN_DATE_ISO = "{min_iso}";
const MAX_DATE_ISO = "{max_iso}";

function dateIntParts(n) {{ return [Math.floor(n / 10000), Math.floor(n / 100) % 100, n % 100]; }}
function isoWeekOf(y, m, d) {{
  const dtu = new Date(Date.UTC(y, m - 1, d));
  dtu.setUTCDate(dtu.getUTCDate() + 4 - (dtu.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(dtu.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((dtu - yearStart) / 86400000) + 1) / 7);
  return dtu.getUTCFullYear() * 100 + week;
}}
const WEEK_KEYS = ROWS.map(r => {{ const [y, m, d] = dateIntParts(r[0]); return isoWeekOf(y, m, d); }});
ROWS.forEach((r, i) => r.push(WEEK_KEYS[i]));

let LAST_BUDGET_WEEK = 0;
BUDGET_ROWS.forEach(b => {{ if (b[0] > LAST_BUDGET_WEEK) LAST_BUDGET_WEEK = b[0]; }});

const BUDGET_LOOKUP = new Map();
BUDGET_ROWS.forEach(b => {{
  const key = b[0] + '|' + b[2] + '|' + b[3];
  BUDGET_LOOKUP.set(key, (BUDGET_LOOKUP.get(key) || 0) + b[4]);
}});

function weekKeysInRange(startDateInt, endDateInt) {{
  const keys = new Set();
  const [sy, sm, sd] = dateIntParts(startDateInt);
  const [ey, em, ed] = dateIntParts(endDateInt);
  let cur = new Date(Date.UTC(sy, sm - 1, sd));
  const end = new Date(Date.UTC(ey, em - 1, ed));
  while (cur <= end) {{
    keys.add(isoWeekOf(cur.getUTCFullYear(), cur.getUTCMonth() + 1, cur.getUTCDate()));
    cur.setUTCDate(cur.getUTCDate() + 1);
  }}
  return keys;
}}

function budgetPeriodInfo(sid, dateInt) {{
  const [cy, cm, cd] = dateIntParts(dateInt);
  if (sid === 'month') {{
    const monthKey = cy * 100 + cm;
    const covered = BUDGET_ROWS.some(b => b[5] === monthKey);
    return {{ matches: b => b[5] === monthKey, actFilter: r => r[14] <= LAST_BUDGET_WEEK, covered }};
  }}
  const weekSet = (sid === 'day' || sid === 'week')
    ? new Set([isoWeekOf(cy, cm, cd)])
    : weekKeysInRange(cy * 10000 + 101, dateInt);
  const coveredWeeks = new Set([...weekSet].filter(w => w <= LAST_BUDGET_WEEK));
  return {{ matches: b => coveredWeeks.has(b[0]), actFilter: r => coveredWeeks.has(r[14]), covered: coveredWeeks.size > 0 }};
}}

function budgetAndVariance(actRows, periodInfo, budgetFilter) {{
  if (!periodInfo.covered) return {{ bdg: 0, variance: 0, covered: false }};
  let actUsed = 0;
  actRows.forEach(r => {{ if (!periodInfo.actFilter || periodInfo.actFilter(r)) actUsed += r[10]; }});
  let bdgTotal = 0;
  BUDGET_ROWS.forEach(b => {{
    if (!periodInfo.matches(b)) return;
    if (budgetFilter && !budgetFilter(b)) return;
    bdgTotal += b[4];
  }});
  return {{ bdg: bdgTotal, variance: actUsed - bdgTotal, covered: true }};
}}

const SECTIONS = ['day', 'week', 'month', 'ytd'];
const CATEGORY_PALETTE = ['#4FD1C5','#FF9F45','#B98CFF','#3DD68C','#FF5D5D','#60A5FA','#FBBF24','#F472B6','#94A3B8'];
let currentDateInt = parseInt(MAX_DATE_ISO.replace(/-/g, ''), 10) || 0;

function fmtEUR(v)     {{ return '\u20ac ' + Number(v).toLocaleString('en-US', {{minimumFractionDigits:0, maximumFractionDigits:0}}); }}
function fmtEUR2(v)    {{ return '\u20ac ' + Number(v).toLocaleString('en-US', {{minimumFractionDigits:2, maximumFractionDigits:2}}); }}
function fmtNum(v, dec) {{ return Number(v).toLocaleString('en-US', {{minimumFractionDigits:dec, maximumFractionDigits:dec}}); }}
function fmtDateInt(n) {{ const [y, m, d] = dateIntParts(n); return String(d).padStart(2,'0') + '/' + String(m).padStart(2,'0') + '/' + y; }}
function varColor(v) {{ return v > 0 ? 'var(--bad)' : 'var(--good)'; }}

function getT() {{
  const dark = !document.body.classList.contains('light-mode');
  return dark
    ? {{ paper:'rgba(0,0,0,0)', plot:'rgba(0,0,0,0)', font:'#EDEFF2', grid:'#22252B', tick:'#8A8F98', zero:'#22252B', subt:'#575C64' }}
    : {{ paper:'rgba(0,0,0,0)', plot:'rgba(0,0,0,0)', font:'#17181A', grid:'#DDE0E6', tick:'#5B5F66', zero:'#DDE0E6', subt:'#9297A0' }};
}}
function themeLayout(layout) {{
  const T = getT();
  const upd = {{ ...layout, paper_bgcolor:T.paper, plot_bgcolor:T.plot, font:{{ ...layout.font, color:T.font }} }};
  Object.keys(upd).forEach(k => {{
    if (k.startsWith('xaxis') || k.startsWith('yaxis')) {{
      upd[k] = {{ ...upd[k], gridcolor:T.grid, zerolinecolor:T.zero, tickfont:{{ ...((upd[k]||{{}}).tickfont||{{}}), color:T.tick }} }};
    }}
  }});
  return upd;
}}

const _pieSpecs = {{}};
const _areaChartSpecs = {{}};

function periodRowsFor(sid, dateInt) {{
  if (sid === 'day') return ROWS.filter(r => r[0] === dateInt);
  const [cy, cm, cd] = dateIntParts(dateInt);
  if (sid === 'week') {{
    const targetWeek = isoWeekOf(cy, cm, cd);
    return ROWS.filter((r, i) => WEEK_KEYS[i] === targetWeek);
  }}
  if (sid === 'month') {{
    const targetYM = cy * 100 + cm;
    return ROWS.filter(r => Math.floor(r[0] / 100) === targetYM);
  }}
  const ytdStart = cy * 10000 + 101;
  return ROWS.filter(r => r[0] >= ytdStart && r[0] <= dateInt);
}}

function periodLabelHtml(sid, dateInt) {{
  const [cy, cm, cd] = dateIntParts(dateInt);
  const ddmmyyyy = String(cd).padStart(2,'0') + '/' + String(cm).padStart(2,'0') + '/' + cy;
  if (sid === 'day')  return 'DAILY \u2014 ' + ddmmyyyy;
  if (sid === 'week') {{ const wk = isoWeekOf(cy, cm, cd); return 'WEEKLY \u2014 WK' + (wk % 100) + ' ' + Math.floor(wk / 100); }}
  if (sid === 'month') {{
    const MESI = ['JANUARY','FEBRUARY','MARCH','APRIL','MAY','JUNE','JULY','AUGUST','SEPTEMBER','OCTOBER','NOVEMBER','DECEMBER'];
    return 'MONTHLY \u2014 ' + MESI[cm - 1] + ' ' + cy;
  }}
  return 'YEAR TO DATE ' + cy + ' \u2014 up to <span class="ytd-until">' + ddmmyyyy + '</span>';
}}

function pieLayout() {{
  return {{
    margin: {{ t:10, b:10, l:10, r:10 }}, showlegend:true,
    legend: {{ orientation:'v', font:{{ family:'IBM Plex Mono', size:9.5 }}, x:1.02, y:0.5, xanchor:'left' }},
    font: {{ family:'IBM Plex Mono', size:11 }}
  }};
}}

function renderSection(sid) {{
  const rows = periodRowsFor(sid, currentDateInt);
  document.getElementById('period-title-' + sid).innerHTML = periodLabelHtml(sid, currentDateInt);
  document.getElementById('period-note-' + sid).textContent = rows.length + ' transactions';

  const kpiBar = document.getElementById('kpi-bar-' + sid);
  const chartsRow = document.getElementById('charts-row-' + sid);
  const areasGrid = document.getElementById('areas-grid-' + sid);

  window._sectionAreaRows = window._sectionAreaRows || {{}};

  if (rows.length === 0) {{
    kpiBar.innerHTML = '<div class="no-data">No data available for selected period</div>';
    chartsRow.style.display = 'none';
    areasGrid.innerHTML = '';
    window._sectionAreaRows[sid] = {{}};
    return;
  }}
  chartsRow.style.display = '';

  const allowVariance = sid !== 'day';
  let totVal = 0;
  const matSeen = new Set();
  const rowsByArea = {{}};
  AREA_ORDER.forEach(a => rowsByArea[a] = []);
  const rowsByCat = {{}};
  rows.forEach(r => {{
    const area = r[1], matGroupIdx = r[4], raggIdx = r[6], matIdx = r[7], val = r[10];
    totVal += val; matSeen.add(matIdx);
    rowsByArea[area].push(r);
    const key = matGroupIdx + '|' + raggIdx;
    (rowsByCat[key] || (rowsByCat[key] = [])).push(r);
  }});

  const periodInfo = allowVariance ? budgetPeriodInfo(sid, currentDateInt) : {{ matches: () => false, actFilter: null, covered: false }};
  const totBudget = budgetAndVariance(rows, periodInfo, null);
  const varLabel = totBudget.covered ? fmtEUR(totBudget.variance) : 'N/A';
  const varColorStyle = totBudget.covered ? varColor(totBudget.variance) : 'var(--txt-dim)';

  kpiBar.innerHTML = `
    <div class="kpi-block"><span class="kpi-lbl">TOTAL COST</span><span class="kpi-val">${{fmtEUR(totVal)}}</span></div>
    <div class="sep"></div>
    <div class="kpi-block"><span class="kpi-lbl">VARIANCE</span><span class="kpi-val" style="color:${{varColorStyle}}">${{varLabel}}</span></div>
    <div class="sep"></div>
    <div class="kpi-block"><span class="kpi-lbl">AVG COST/TRANS.</span><span class="kpi-val">${{fmtEUR2(rows.length ? totVal / rows.length : 0)}}</span></div>
    <div class="sep"></div>
    <div class="kpi-block"><span class="kpi-lbl">TRANSACTIONS</span><span class="kpi-val">${{rows.length}}</span></div>
    <div class="sep"></div>
    <div class="kpi-block"><span class="kpi-lbl">UNIQUE ITEMS</span><span class="kpi-val">${{matSeen.size}}</span></div>
  `;

  const byArea = {{}};
  AREA_ORDER.forEach(a => {{
    const arows = rowsByArea[a];
    byArea[a] = {{
      val: arows.reduce((s, r) => s + r[10], 0),
      n: arows.length,
      mats: new Set(arows.map(r => r[7])),
      budget: budgetAndVariance(arows, periodInfo, b => b[1] === a)
    }};
  }});

  const pieLabels = [], pieValues = [], pieColors = [], pieVarLabels = [];
  AREA_ORDER.forEach(a => {{
    if (byArea[a].n > 0) {{
      pieLabels.push(AREA_META[a].name); pieValues.push(byArea[a].val); pieColors.push(AREA_META[a].color);
      pieVarLabels.push(byArea[a].budget.covered ? fmtEUR(byArea[a].budget.variance) : 'N/A');
    }}
  }});
  const cdcSpec = {{
    data: [{{
      type: 'pie', labels: pieLabels, values: pieValues, hole: 0.5,
      marker: {{ colors: pieColors }},
      textinfo: 'percent', textposition: 'inside', insidetextorientation: 'radial',
      textfont: {{ family: 'IBM Plex Mono', size: 11, color: '#0B0D10' }},
      customdata: pieVarLabels,
      hovertemplate: '%{{label}}<br>Cost: \u20ac %{{value:,.0f}}<br>Var: %{{customdata}}<br>%{{percent}}<extra></extra>'
    }}],
    layout: pieLayout()
  }};
  _pieSpecs['pie-cdc-' + sid] = cdcSpec;
  Plotly.newPlot('pie-cdc-' + sid, cdcSpec.data, themeLayout(cdcSpec.layout), {{ responsive:true, displayModeBar:false }});

  const catEntries = Object.entries(rowsByCat)
    .map(([key, crows]) => [key, {{ val: crows.reduce((s, r) => s + r[10], 0), rows: crows }}])
    .sort((x, y) => y[1].val - x[1].val);
  const TOP_N = 8;
  const top = catEntries.slice(0, TOP_N);
  const restEntries = catEntries.slice(TOP_N);
  const restRows = restEntries.flatMap(([, v]) => v.rows);
  const restVal = restRows.reduce((s, r) => s + r[10], 0);
  const restMatGroupIdxs = new Set(restEntries.map(([key]) => Number(key.split('|')[0])));
  const restBudget = budgetAndVariance(restRows, periodInfo, b => restMatGroupIdxs.has(b[3]));
  const catLabels = top.map(([key]) => {{ const [mi, ri] = key.split('|').map(Number); return DICTS.matgroups[mi] + ' \u00b7 ' + DICTS.raggmerci[ri]; }});
  const catValues = top.map(([, v]) => v.val);
  const catVarLabels = top.map(([key, v]) => {{
    const matGroupIdx = Number(key.split('|')[0]);
    const b = budgetAndVariance(v.rows, periodInfo, bb => bb[3] === matGroupIdx);
    return b.covered ? fmtEUR(b.variance) : 'N/A';
  }});
  const catColors = top.map((_, i) => CATEGORY_PALETTE[i % (CATEGORY_PALETTE.length - 1)]);
  if (restVal > 0.005) {{
    catLabels.push('OTHER'); catValues.push(restVal);
    catVarLabels.push(restBudget.covered ? fmtEUR(restBudget.variance) : 'N/A');
    catColors.push(CATEGORY_PALETTE[CATEGORY_PALETTE.length - 1]);
  }}
  const catSpec = {{
    data: [{{
      type: 'pie', labels: catLabels, values: catValues, hole: 0.5,
      marker: {{ colors: catColors }},
      textinfo: 'percent', textposition: 'inside', insidetextorientation: 'radial',
      textfont: {{ family: 'IBM Plex Mono', size: 11, color: '#0B0D10' }},
      customdata: catVarLabels,
      hovertemplate: '%{{label}}<br>Cost: \u20ac %{{value:,.0f}}<br>Var: %{{customdata}}<br>%{{percent}}<extra></extra>'
    }}],
    layout: pieLayout()
  }};
  _pieSpecs['pie-cat-' + sid] = catSpec;
  Plotly.newPlot('pie-cat-' + sid, catSpec.data, themeLayout(catSpec.layout), {{ responsive:true, displayModeBar:false }});

  let gridHtml = '';
  AREA_ORDER.forEach(a => {{
    const agg = byArea[a];
    if (agg.n === 0) return;
    const pct = totVal !== 0 ? (agg.val / totVal * 100) : 0;
    const meta = AREA_META[a];
    const cardId = sid + '_' + a;
    const areaVarLabel = agg.budget.covered ? fmtEUR(agg.budget.variance) : 'N/A';
    const areaVarColor = agg.budget.covered ? varColor(agg.budget.variance) : 'var(--txt-dim)';
    gridHtml += `
      <div class="area-card" style="--acolor:${{meta.color}}" id="card-${{cardId}}">
        <div class="area-header" onclick="toggleAreaCard('${{cardId}}')">
          <div class="area-dot"></div>
          <div class="area-name">${{meta.name}}</div>
          <div class="area-cdl" id="chev-${{cardId}}">&#9654;</div>
        </div>
        <div class="area-kpi" style="padding:10px 20px;">
          <div class="kpi-item"><span class="kpi-lbl">ACTUAL COST</span><span class="kpi-val">${{fmtEUR(agg.val)}}</span></div>
          <div class="kpi-sep"></div>
          <div class="kpi-item"><span class="kpi-lbl">VARIANCE</span><span class="kpi-val" style="color:${{areaVarColor}}">${{areaVarLabel}}</span></div>
          <div class="kpi-sep"></div>
          <div class="kpi-item"><span class="kpi-lbl">ITEMS</span><span class="kpi-val">${{agg.mats.size}}</span></div>
          <div class="kpi-sep"></div>
          <div class="kpi-item"><span class="kpi-lbl">TRANS.</span><span class="kpi-val">${{agg.n}}</span></div>
          <div class="kpi-sep"></div>
          <div class="kpi-item"><span class="kpi-lbl">% OF TOTAL</span><span class="kpi-val">${{fmtNum(pct,1)}}%</span></div>
        </div>
        <div class="area-detail-wrap" id="detail-${{cardId}}" style="display:none;">
          <div class="chart-box" style="margin-bottom:14px;"><div id="chart-${{cardId}}" style="min-height:220px;"></div></div>
          <div class="table-scroll"><table class="cdl-table" id="table-${{cardId}}"></table></div>
        </div>
      </div>`;
  }});
  areasGrid.innerHTML = gridHtml || '<div class="no-data">No operational data in this period</div>';

  window._sectionAreaRows[sid] = {{}};
  AREA_ORDER.forEach(a => {{ window._sectionAreaRows[sid][a] = rowsByArea[a]; }});
}}

function renderAll() {{ SECTIONS.forEach(renderSection); }}

function toggleAreaCard(cardId) {{
  const detail = document.getElementById('detail-' + cardId);
  const chev = document.getElementById('chev-' + cardId);
  if (!detail) return;
  const opening = detail.style.display === 'none';
  detail.style.display = opening ? 'block' : 'none';
  chev.style.transform = opening ? 'rotate(90deg)' : 'rotate(0deg)';
  if (opening) renderAreaDetail(cardId);
}}

function renderAreaDetail(cardId) {{
  const [sid, a] = cardId.split('_');
  const rows = (window._sectionAreaRows[sid] && window._sectionAreaRows[sid][a]) || [];

  const byFam = {{}};
  rows.forEach(r => {{
    const famName = DICTS.macrofams[r[5]] || '(N/A)';
    byFam[famName] = (byFam[famName] || 0) + r[10];
  }});
  const famEntries = Object.entries(byFam).sort((x, y) => y[1] - x[1]).slice(0, 10);
  const spec = {{
    data: [{{
      type: 'bar', orientation: 'h',
      x: famEntries.map(e => e[1]).reverse(),
      y: famEntries.map(e => e[0]).reverse(),
      marker: {{ color: AREA_META[a].color }},
      hovertemplate: '%{{y}}<br>\u20ac %{{x:,.0f}}<extra></extra>'
    }}],
    layout: {{ margin: {{ t:10, b:30, l:170, r:20 }}, font: {{ family:'IBM Plex Mono', size:10 }}, yaxis: {{ automargin:true }} }}
  }};
  _areaChartSpecs['chart-' + cardId] = spec;
  Plotly.newPlot('chart-' + cardId, spec.data, themeLayout(spec.layout), {{ responsive:true, displayModeBar:false }});

  const showDate = sid !== 'day';
  const allowVariance = sid !== 'day';
  const periodInfo = allowVariance ? budgetPeriodInfo(sid, currentDateInt) : {{ matches: () => false, actFilter: null, covered: false }};

  const rowBudget = r => {{
    if (!allowVariance || r[14] > LAST_BUDGET_WEEK) return null;
    const bdg = BUDGET_LOOKUP.get(r[14] + '|' + r[2] + '|' + r[4]);
    return (bdg === undefined) ? null : bdg;
  }};
  const rowVarLabel = r => {{ const bdg = rowBudget(r); return bdg === null ? 'N/A' : fmtEUR2(r[10] - bdg); }};
  const rowVarColor = r => {{ const bdg = rowBudget(r); return bdg === null ? 'var(--txt-dim)' : varColor(r[10] - bdg); }};
  const groups = {{}};
  rows.forEach(r => {{
    const key = r[4] + '|' + r[6];
    if (!groups[key]) groups[key] = {{ matIdx: r[4], raggIdx: r[6], val: 0, n: 0, codes: new Set(), rows: [], qtaByUm: {{}} }};
    const g = groups[key];
    const um = DICTS.materials[r[7]][2];
    g.val += r[10]; g.n += 1; g.codes.add(r[7]); g.rows.push(r);
    g.qtaByUm[um] = (g.qtaByUm[um] || 0) + r[9];
  }});

  Object.values(groups).forEach(g => {{
    g.budget = budgetAndVariance(g.rows, periodInfo, b => b[1] === a && b[3] === g.matIdx);
  }});
  const groupList = Object.values(groups).sort((x, y) => y.val - x.val);

  window._groupIndex = window._groupIndex || {{}};
  window._groupIndex[cardId] = {{}};

  let outer = '<thead><tr><th class="cdl-th-name">Category Group</th><th>Unique Codes</th>' +
    '<th>Trans.</th><th class="cdl-th-name">Qty by Unit</th><th>Cost &euro;</th><th>Variance &euro;</th></tr></thead><tbody>';
  groupList.forEach((g, i) => {{
    const gid = cardId + '_g' + i;
    window._groupIndex[cardId][g.matIdx + '|' + g.raggIdx] = gid;
    const label = DICTS.matgroups[g.matIdx] + ' &middot; ' + DICTS.raggmerci[g.raggIdx];
    const qtaLabel = Object.entries(g.qtaByUm).sort((x, y) => y[1] - x[1]).map(([um, q]) => fmtNum(q, 1) + ' ' + um).join(' + ');
    const gVarLabel = g.budget.covered ? fmtEUR2(g.budget.variance) : 'N/A';
    const gVarColor = g.budget.covered ? varColor(g.budget.variance) : 'var(--txt-dim)';
    outer += `<tr class="grp-row" id="grprow-${{gid}}" onclick="toggleGroupRow('${{gid}}')">
      <td class="cdl-name"><span class="grp-arrow" id="grparrow-${{gid}}">&#9654;</span> ${{label}}</td>
      <td>${{g.codes.size}}</td><td>${{g.n}}</td><td class="cdl-name cdl-dim">${{qtaLabel}}</td>
      <td class="cdl-val">${{fmtEUR2(g.val)}}</td><td class="cdl-val" style="color:${{gVarColor}}">${{gVarLabel}}</td>
    </tr>`;
    const innerSorted = [...g.rows].sort((x, y) => y[10] - x[10]);
    const innerThead = '<thead><tr>' + (showDate ? '<th class="cdl-th-name">Date</th>' : '') +
      '<th class="cdl-th-name">Department</th><th class="cdl-th-name">Code</th><th class="cdl-th-name">Description</th>' +
      '<th class="cdl-th-name">User</th><th>Qty</th><th>UM</th><th>Cost &euro;</th><th>Var. &euro;</th><th>&euro;/unit</th></tr></thead>';
    const innerBody = innerSorted.map(r => {{
      const mat = DICTS.materials[r[7]];
      const reparto = DICTS.reparti[r[3]];
      const utente = DICTS.utenti[r[8]];
      const dateCell = showDate ? `<td class="cdl-name">${{fmtDateInt(r[0])}}</td>` : '';
      const eurpz = (r[11] === null || r[11] === undefined) ? '\u2014' : fmtNum(r[11], 2);
      return `<tr>${{dateCell}}<td class="cdl-name cdl-dim">${{reparto}}</td><td class="cdl-name">${{mat[0]}}</td><td class="cdl-name">${{mat[1]}}</td>` +
        `<td class="cdl-name cdl-dim">${{utente}}</td><td class="cdl-val">${{fmtNum(r[9],1)}}</td><td class="cdl-dim">${{mat[2]}}</td>` +
        `<td class="cdl-val">${{fmtEUR2(r[10])}}</td><td class="cdl-val" style="color:${{rowVarColor(r)}}">${{rowVarLabel(r)}}</td><td class="cdl-dim">${{eurpz}}</td></tr>`;
    }}).join('');
    outer += `<tr class="grp-detail-row" id="grpdetail-${{gid}}" style="display:none;"><td colspan="6">
      <table class="cdl-table">${{innerThead}}<tbody>${{innerBody}}</tbody></table>
    </td></tr>`;
  }});
  outer += '</tbody>';

  document.getElementById('table-' + cardId).innerHTML = outer;
}}

function toggleGroupRow(gid) {{
  const row = document.getElementById('grpdetail-' + gid);
  const arrow = document.getElementById('grparrow-' + gid);
  if (!row) return;
  const opening = row.style.display === 'none';
  row.style.display = opening ? 'table-row' : 'none';
  if (arrow) arrow.classList.toggle('open', opening);
}}

const SEARCH_MIN_CHARS = 2;
const SEARCH_LIMIT = 100;
let _searchDebounce = null;

function matchesQuery(r, q) {{
  const mat = DICTS.materials[r[7]];
  const fields = [mat[0], mat[1], DICTS.utenti[r[8]], DICTS.reparti[r[3]], DICTS.cdcs[r[2]], DICTS.matgroups[r[4]], DICTS.raggmerci[r[6]]];
  return fields.some(f => f && f.toLowerCase().includes(q));
}}

function positionSearchResults() {{
  const input = document.getElementById('search-input');
  const box = document.getElementById('search-results');
  const r = input.getBoundingClientRect();
  const maxWidth = Math.min(380, window.innerWidth - 16);
  box.style.width = maxWidth + 'px';
  box.style.top = (r.bottom + 6) + 'px';
  let left = r.right - maxWidth;
  if (left < 8) left = 8;
  box.style.left = left + 'px';
}}

function runSearch(query) {{
  const box = document.getElementById('search-results');
  const q = query.trim().toLowerCase();
  if (q.length < SEARCH_MIN_CHARS) {{ box.classList.remove('open'); box.innerHTML = ''; return; }}

  const matches = [];
  for (let i = ROWS.length - 1; i >= 0 && matches.length < SEARCH_LIMIT; i--) {{
    if (matchesQuery(ROWS[i], q)) matches.push(ROWS[i]);
  }}
  window._searchMatches = matches;
  positionSearchResults();

  if (matches.length === 0) {{
    box.innerHTML = '<div class="search-result-empty">No results for “' + query + '”</div>';
    box.classList.add('open');
    return;
  }}

  box.innerHTML = '<div class="search-results-header">' + matches.length + (matches.length === SEARCH_LIMIT ? '+' : '') +
    ' results — click to view</div>' +
    matches.map((r, idx) => {{
      const mat = DICTS.materials[r[7]];
      const areaName = AREA_META[r[1]].name;
      return `<div class="search-result-item" onclick="jumpToRow(${{idx}})">
        <div class="search-result-main">${{mat[0]}} — ${{mat[1]}}</div>
        <div class="search-result-sub">${{fmtDateInt(r[0])}} · ${{areaName}} · ${{DICTS.utenti[r[8]]}} · ${{fmtEUR2(r[10])}}</div>
      </div>`;
    }}).join('');
  box.classList.add('open');
}}

function jumpToRow(idx) {{
  const r = (window._searchMatches || [])[idx];
  if (!r) return;
  document.getElementById('search-results').classList.remove('open');
  document.getElementById('search-input').value = '';

  currentDateInt = r[0];
  const [y, m, d] = dateIntParts(r[0]);
  document.getElementById('date-picker').value = y + '-' + String(m).padStart(2, '0') + '-' + String(d).padStart(2, '0');
  renderAll();

  const area = r[1];
  const key = r[4] + '|' + r[6];
  let targetRow = null;

  SECTIONS.forEach(sid => {{
    const cardId = sid + '_' + area;
    const cardEl = document.getElementById('card-' + cardId);
    if (!cardEl) return;
    const detail = document.getElementById('detail-' + cardId);
    if (detail.style.display === 'none') toggleAreaCard(cardId);
    else renderAreaDetail(cardId);

    const gid = ((window._groupIndex || {{}})[cardId] || {{}})[key];
    if (!gid) return;
    const grpDetail = document.getElementById('grpdetail-' + gid);
    if (grpDetail && grpDetail.style.display === 'none') toggleGroupRow(gid);
    if (sid === 'day') targetRow = document.getElementById('grprow-' + gid);
  }});

  if (targetRow) {{
    requestAnimationFrame(() => requestAnimationFrame(() => {{
      targetRow.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      targetRow.classList.remove('search-highlight');
      void targetRow.offsetWidth;
      targetRow.classList.add('search-highlight');
    }}));
  }}
}}

document.getElementById('search-input').addEventListener('input', function () {{ clearTimeout(_searchDebounce); const val = this.value; _searchDebounce = setTimeout(() => runSearch(val), 120); }});
document.getElementById('search-input').addEventListener('keydown', function (e) {{ if (e.key === 'Escape') {{ this.value = ''; document.getElementById('search-results').classList.remove('open'); this.blur(); }} }});
document.addEventListener('click', function (e) {{ const wrap = document.querySelector('.search-wrap'); const results = document.getElementById('search-results'); const insideWrap = wrap && wrap.contains(e.target); const insideResults = results && results.contains(e.target); if (!insideWrap && !insideResults) results.classList.remove('open'); }});
window.addEventListener('resize', function () {{ const box = document.getElementById('search-results'); if (box.classList.contains('open')) positionSearchResults(); }});

document.getElementById('date-picker').addEventListener('change', function () {{
  if (!this.value) return;
  currentDateInt = parseInt(this.value.replace(/-/g, ''), 10);
  renderAll();
}});

function toggleTheme() {{
  document.body.classList.toggle('light-mode');
  document.getElementById('btn-theme').innerHTML = document.body.classList.contains('light-mode') ? '&#127183;' : '&#9728;&#65039;';
  Object.keys(_pieSpecs).forEach(id => {{
    const el = document.getElementById(id);
    if (el && el._fullLayout) Plotly.react(id, _pieSpecs[id].data, themeLayout(_pieSpecs[id].layout));
  }});
  Object.keys(_areaChartSpecs).forEach(id => {{
    const el = document.getElementById(id);
    if (el && el._fullLayout) Plotly.react(id, _areaChartSpecs[id].data, themeLayout(_areaChartSpecs[id].layout));
  }});
}}

(function () {{
  const OFFSET = 68;
  const slider = document.getElementById('navSlider');
  function updateActive() {{
    let current = SECTIONS[0];
    SECTIONS.forEach(function (sid) {{ const el = document.getElementById('section-' + sid); if (el && el.getBoundingClientRect().top <= OFFSET + 10) current = sid; }});
    SECTIONS.forEach(function (sid) {{ const link = document.getElementById('nav-' + sid); if (link) link.classList.toggle('active', sid === current); }});
    if (slider) slider.style.transform = 'translateX(' + (SECTIONS.indexOf(current) * 100) + '%)';
  }}
  document.querySelectorAll('.nav-link').forEach(function (link) {{
    link.addEventListener('click', function (e) {{
      const target = document.querySelector(this.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      window.scrollTo({{ top: target.getBoundingClientRect().top + window.scrollY - OFFSET + 2, behavior: 'smooth' }});
    }});
  }});
  window.addEventListener('scroll', updateActive, {{ passive: true }});
  updateActive();
}})();

renderAll();
</script>
</body>
</html>"""

    os.makedirs(latest_dir, exist_ok=True)
    latest_path = os.path.join(latest_dir, LATEST_FILENAME)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    
    print("═" * 65)
    print(f"🚀 DASHBOARD GENERATA CON SUCCESSO!")
    print(f"   🔗 Apri questo file nel browser: {os.path.abspath(latest_path)}")
    print("═" * 65)


if __name__ == "__main__":
    print("═" * 70)
    print(" MATERIALI INDIRETTI — Dashboard (Standalone & Serverless)")
    print("═" * 70)
    
    df, budget_df = load_mock_data()
    dicts, rows, budget_rows, min_date_int, max_date_int = build_payload(df, budget_df)
    
    print(f"\n⏳ Generazione HTML e indicizzazione ricerca in corso...")
    build_dashboard(dicts, rows, budget_rows, min_date_int, max_date_int)
