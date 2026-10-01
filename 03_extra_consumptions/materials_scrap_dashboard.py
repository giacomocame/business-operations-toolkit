"""
╔══════════════════════════════════════════════════════════════════╗
║         INDIRECT MATERIALS & SCRAP VARIANCE DASHBOARD            ║
║         Output: Serverless Offline HTML SPA                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import random
import colorsys
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
#  CONFIGURAZIONE
# ─────────────────────────────────────────────────────────────────

OUTPUT_DIR_LATEST = "./output"
LATEST_FILENAME   = "index.html"

C_RED = "#EF4444"; C_GREEN = "#10B981"; C_SCRAP = "#F59E0B"; C_EP = "#3B82F6"

# ─────────────────────────────────────────────────────────────────
#  1) GENERATORE MOCK DATA (Simulazione Estrazione SAP / ERP)
# ─────────────────────────────────────────────────────────────────

def load_mock_data():
    """
    Genera storici realistici di extraconsumi e scarti.
    Sostituisce la lettura dei file Excel locali per permettere 
    l'esecuzione della demo su qualsiasi computer.
    """
    print("⏳ Generazione mock data (60 giorni di storico varianze)...")
    data = []
    today = date.today()
    start_date = today - timedelta(days=60)
    
    families = {
        "RES-01": "Resine Polimeriche",
        "MET-02": "Componenti Metallici",
        "PKG-03": "Materiale Imballaggio",
        "CHE-04": "Sostanze Chimiche",
        "CON-05": "Materiale di Consumo"
    }
    
    random.seed(42) # Seed fisso per consistenza visiva nella demo
    
    for i in range(61):
        d = start_date + timedelta(days=i)
        if d.weekday() >= 5: continue # Salta i weekend
        
        week_num = d.isocalendar()[1]
        
        # Genera tra 8 e 20 movimenti di magazzino anomali per giorno
        for _ in range(random.randint(8, 20)):
            fam_code = random.choice(list(families.keys()))
            desc = families[fam_code]
            sap_code = f"MAT-{random.randint(1000, 9999)}"
            utente = f"OP-{random.randint(1, 12):02d}"
            
            # Generazione valori realistici
            pure_val = random.uniform(50, 1500)
            scrap_val = pure_val * random.uniform(0.0, 0.20)
            ep_val = pure_val * random.uniform(0.0, 0.10)
            
            # Varianza: positiva (extraconsumo/rosso) o negativa (risparmio/verde)
            var = scrap_val + ep_val + random.uniform(-100, 250)
            
            data.append({
                "FAMIGLIA": fam_code,
                "DESC_FAM": desc,
                "WEEK": f"WK{week_num}",
                "DATA": d,
                "SAP_CODE": sap_code,
                "UTENTE": utente,
                "VARIANZA": var,
                "SCRAP_VAL": scrap_val,
                "EP_VAL": ep_val,
                "PURE_VAL": pure_val,
                "SCRAP_QTY": scrap_val / random.uniform(2, 10),
                "EP_QTY": ep_val / random.uniform(2, 10),
                "NOTE": ""
            })
            
    df = pd.DataFrame(data)
    df["SOURCE_FILE"] = "SAP_EXTRACT_MOCK.xlsx"
    print(f"📊 Righe grezze simulate: {len(df)}")
    return df

# ─────────────────────────────────────────────────────────────────
#  2) PULIZIA E NORMALIZZAZIONE
# ─────────────────────────────────────────────────────────────────

def clean_data(df):
    if df.empty: return df

    def parse_week(v):
        if pd.isna(v): return None
        s = str(v).strip().upper()
        if s.startswith("WK"): s = s[2:].strip()
        try: return int(float(s))
        except: return None
        
    df["WEEK_NUM"] = df["WEEK"].apply(parse_week)
    df["IS_WEEK_AGG"] = df["WEEK"].astype(str).str.strip().str.upper().str.startswith("WK")

    def parse_data(v):
        if pd.isna(v): return pd.NaT
        if isinstance(v, (datetime, date)): return pd.to_datetime(v)
        try: return pd.to_datetime(float(v), unit="D", origin="1899-12-30")
        except: return pd.NaT
        
    df["DATA_DT"] = df["DATA"].apply(parse_data)
    df["IS_DAILY"] = df["DATA_DT"].notna()
    df = df.dropna(subset=["WEEK_NUM"])

    df["DESC_FAM"] = df["DESC_FAM"].astype(str).str.strip()
    df["FAMIGLIA"] = df["FAMIGLIA"].astype(str).str.strip()
    df["SAP_CODE"] = df["SAP_CODE"].fillna("N/D").astype(str).str.strip()
    df["UTENTE"]   = df["UTENTE"].fillna("—").astype(str).str.strip()
    df["NOTE"]     = df["NOTE"].fillna("").astype(str).str.strip()

    for c in ["VARIANZA", "SCRAP_VAL", "EP_VAL", "PURE_VAL", "SCRAP_QTY", "EP_QTY"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    ref_year = int(df.loc[df["IS_DAILY"], "DATA_DT"].dt.year.mode().iloc[0]) if df["IS_DAILY"].any() else datetime.now().year

    def eff_month(row):
        if row["IS_DAILY"]: return row["DATA_DT"].to_period("M")
        try: return pd.Period(date.fromisocalendar(ref_year, int(row["WEEK_NUM"]), 4), freq="M")
        except: return pd.NaT
        
    df["EFF_MONTH"] = df.apply(eff_month, axis=1)

    print(f"✅ Dataset elaborato: {len(df)} righe, {df['DESC_FAM'].nunique()} famiglie.")
    return df

# ─────────────────────────────────────────────────────────────────
#  3) AGGREGAZIONI
# ─────────────────────────────────────────────────────────────────

def family_summary(df_period):
    if df_period.empty:
        return pd.DataFrame(columns=["FAMIGLIA", "DESC_FAM", "VARIANZA", "SCRAP_VAL", "EP_VAL", "PURE_VAL", "SCRAP_QTY", "EP_QTY", "N_RIGHE"])
    g = df_period.groupby("DESC_FAM", as_index=False).agg(
        FAMIGLIA=("FAMIGLIA", lambda s: "/".join(sorted(set(s)))),
        VARIANZA=("VARIANZA", "sum"), SCRAP_VAL=("SCRAP_VAL", "sum"),
        EP_VAL=("EP_VAL", "sum"), PURE_VAL=("PURE_VAL", "sum"),
        SCRAP_QTY=("SCRAP_QTY", "sum"), EP_QTY=("EP_QTY", "sum"),
        N_RIGHE=("VARIANZA", "size"))
    return g.sort_values("VARIANZA", ascending=False).reset_index(drop=True)

def family_detail_rows(df_period, desc_fam):
    d = df_period[df_period["DESC_FAM"] == desc_fam].copy()
    return d.sort_values("VARIANZA", ascending=False)[["FAMIGLIA", "SAP_CODE", "UTENTE", "NOTE", "VARIANZA", "SCRAP_VAL", "EP_VAL", "PURE_VAL", "SCRAP_QTY", "EP_QTY"]]

def trend_day_context(df_all, desc_fam, ref_day, last_day):
    monday = ref_day - pd.Timedelta(days=ref_day.weekday())
    sunday = monday + pd.Timedelta(days=6)
    end = min(sunday, last_day)
    days = pd.date_range(monday, end, freq="D")
    d = df_all[(df_all["DESC_FAM"] == desc_fam) & (df_all["IS_DAILY"])]
    sums = d.groupby(d["DATA_DT"].dt.date)["VARIANZA"].sum() if not d.empty else pd.Series(dtype=float)
    return [dd.strftime("%a %d/%m") for dd in days], [round(float(sums.get(dd.date(), 0.0)), 2) for dd in days]

def trend_week_last5(df_all, desc_fam, avail_weeks, ref_week):
    weeks_upto = [w for w in avail_weeks if w <= ref_week]
    weeks_sel = weeks_upto[-5:] if weeks_upto else []
    d = df_all[df_all["DESC_FAM"] == desc_fam]
    values = []
    for w in weeks_sel:
        week_all = d[d["WEEK_NUM"] == w]
        week_consuntivo = week_all[week_all["IS_WEEK_AGG"]]
        values.append(round(float((week_consuntivo if not week_consuntivo.empty else week_all)["VARIANZA"].sum()), 2))
    return [f"WK{w}" for w in weeks_sel], values

def trend_month_from_jan(df_all, desc_fam, ref_month):
    months = pd.period_range(start=pd.Period(year=ref_month.year, month=1, freq="M"), end=ref_month, freq="M")
    sums = df_all[df_all["DESC_FAM"] == desc_fam].groupby("EFF_MONTH")["VARIANZA"].sum() if not df_all[df_all["DESC_FAM"] == desc_fam].empty else pd.Series(dtype=float)
    return [p.strftime("%b").upper() for p in months], [round(float(sums.get(p, 0.0)), 2) for p in months]

def fam_id(desc_fam): return f"fam_{''.join(ch for ch in str(desc_fam) if ch.isalnum()).lower()}"

def generate_palette(categories):
    n = max(len(categories), 1)
    return {cat: "#{:02x}{:02x}{:02x}".format(int(r*255), int(g*255), int(b*255)) for i, cat in enumerate(sorted(categories)) for r, g, b in [colorsys.hls_to_rgb(i/n, 0.5, 0.55)]}

def make_family_chart(labels, values, color):
    if not labels or all(v == 0 for v in values): return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=labels, y=values, mode="lines+markers", line=dict(color=color, width=3), marker=dict(size=6), hovertemplate="<b>%{x}</b><br>VAR: € %{y:+,.2f}<extra></extra>"))
    fig.add_hline(y=0, line_color="#6B7280", line_width=1)
    fig.update_layout(template="plotly_dark", height=200, showlegend=False, margin=dict(l=40, r=20, t=15, b=25), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(font_family="monospace", font_size=12), xaxis=dict(gridcolor="#374151", tickfont=dict(size=10)), yaxis=dict(gridcolor="#374151", tickfont=dict(size=10), tickformat=",.2f"))
    return fig.to_json()

# ─────────────────────────────────────────────────────────────────
#  4) BUILD DASHBOARD HTML
# ─────────────────────────────────────────────────────────────────

def build_dashboard(latest_dir=OUTPUT_DIR_LATEST):
    df = clean_data(load_mock_data())
    palette = generate_palette(df["DESC_FAM"].unique())

    avail_days   = sorted(df.loc[df["IS_DAILY"], "DATA_DT"].dt.date.unique())
    avail_weeks  = sorted(df["WEEK_NUM"].dropna().unique().astype(int))
    avail_months = sorted(df["EFF_MONTH"].dropna().unique())

    FAM_SUMMARY = {"day": {}, "week": {}, "month": {}}
    FAM_DETAIL  = {"day": {}, "week": {}, "month": {}}
    FAM_TREND   = {"day": {}, "week": {}, "month": {}}

    def register(tab, key, df_period, trend_fn):
        summ = family_summary(df_period)
        FAM_SUMMARY[tab][key] = [
            {"famiglia": r.FAMIGLIA, "desc": r.DESC_FAM, "fid": fam_id(r.DESC_FAM), 
             "var": round(r.VARIANZA, 2), "scrap": round(r.SCRAP_VAL, 2), 
             "ep": round(r.EP_VAL, 2), "pure": round(r.PURE_VAL, 2), 
             "scrap_qty": round(r.SCRAP_QTY, 2), "ep_qty": round(r.EP_QTY, 2), 
             "n": int(r.N_RIGHE)} 
            for r in summ.itertuples()
        ]
        
        det = {}
        trend = {}
        for desc in summ["DESC_FAM"]:
            rows = family_detail_rows(df_period, desc)
            det[fam_id(desc)] = [
                {"famiglia": r.FAMIGLIA, "sap": r.SAP_CODE, "utente": r.UTENTE, 
                 "nota": r.NOTE, "var": round(r.VARIANZA, 2), "scrap": round(r.SCRAP_VAL, 2), 
                 "ep": round(r.EP_VAL, 2), "pure": round(r.PURE_VAL, 2), 
                 "scrap_qty": round(r.SCRAP_QTY, 2), "ep_qty": round(r.EP_QTY, 2)} 
                for r in rows.itertuples()
            ]
            labels, values = trend_fn(desc)
            spec = make_family_chart(labels, values, palette.get(desc, "#6B7280"))
            if spec: 
                trend[fam_id(desc)] = spec
                
        FAM_DETAIL[tab][key] = det
        FAM_TREND[tab][key] = trend

    last_day_ts = pd.Timestamp(avail_days[-1]) if avail_days else None
    
    for d in avail_days: 
        register("day", d.isoformat(), df[(df["IS_DAILY"]) & (df["DATA_DT"].dt.date == d)], lambda desc, d_ts=pd.Timestamp(d): trend_day_context(df, desc, d_ts, last_day_ts))
    for w in avail_weeks: 
        register("week", str(w), df[df["WEEK_NUM"] == w], lambda desc, w=w: trend_week_last5(df, desc, avail_weeks, w))
    for m in avail_months: 
        register("month", str(m), df[df["EFF_MONTH"] == m], lambda desc, m=m: trend_month_from_jan(df, desc, m))

    day_opts   = "".join(f'<option value="{d.isoformat()}"{" selected" if d == avail_days[-1] else ""}>{d.strftime("%d/%m/%Y")}</option>' for d in avail_days)
    week_opts  = "".join(f'<option value="{w}"{" selected" if w == avail_weeks[-1] else ""}>WK{w}</option>' for w in avail_weeks)
    month_opts = "".join(f'<option value="{m}"{" selected" if m == avail_months[-1] else ""}>{m.strftime("%B %Y").upper()}</option>' for m in avail_months)

    html_doc = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Material Variance Dashboard · OMEGA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Baloo+2:wght@600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {{ --bg-main: #0B0D10; --bg-card: rgba(19, 22, 27, 0.72); --bg-input: #14171C; --text-main: #EDEFF2; --text-muted: #8A8F98; --border: rgba(255, 255, 255, 0.09); --accent: #4FD1C5; --danger: #FF5D5D; --warning: #FF7A33; --success: #3DD68C; --pill-bg: rgba(13, 16, 21, 0.75); }}
body.light-mode {{ --bg-main: #F2F0EA; --bg-card: rgba(255, 255, 255, 0.78); --bg-input: #FFFFFF; --text-main: #17181A; --text-muted: #5B5F66; --border: rgba(0, 0, 0, 0.08); --accent: #0F8C82; --danger: #E23D3D; --warning: #C9843E; --success: #1FAE6E; --pill-bg: rgba(255, 255, 255, 0.78); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Space Grotesk', sans-serif; background: radial-gradient(circle at 12% 8%, rgba(79,209,197,.07), transparent 40%), radial-gradient(circle at 88% 92%, rgba(255,122,51,.07), transparent 40%), var(--bg-main); color:var(--text-main); padding:20px; transition:background-color .3s,color .3s; }}
.mono {{ font-family:'IBM Plex Mono', monospace; }}
.header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid var(--border); }}
.header h1 {{ font-family:'Baloo 2', sans-serif; font-size:24px; font-weight:700; letter-spacing:-.01em; }}
.header-meta {{ font-family:'IBM Plex Mono', monospace; font-size:11px; letter-spacing:.06em; color:var(--text-muted); text-align:right; text-transform:uppercase; }}
.nav-container {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; gap:15px; flex-wrap:wrap; }}
.tabs {{ display:flex; gap:2px; background:var(--pill-bg); backdrop-filter:blur(20px); padding:4px; border-radius:999px; border:1px solid var(--border); }}
.tab-btn {{ background:transparent; border:none; color:var(--text-muted); padding:8px 18px; font-family:'IBM Plex Mono', monospace; font-weight:600; font-size:11px; letter-spacing:.06em; text-transform:uppercase; cursor:pointer; border-radius:999px; transition:all .2s ease; }}
.tab-btn.active {{ background:linear-gradient(135deg, #4FD1C5, #FF7A33); color:#0B0D10; }}
.period-select {{ background:var(--pill-bg); backdrop-filter:blur(14px); color:var(--text-main); border:1px solid var(--border); padding:7px 14px; border-radius:999px; font-family:'IBM Plex Mono', monospace; font-size:11px; font-weight:600; cursor:pointer; }}
.theme-btn {{ background:var(--pill-bg); backdrop-filter:blur(14px); border:1px solid var(--border); color:var(--text-main); padding:8px 14px; border-radius:999px; cursor:pointer; font-family:'IBM Plex Mono', monospace; font-size:11px; font-weight:600; transition:all .2s ease; }}
.theme-btn:hover {{ border-color:var(--text-muted); transform:translateY(-1px); }}
.section-title {{ font-family:'IBM Plex Mono', monospace; font-size:11px; font-weight:600; margin:20px 0 12px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.12em; }}
.summary-table {{ width:100%; border-collapse:collapse; background:var(--bg-card); backdrop-filter:blur(14px); border:1px solid var(--border); border-radius:14px; overflow:hidden; font-size:13px; margin-bottom:25px; }}
.summary-table th {{ background:rgba(255,255,255,.03); padding:10px 14px; font-family:'IBM Plex Mono', monospace; font-weight:600; color:var(--text-muted); text-transform:uppercase; font-size:10px; letter-spacing:.1em; text-align:right; }}
.summary-table th:first-child, .summary-table th:nth-child(2) {{ text-align:left; }}
.summary-table td {{ padding:10px 14px; border-top:1px solid var(--border); text-align:right; vertical-align:middle; font-family:'IBM Plex Mono', monospace; font-size:12px; }}
.summary-table td.cell-famiglia {{ text-align:left; color:var(--text-muted); font-weight:600; }}
.summary-table td.cell-desc {{ text-align:left; font-weight:600; font-family:'Space Grotesk', sans-serif; display:flex; align-items:center; gap:8px; }}
.summary-table tr {{ cursor:pointer; }}
.summary-table tr:hover td {{ background:rgba(255,255,255,.03); }}
.fam-dot {{ width:10px; height:10px; border-radius:3px; display:inline-block; flex-shrink:0; }}
.semaforo {{ width:9px; height:9px; border-radius:50%; display:inline-block; flex-shrink:0; box-shadow:0 0 6px rgba(0,0,0,.5); }}
.families-grid {{ display:flex; flex-direction:column; gap:10px; }}
.fam-card {{ background:var(--bg-card); backdrop-filter:blur(14px); border:1px solid var(--border); border-radius:14px; overflow:hidden; transition:border-color .2s ease; }}
.fam-card:hover {{ border-color:var(--text-muted); }}
.fam-header {{ padding:14px 20px; display:grid; grid-template-columns:2.5fr 1.2fr 1.2fr 1.2fr .4fr; align-items:center; cursor:pointer; gap:15px; }}
.fam-header:hover {{ background:rgba(255,255,255,.02); }}
.fam-name-block {{ display:flex; align-items:center; gap:10px; min-width:0; }}
.fam-badge {{ width:12px; height:12px; border-radius:3px; flex-shrink:0; }}
.fam-title {{ font-weight:600; font-size:14px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.fam-val {{ font-family:'IBM Plex Mono', monospace; font-weight:600; font-size:13px; text-align:right; }}
.fam-val.neg {{ color:var(--danger); }}
.fam-val.pos {{ color:var(--success); }}
.arrow {{ text-align:right; color:var(--text-muted); font-weight:bold; transition:transform .2s; }}
.fam-card.expanded .arrow {{ transform:rotate(90deg); }}
.fam-body {{ display:none; padding:18px 20px; border-top:1px solid var(--border); background:rgba(255,255,255,.02); grid-template-columns:1.7fr 1fr; gap:20px; }}
body.light-mode .fam-body {{ background:rgba(0,0,0,.02); }}
.fam-card.expanded .fam-body {{ display:grid; }}
.table-container {{ overflow-x:auto; background:rgba(255,255,255,.02); border:1px solid var(--border); border-radius:10px; max-height:340px; overflow-y:auto; }}
table.detail {{ width:100%; border-collapse:collapse; text-align:left; font-family:'IBM Plex Mono', monospace; font-size:11px; }}
table.detail th {{ background:rgba(255,255,255,.04); padding:8px 10px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:.06em; font-size:9px; border-bottom:1px solid var(--border); position:sticky; top:0; }}
table.detail td {{ padding:7px 10px; border-bottom:1px solid var(--border); }}
table.detail tr:last-child td {{ border-bottom:none; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.no-data {{ padding:30px; text-align:center; font-family:'IBM Plex Mono', monospace; color:var(--text-muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Indirect Materials &amp; Scrap Variance</h1>
    <div class="mono" style="font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--text-muted); margin-top:5px;">PLANT OMEGA · Operations Controlling</div>
  </div>
  <div class="header-meta">
    <div>Generato: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>
  </div>
</div>

<div class="nav-container">
  <div class="tabs">
    <button class="tab-btn active" id="tab-day"   onclick="setTab('day')">DAILY</button>
    <button class="tab-btn"        id="tab-week"  onclick="setTab('week')">WEEKLY</button>
    <button class="tab-btn"        id="tab-month" onclick="setTab('month')">MONTHLY</button>
  </div>
  <div style="display:flex; gap:10px; align-items:center;">
    <select id="sel-day"   class="period-select" onchange="onPeriodChange()">{day_opts}</select>
    <select id="sel-week"  class="period-select" style="display:none" onchange="onPeriodChange()">{week_opts}</select>
    <select id="sel-month" class="period-select" style="display:none" onchange="onPeriodChange()">{month_opts}</select>
    <button class="theme-btn" onclick="toggleTheme()">🌓 Tema</button>
  </div>
</div>

<div class="section-title">Riepilogo per Categoria — ordinato per Varianza (decrescente)</div>
<div class="table-container" style="max-height:none; margin-bottom:25px;">
<table class="summary-table" id="summary-table">
  <thead><tr>
    <th>Codice</th><th>Descrizione Categoria</th><th>Varianza €</th><th>Scarti €</th>
    <th>Extra Pick €</th><th>Consumo Puro €</th><th>Qty Scarti</th><th>Qty EP</th><th>Movimenti</th>
  </tr></thead>
  <tbody id="summary-tbody"></tbody>
</table>
</div>

<div class="section-title">Dettaglio per Categoria — clicca per espandere le righe</div>
<div class="families-grid" id="families-grid"></div>

<script>
const FAM_SUMMARY = {json.dumps(FAM_SUMMARY)};
const FAM_DETAIL  = {json.dumps(FAM_DETAIL)};
const FAM_TREND   = {json.dumps(FAM_TREND)};
const PALETTE     = {json.dumps(palette)};

var currentTab = 'day';
var currentKey = '{avail_days[-1].isoformat() if avail_days else ""}';
const DEFAULTS = {{ day: currentKey, week: '{avail_weeks[-1] if avail_weeks else ""}', month: '{avail_months[-1] if avail_months else ""}' }};
const expandedCards = new Set();

function fmt(v)    {{ return '€ ' + Number(v).toLocaleString('it-IT', {{minimumFractionDigits:2, maximumFractionDigits:2}}); }}
function fmtQty(v) {{ return Number(v).toLocaleString('it-IT', {{minimumFractionDigits:2, maximumFractionDigits:2}}); }}

function setTab(tabName) {{
  currentTab = tabName;
  currentKey = DEFAULTS[tabName];
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + tabName).classList.add('active');
  ['day','week','month'].forEach(t => document.getElementById('sel-' + t).style.display = (t === tabName ? 'inline-block' : 'none'));
  document.getElementById('sel-' + tabName).value = currentKey;
  expandedCards.clear();
  render();
}}

function onPeriodChange() {{
  currentKey = document.getElementById('sel-' + currentTab).value;
  expandedCards.clear();
  render();
}}

function render() {{
  const famList = (FAM_SUMMARY[currentTab] || {{}})[currentKey] || [];
  let summaryHtml = '';
  
  famList.forEach(f => {{
    const vClass = f.var > 0 ? 'fam-val neg' : 'fam-val pos';
    const color = PALETTE[f.desc] || '#6B7280';
    const semColor = f.var > 0 ? 'var(--danger)' : 'var(--success)';
    summaryHtml += `<tr onclick="toggleCard('${{f.fid}}')">
      <td class="cell-famiglia">${{f.famiglia}}</td>
      <td class="cell-desc"><span class="semaforo" style="background:${{semColor}}" title="${{f.var > 0 ? 'Extraconsumo' : 'Risparmio'}}"></span><span class="fam-dot" style="background:${{color}}"></span>${{f.desc}}</td>
      <td class="num"><span class="${{vClass}}">${{f.var > 0 ? '+' : ''}}${{fmt(f.var)}}</span></td>
      <td class="num">${{fmt(f.scrap)}}</td>
      <td class="num">${{fmt(f.ep)}}</td>
      <td class="num">${{fmt(f.pure)}}</td>
      <td class="num">${{fmtQty(f.scrap_qty)}}</td>
      <td class="num">${{fmtQty(f.ep_qty)}}</td>
      <td class="num">${{f.n}}</td>
    </tr>`;
  }});
  document.getElementById('summary-tbody').innerHTML = summaryHtml || '<tr><td colspan="9" class="no-data">Nessun movimento nel periodo</td></tr>';

  let gridHtml = '';
  famList.forEach(f => {{
    const color = PALETTE[f.desc] || '#6B7280';
    const isOpen = expandedCards.has(f.fid);
    const vClass = f.var > 0 ? 'fam-val neg' : 'fam-val pos';
    gridHtml += `<div class="fam-card ${{isOpen ? 'expanded' : ''}}" id="card_${{f.fid}}">
      <div class="fam-header" onclick="toggleCard('${{f.fid}}')">
        <div class="fam-name-block"><div class="fam-badge" style="background:${{color}}"></div>
          <div class="fam-title" title="${{f.desc}}">${{f.desc}}</div></div>
        <div class="${{vClass}}">${{f.var > 0 ? '+' : ''}}${{fmt(f.var)}}</div>
        <div class="fam-val" style="color:var(--text-muted)">${{fmt(f.scrap)}}</div>
        <div class="fam-val" style="color:var(--text-muted)">${{fmt(f.ep)}}</div>
        <div class="arrow">▶</div>
      </div>
      <div class="fam-body">
        <div class="table-container">
          <table class="detail">
            <thead><tr>
              <th>Codice Fam.</th><th>Codice SAP</th><th>Utente/Operatore</th><th>Note</th>
              <th class="num">Varianza €</th><th class="num">Scarti €</th><th class="num">Extra Pick €</th>
              <th class="num">Consumo Puro €</th><th class="num">Qty Scarti</th><th class="num">Qty EP</th>
            </tr></thead>
            <tbody>${{renderDetailRows(f.fid)}}</tbody>
          </table>
        </div>
        <div id="chart-${{f.fid}}" style="min-height:200px;"></div>
      </div>
    </div>`;
  }});
  document.getElementById('families-grid').innerHTML = gridHtml || '<div class="no-data">Nessuna categoria con movimenti nel periodo selezionato</div>';

  expandedCards.forEach(fid => renderChart(fid));
}}

function renderDetailRows(fid) {{
  const rows = ((FAM_DETAIL[currentTab] || {{}})[currentKey] || {{}})[fid] || [];
  if (!rows.length) return '<tr><td colspan="10" class="no-data">Nessun movimento</td></tr>';
  return rows.map(r => {{
    const vClass = r.var > 0 ? 'fam-val neg' : 'fam-val pos';
    return `<tr>
      <td>${{r.famiglia}}</td>
      <td style="font-family:monospace">${{r.sap}}</td>
      <td>${{r.utente}}</td>
      <td style="color:var(--text-muted); font-size:11px;">${{r.nota || '—'}}</td>
      <td class="num"><span class="${{vClass}}">${{r.var > 0 ? '+' : ''}}${{fmt(r.var)}}</span></td>
      <td class="num">${{fmt(r.scrap)}}</td>
      <td class="num">${{fmt(r.ep)}}</td>
      <td class="num">${{fmt(r.pure)}}</td>
      <td class="num">${{fmtQty(r.scrap_qty)}}</td>
      <td class="num">${{fmtQty(r.ep_qty)}}</td>
    </tr>`;
  }}).join('');
}}

function toggleCard(fid) {{
  const card = document.getElementById('card_' + fid);
  if (!card) return;
  if (expandedCards.has(fid)) {{
    expandedCards.delete(fid); card.classList.remove('expanded');
  }} else {{
    expandedCards.add(fid); card.classList.add('expanded'); renderChart(fid);
  }}
}}

function renderChart(fid) {{
  const spec = ((FAM_TREND[currentTab] || {{}})[currentKey] || {{}})[fid];
  const el = document.getElementById('chart-' + fid);
  if (!el) return;
  if (spec) {{
    const parsed = JSON.parse(spec);
    Plotly.newPlot('chart-' + fid, parsed.data, parsed.layout, {{responsive:true, displayModeBar:false}});
  }} else {{
    el.innerHTML = '<div class="no-data">Trend non disponibile per questo periodo</div>';
  }}
}}

function toggleTheme() {{ document.body.classList.toggle('light-mode'); }}

setTab('day');
</script>
</body>
</html>"""

    os.makedirs(latest_dir, exist_ok=True)
    out_path = os.path.join(latest_dir, LATEST_FILENAME)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print("═" * 65)
    print(f"🚀 DASHBOARD GENERATA CON SUCCESSO!")
    print(f"   🔗 Apri questo file nel browser: {os.path.abspath(out_path)}")
    print("═" * 65)

if __name__ == "__main__":
    build_dashboard()
