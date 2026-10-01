"""
╔══════════════════════════════════════════════════════════════════╗
║         OPERATIONS EFFICIENCY DASHBOARD — STABILIMENTO OMEGA     ║
║         Output: HTML interattivo SPA (Offline, Nessun Server)    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, json, random
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────

OUTPUT_DIR_LATEST  = "./output"
LATEST_FILENAME    = "index.html"

# ─────────────────────────────────────────────────────────────────
#  COSTANTI
# ─────────────────────────────────────────────────────────────────

AREE = ["Lavorazione", "Assemblaggio", "Trattamento", "Imballaggio"]
COL1_TO_AREA = {
    "LAVORAZIONE":  "Lavorazione",
    "ASSEMBLAGGIO": "Assemblaggio",
    "TRATTAMENTO":  "Trattamento",
    "IMBALLAGGIO":  "Imballaggio",
}
AREA_COLORS = {
    "Lavorazione":  "#4FD1C5",
    "Assemblaggio": "#FF9F45",
    "Trattamento":  "#3DD68C",
    "Imballaggio":  "#B98CFF",
}
AREA_IDS = {a: a.lower().replace(" ", "_") for a in AREE}

OFF_STD = 0; OFF_ACT = 1; OFF_BDG = 2; OFF_EFF = 4; OFF_VAR = 5
C_STD = "#4FD1C5"; C_ACT = "#FF9F45"
C_GREEN = "#3DD68C"; C_RED = "#FF5D5D"

MESI_IT = ["GENNAIO","FEBBRAIO","MARZO","APRILE","MAGGIO","GIUGNO",
           "LUGLIO","AGOSTO","SETTEMBRE","OTTOBRE","NOVEMBRE","DICEMBRE"]

# ─────────────────────────────────────────────────────────────────
#  HELPERS GENERICI
# ─────────────────────────────────────────────────────────────────

def _cdl_area(row):
    v = str(row[1]).strip() if row[1] else ""
    return COL1_TO_AREA.get(v.upper(), v if v in AREE else None)

def _is_subtotal(row):
    return (row[0] is None and str(row[1]).strip() == ""
            and isinstance(row[3], str) and row[3].strip() in AREE)

def _is_cdl(row):
    v = row[0]
    return isinstance(v, str) and v.strip() not in ("", "-", " ", "None")

def _f(v):
    try:
        f = float(v); return f if f != 0.0 else None
    except: return None

def _fz(v):
    return _f(v) or 0.0

def plant_bdg_from_total_row(data_rows, ci):
    for row in data_rows:
        if isinstance(row[3], str) and row[3].strip() == PLANT_TOTAL_ROW:
            if ci + OFF_BDG < len(row):
                return _f(row[ci + OFF_BDG])
    return None

ADD_PED_ROWS = {
    "Scarti Lavorazione (Setup)":       "Lavorazione",
    "Scarti Lavorazione (Tolleranza)":  "Lavorazione",
    "Scarti Trattamento Superficiale":  "Trattamento",
}

ADD_PED_SERIES = {
    "Scarti Lavorazione (Setup)":       "Setup (Lavorazione)",
    "Scarti Lavorazione (Tolleranza)":  "Tolleranza (Lavorazione)",
    "Scarti Trattamento Superficiale":  "Rework (Trattamento)",
}
ADD_PED_ORDER  = ["Setup (Lavorazione)", "Tolleranza (Lavorazione)", "Rework (Trattamento)"]
ADD_PED_COLORS = {
    "Setup (Lavorazione)":       "#4FD1C5",
    "Tolleranza (Lavorazione)":  "#FF9F45",
    "Rework (Trattamento)":      "#B98CFF",
}
ADD_PED_TOTAL_LABEL = "TOTALE Ore Scarto"
ADD_PED_TOTAL_COLOR = "#F2F0EA"

PLANT_TOTAL_ROW   = "TOTALE STABILIMENTO OMEGA"
PLANT_TOTAL_LABEL = "TOTALE STABILIMENTO"
PLANT_TOTAL_COLOR = ADD_PED_TOTAL_COLOR

def _extract_add_ped(data_rows, ci):
    out = {a: [] for a in AREE}
    for row in data_rows:
        if ci + OFF_VAR >= len(row): continue
        descr = str(row[3]).strip() if row[3] else ""
        area = ADD_PED_ROWS.get(descr)
        if not area: continue
        act = _fz(row[ci + OFF_ACT])
        var = int(round(_fz(row[ci + OFF_VAR])))
        if act == 0 and var == 0: continue
        out[area].append({
            "descr": descr, "std": None, "act": act,
            "eff": None, "var": var, "addebito": True,
        })
    return out

# ─────────────────────────────────────────────────────────────────
#  GENERATORE DATI IN-MEMORY 
# ─────────────────────────────────────────────────────────────────

def load_dbd():
    print("⏳ Generazione storica mock data (60 giorni)...")
    dates_cols = []
    data_rows = []
    
    cdl_setup = {
        "Lavorazione":  ["Tornio CNC Alpha", "Tornio CNC Beta", "Fresa a 5 Assi", "Taglio Laser"],
        "Assemblaggio": ["Linea Automatica 1", "Linea Automatica 2"],
        "Trattamento":  ["Bagno Galvanico", "Forno Ricottura", "Sabbiatrice"],
        "Imballaggio":  ["Inscatolatrice Rapida", "Pallettizzatore Robot"]
    }
    
    for area, cdls in cdl_setup.items():
        data_rows.append([None, "", "", area]) # Subtotale
        for i, cdl in enumerate(cdls):
            data_rows.append([f"CDL-{area[:3].upper()}{i+1}", area, "", cdl])
            
    for rw in ADD_PED_ROWS.keys():
        data_rows.append([None, "", "", rw])
        
    data_rows.append([None, "", "", PLANT_TOTAL_ROW])
    
    for r in data_rows:
        while len(r) < 20: r.append(None)
            
    today = date.today()
    start_date = today - timedelta(days=60)
    current_ci = 20
    
    random.seed()
    
    for i in range(61):
        d = start_date + timedelta(days=i)
        if d.weekday() >= 5: continue 
        
        ts = pd.Timestamp(d)
        dates_cols.append((ts, current_ci))
        
        for r in data_rows:
            desc = str(r[3])
            if desc in AREE or desc == PLANT_TOTAL_ROW:
                r.extend([0, 0, 0.85, 0, 0, 0, 0, 0, 0])
            elif "Scarti" in desc:
                act = random.uniform(2, 12)
                var = act * 45 
                r.extend([0, act, 0.85, 0, 0, var, 0, 0, 0])
            else:
                std = random.uniform(50, 200)
                simulated_eff = random.uniform(0.78, 0.92)
                act = std / simulated_eff
                eff = simulated_eff
                var = (act - std) * 45 
                bdg_pct = 0.85
                bdg_h = std / bdg_pct # FIX: Calcolo ore budget base
                r.extend([std, act, bdg_pct, bdg_h, eff, var, 0, 0, 0])
                
        # FIX: Consolidamento matematico che include bdg_h all'indice 3
        tot_std = tot_act = tot_var = tot_bdgh = 0
        for area in AREE:
            a_std = sum(r[current_ci+OFF_STD] for r in data_rows if r[1] == area and r[0] is not None)
            a_act = sum(r[current_ci+OFF_ACT] for r in data_rows if r[1] == area and r[0] is not None)
            a_var = sum(r[current_ci+OFF_VAR] for r in data_rows if r[1] == area and r[0] is not None)
            a_bdgh = sum(r[current_ci+3] for r in data_rows if r[1] == area and r[0] is not None)
            for r in data_rows:
                if r[3] == area and _is_subtotal(r):
                    r[current_ci+OFF_STD] = a_std
                    r[current_ci+OFF_ACT] = a_act
                    r[current_ci+OFF_VAR] = a_var
                    r[current_ci+3]       = a_bdgh
                    r[current_ci+OFF_EFF] = a_std / a_act if a_act else 0
                    r[current_ci+OFF_BDG] = a_std / a_bdgh if a_bdgh else 0.85
                    tot_std += a_std; tot_act += a_act; tot_var += a_var; tot_bdgh += a_bdgh
                    
        rw_act = sum(r[current_ci+OFF_ACT] for r in data_rows if "Scarti" in str(r[3]))
        rw_var = sum(r[current_ci+OFF_VAR] for r in data_rows if "Scarti" in str(r[3]))
        tot_act += rw_act; tot_var += rw_var
        
        for r in data_rows:
            if r[3] == PLANT_TOTAL_ROW:
                r[current_ci+OFF_STD] = tot_std
                r[current_ci+OFF_ACT] = tot_act
                r[current_ci+OFF_VAR] = tot_var
                r[current_ci+3]       = tot_bdgh
                r[current_ci+OFF_EFF] = tot_std / tot_act if tot_act else 0
                r[current_ci+OFF_BDG] = tot_std / tot_bdgh if tot_bdgh else 0.85
                
        current_ci += 9

    return dates_cols, data_rows

def extract_day(data_rows, ci):
    areas = []
    cdl_by_area = {a: [] for a in AREE}
    for row in data_rows:
        if _is_subtotal(row):
            areas.append({
                "area": row[3].strip(),
                "std":  _fz(row[ci+OFF_STD]), "act":  _fz(row[ci+OFF_ACT]),
                "bdg":  _f (row[ci+OFF_BDG]), "eff":  _f (row[ci+OFF_EFF]),
                "var":  int(round(_fz(row[ci+OFF_VAR]))),
            })
        elif _is_cdl(row):
            area = _cdl_area(row)
            if not area: continue
            std  = _fz(row[ci+OFF_STD]); act = _fz(row[ci+OFF_ACT])
            descr = str(row[3]).strip()[:35] if row[3] else ""
            if descr and (std > 0 or act > 0):
                cdl_by_area[area].append({
                    "descr": descr, "std": std, "act": act,
                    "eff": _f(row[ci+OFF_EFF]), "var": int(round(_fz(row[ci+OFF_VAR]))),
                })
    add_ped = _extract_add_ped(data_rows, ci)
    for a in ("Lavorazione", "Trattamento"):
        cdl_by_area[a].extend(add_ped[a])
    return pd.DataFrame(areas), cdl_by_area

def _trend_dfs_from_cols(data_rows, valid_cols):
    area_recs = []; cdl_recs = []
    for ts, ci in valid_cols:
        for row in data_rows:
            if _is_subtotal(row):
                eff = _f(row[ci+OFF_EFF])
                if eff is not None:
                    area_recs.append({
                        "date": ts, "area": row[3].strip(),
                        "eff":  round(eff*100, 2), "var":  int(round(_fz(row[ci+OFF_VAR]))),
                        "std":  int(round(_fz(row[ci+OFF_STD]))), "act":  int(round(_fz(row[ci+OFF_ACT]))),
                    })
            elif _is_cdl(row):
                area = _cdl_area(row)
                if not area: continue
                eff = _f(row[ci+OFF_EFF])
                descr = str(row[3]).strip()[:35] if row[3] else ""
                if descr and eff is not None:
                    cdl_recs.append({
                        "date": ts, "area": area, "descr": descr,
                        "eff":  round(eff*100, 2), "var":  int(round(_fz(row[ci+OFF_VAR]))),
                        "std":  int(round(_fz(row[ci+OFF_STD]))), "act":  int(round(_fz(row[ci+OFF_ACT]))),
                    })
    return pd.DataFrame(area_recs), pd.DataFrame(cdl_recs)

def extract_trend_week_to_date(data_rows, dates_cols, target_date):
    monday = target_date - timedelta(days=target_date.weekday())
    valid = [(ts, ci) for ts, ci in dates_cols if monday <= ts.date() <= target_date and any(_fz(r[ci+OFF_STD]) > 0 for r in data_rows if _is_cdl(r))]
    valid.sort(key=lambda x: x[0])
    return _trend_dfs_from_cols(data_rows, valid)

def _valid_week_to_date_cols(data_rows, dates_cols, target_date):
    monday = target_date - timedelta(days=target_date.weekday())
    valid = [(ts, ci) for ts, ci in dates_cols if monday <= ts.date() <= target_date and any(_fz(r[ci+OFF_STD]) > 0 for r in data_rows if _is_cdl(r))]
    valid.sort(key=lambda x: x[0])
    return valid

def _extract_add_ped_trend(data_rows, cols_labels):
    recs = []
    for label, ci in cols_labels:
        for row in data_rows:
            if ci + OFF_VAR >= len(row): continue
            descr = str(row[3]).strip() if row[3] else ""
            serie = ADD_PED_SERIES.get(descr)
            if not serie: continue
            recs.append({"label": label, "serie": serie, "act": _fz(row[ci+OFF_ACT]), "var": int(round(_fz(row[ci+OFF_VAR])))})
    return pd.DataFrame(recs, columns=["label", "serie", "act", "var"])

def _extract_total_trend(data_rows, cols_labels):
    recs = []
    row = next((r for r in data_rows if isinstance(r[3], str) and r[3].strip() == PLANT_TOTAL_ROW), None)
    if row is not None:
        for label, ci in cols_labels:
            if ci + OFF_VAR >= len(row): continue
            eff = _f(row[ci + OFF_EFF])
            if eff is None: continue
            recs.append({"label": label, "eff": round(eff*100, 2), "std": int(round(_fz(row[ci+OFF_STD]))), "act": int(round(_fz(row[ci+OFF_ACT]))), "var": int(round(_fz(row[ci+OFF_VAR])))})
    return pd.DataFrame(recs, columns=["label", "eff", "std", "act", "var"])

# ─────────────────────────────────────────────────────────────────
#  GRAFICI PLOTLY 
# ─────────────────────────────────────────────────────────────────

def _make_section_charts(df_area, df_trend, trend_labels, df_cdl_trend, section_id, trend_title, df_total=None):
    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.30, 0.70],
        subplot_titles=["EFF % PER AREA", trend_title], horizontal_spacing=0.12,
    )
    df_a = df_area[df_area["area"].isin(AREE)].copy()
    df_a["area"] = pd.Categorical(df_a["area"], categories=AREE[::-1], ordered=True)
    df_a = df_a.sort_values("area")
    df_a["eff_pct"] = df_a["eff"].fillna(0) * 100
    df_a["bdg_pct"] = df_a["bdg"].fillna(0) * 100
    dot_colors = [C_GREEN if row["eff_pct"] >= row["bdg_pct"] else C_RED for _, row in df_a.iterrows()]

    fig.add_trace(go.Scatter(
        x=[0]*len(df_a), y=df_a["area"], mode="markers+text",
        marker=dict(size=32, color=dot_colors, opacity=0.9, line=dict(width=2, color="rgba(255,255,255,0.35)")),
        text=df_a.apply(lambda r: f"  {r['eff_pct']:.1f}%  bdg {r['bdg_pct']:.1f}%", axis=1),
        textposition="middle right", textfont=dict(size=12, family="monospace"),
        customdata=df_a["area"].tolist(),
        hovertemplate="<b>%{y}</b><br>%{text}<br><i>Clicca per il dettaglio</i><extra></extra>",
        showlegend=False,
    ), row=1, col=1)
    
    fig.update_xaxes(range=[-1, 6], showticklabels=False, showgrid=False, zeroline=False, row=1, col=1)
    fig.update_yaxes(tickfont=dict(size=12), showgrid=False, row=1, col=1)

    if not df_trend.empty:
        for area in AREE:
            sub = df_trend[df_trend["area"] == area]
            if sub.empty: continue
            cd_data = (sub[["var", "std", "act"]].values.tolist() if all(c in sub.columns for c in ["var", "std", "act"]) else [[0, 0, 0]]*len(sub))
            fig.add_trace(go.Scatter(
                x=sub["label"], y=sub["eff"], mode="lines+markers", name=area,
                line=dict(color=AREA_COLORS[area], width=3), marker=dict(size=7), customdata=cd_data,
                hovertemplate=(f"<b>{area}</b><br>%{{x}}<br>EFF: <b>%{{y:.1f}}%</b><br>STD: <b>%{{customdata[1]:,.0f}} h</b><br>ACT: <b>%{{customdata[2]:,.0f}} h</b><br>VAR: <b>€ %{{customdata[0]:+,.0f}}</b><extra></extra>"),
            ), row=1, col=2)
            
        if df_total is not None and not df_total.empty:
            fig.add_trace(go.Scatter(
                x=df_total["label"], y=df_total["eff"], mode="lines+markers", name=PLANT_TOTAL_LABEL,
                line=dict(color=PLANT_TOTAL_COLOR, width=2.5, dash="dash"), marker=dict(size=8, symbol="diamond"), customdata=df_total[["var", "std", "act"]].values.tolist(),
                hovertemplate=(f"<b>{PLANT_TOTAL_LABEL}</b><br>%{{x}}<br>EFF: <b>%{{y:.1f}}%</b><br>STD: <b>%{{customdata[1]:,.0f}} h</b><br>ACT: <b>%{{customdata[2]:,.0f}} h</b><br>VAR: <b>€ %{{customdata[0]:+,.0f}}</b><extra></extra>"),
            ), row=1, col=2)
            
        fig.update_xaxes(tickangle=-40, tickfont=dict(size=11), row=1, col=2)
        fig.update_yaxes(ticksuffix="%", tickfont=dict(size=12), row=1, col=2)

    fig.update_layout(
        height=340, margin=dict(t=45, b=30, l=55, r=160), font=dict(family="monospace", size=13),
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=12), tracegroupgap=2),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(font_family="monospace", font_size=13),
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, row=1, col=2)
    fig.update_yaxes(showgrid=True, gridwidth=1, row=1, col=2)
    overview_json = fig.to_json()

    import colorsys
    def area_palette(base_hex, n):
        base_hex = base_hex.lstrip("#")
        r, g, b = [int(base_hex[i:i+2], 16)/255 for i in (0, 2, 4)]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        colors = []
        for i in range(n):
            hue = (h + i * 0.13) % 1.0
            sat = max(0.4, s - i * 0.05); val = min(1.0, v + i * 0.08)
            r2, g2, b2 = colorsys.hsv_to_rgb(hue, sat, val)
            colors.append("#{:02x}{:02x}{:02x}".format(int(r2*255), int(g2*255), int(b2*255)))
        return colors

    area_charts = {}
    if df_cdl_trend is None or df_cdl_trend.empty: return overview_json, area_charts
    
    labels = list(dict.fromkeys((df_trend["label"].tolist() if df_trend is not None and not df_trend.empty else []) + df_cdl_trend["label"].tolist()))

    def _aligned(sub):
        s = sub.drop_duplicates("label").set_index("label").reindex(labels)
        out = {}
        for col in ("eff", "std", "act", "var"):
            out[col] = [None if pd.isna(v) else (round(float(v), 2) if col == "eff" else int(v)) for v in s[col].tolist()]
        return out

    for area in AREE:
        df = df_cdl_trend[df_cdl_trend["area"] == area]
        if df.empty: continue
        cdl_names = df["descr"].unique().tolist()
        palette = area_palette(AREA_COLORS[area], len(cdl_names))
        row_bdg = df_area[df_area["area"] == area]
        bdg_val = row_bdg.iloc[0]["bdg"] if not row_bdg.empty else None
        y_line  = round(bdg_val * 100, 1) if bdg_val is not None and pd.notna(bdg_val) else 40.0
        series = [{"name": n, "color": palette[i], **_aligned(df[df["descr"] == n])} for i, n in enumerate(cdl_names)]
        sub_tot = (df_trend[df_trend["area"] == area] if df_trend is not None and not df_trend.empty else pd.DataFrame())
        area_charts[area] = {
            "area": area, "color": AREA_COLORS[area], "labels": labels, "bdg": y_line,
            "total": _aligned(sub_tot) if not sub_tot.empty else None, "series": series,
        }

    return overview_json, area_charts

def _sparkline_svg(eff, bdg, color, w=96, h=24):
    pts = [(i, v) for i, v in enumerate(eff) if v is not None]
    if len(pts) < 2: return '<span class="spark-empty">—</span>'
    vals = [v for _, v in pts] + [bdg]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9: hi = lo + 1
    n = max(len(eff) - 1, 1); pad = 3
    X = lambda i: pad + i * (w - 2*pad) / n
    Y = lambda v: pad + (hi - v) * (h - 2*pad) / (hi - lo)
    path = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in pts)
    li, lv = pts[-1]
    dot = C_GREEN if lv >= bdg else C_RED
    return (
        f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<line x1="0" x2="{w}" y1="{Y(bdg):.1f}" y2="{Y(bdg):.1f}" class="spark-bdg"/>'
        f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{X(li):.1f}" cy="{Y(lv):.1f}" r="2.6" fill="{dot}"/>'
        f'</svg>'
    )

def _make_addped_line_chart(df_trend, hline_y=None):
    if df_trend is None or df_trend.empty: return None
    labels_order = list(dict.fromkeys(df_trend["label"].tolist()))
    fig = go.Figure()
    for serie in ADD_PED_ORDER:
        sub = df_trend[df_trend["serie"] == serie]
        if sub.empty: continue
        sub = sub.set_index("label").reindex(labels_order).fillna(0).reset_index()
        fig.add_trace(go.Scatter(
            x=sub["label"], y=sub["act"], mode="lines+markers", name=serie,
            line=dict(color=ADD_PED_COLORS[serie], width=2.5), marker=dict(size=7), customdata=sub["var"],
            hovertemplate=(f"<b>{serie}</b><br>%{{x}}<br>ACT: <b>%{{y:,.0f}} h</b><br>VAR: <b>€ %{{customdata:+,.0f}}</b><extra></extra>"),
        ))
    tot = (df_trend.groupby("label", sort=False)[["act", "var"]].sum().reindex(labels_order).fillna(0).reset_index())
    fig.add_trace(go.Scatter(
        x=tot["label"], y=tot["act"], mode="lines+markers", name=ADD_PED_TOTAL_LABEL,
        line=dict(color=ADD_PED_TOTAL_COLOR, width=2.5, dash="dash"), marker=dict(size=7, symbol="diamond"), customdata=tot["var"],
        hovertemplate=(f"<b>{ADD_PED_TOTAL_LABEL}</b><br>%{{x}}<br>ACT: <b>%{{y:,.0f}} h</b><br>VAR: <b>€ %{{customdata:+,.0f}}</b><extra></extra>"),
    ))
    if hline_y is not None:
        fig.add_hline(y=hline_y, line_color="#FFFFFF", line_width=1, layer="above")
    fig.update_layout(
        height=225, margin=dict(t=15, b=60, l=50, r=185), font=dict(family="monospace", size=12),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02, font=dict(size=10.5), tracegroupgap=3),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(font_family="monospace", font_size=13),
        xaxis=dict(tickangle=-30, tickfont=dict(size=11), showgrid=True, gridwidth=1, automargin=True),
        yaxis=dict(ticksuffix=" h", tickfont=dict(size=12), showgrid=True, gridwidth=1, automargin=True),
    )
    return fig.to_json()

# ─────────────────────────────────────────────────────────────────
#  COSTRUZIONE HTML - SEZIONI
# ─────────────────────────────────────────────────────────────────

ADDPED_PERIOD_META = [
    ("day",   "\U0001f4c5", "DAILY"), ("week",  "\U0001f4c6", "WEEKLY"),
    ("month", "\U0001f5d3", "MONTHLY"), ("ytd",   "\U0001f4ca", "YTD"),
]

def _build_addped_block(pid, icon, label, subtitle, df_trend):
    chart_id = f"addped-chart-{pid}"
    if df_trend is None or df_trend.empty:
        body = '<div class="addped-empty">Nessun dato disponibile</div>'
        kpi_html = ""
    else:
        last_label = df_trend["label"].iloc[-1]
        last = df_trend[df_trend["label"] == last_label]
        tot_act = last["act"].sum()
        tot_var = int(round(last["var"].sum()))
        var_color = C_RED if tot_var > 0 else C_GREEN # Extra costo = ROSSO
        body = f'<div id="{chart_id}" class="addped-chart-container"></div>'
        kpi_html = (
            f'<span class="addped-block-kpi">ULTIMO: {last_label}'
            f' &nbsp;·&nbsp; ACT <b style="color:{C_ACT}">{tot_act:,.0f} h</b>'
            f' &nbsp;·&nbsp; VAR <b style="color:{var_color}">\u20ac +{tot_var:,.0f}</b></span>'
        )
    return (
        f'<div class="addped-block" id="addped-block-{pid}">'
        f'  <div class="addped-block-header"><span class="addped-block-icon">{icon}</span><span class="addped-block-title">{label}</span>{kpi_html}</div>'
        f'  <div class="addped-block-subtitle">{subtitle}</div>{body}</div>'
    )

def _build_area_table(df_area):
    def _cell_eff(val, bdg): return f'<td class="at-val" style="color:{C_GREEN if val >= bdg else C_RED}">{val:.1f}%</td>'
    # Costo in eccesso (var > 0) è ROSSO, risparmio (var < 0) è VERDE
    def _cell_var(val): return f'<td class="at-val" style="color:{C_RED if val > 0 else C_GREEN}">€ {"+" if val > 0 else ""}{val:,.0f}</td>'
    
    def area_block(area):
        row = df_area[df_area["area"] == area]
        if row.empty: return f'''<table class="area-table"><thead><tr><th colspan="5">{area.upper()}</th></tr></thead><tbody><tr><td colspan="5">—</td></tr></tbody></table>'''
        r = row.iloc[0]
        e, bdg = r["eff"] * 100 if pd.notna(r["eff"]) else 0.0, r["bdg"] * 100 if pd.notna(r["bdg"]) else 0.0
        return (
            f'<table class="area-table"><thead><tr><th colspan="5" class="at-area" style="border-left:3px solid {AREA_COLORS[area]}">{area.upper()}</th></tr>'
            f'<tr><th>STD (h)</th><th>ACT (h)</th><th>BDG %</th><th>EFF %</th><th>VAR €</th></tr></thead><tbody><tr>'
            f'<td class="at-val">{r["std"]:,.0f}</td><td class="at-val">{r["act"]:,.0f}</td><td class="at-val at-dim">{bdg:.1f}%</td>'
            + _cell_eff(e, bdg) + _cell_var(r["var"]) + f'</tr></tbody></table>'
        )
    return f'<div class="area-tables-wrap"><div class="area-tables-col">{area_block("Lavorazione") + area_block("Assemblaggio")}</div><div class="area-tables-col">{area_block("Trattamento") + area_block("Imballaggio")}</div></div>'

def _build_cdl_table(area, cdl_list, area_bdg_pct, chart_payload=None):
    if not cdl_list: return ""
    import html as _html
    series_by_name = {s["name"]: s for s in (chart_payload or {}).get("series", [])}
    spark_bdg = (chart_payload or {}).get("bdg", area_bdg_pct)
    rows_html = ""
    for c in sorted([c for c in cdl_list if not c.get("addebito")], key=lambda x: x["descr"]):
        eff = (c["eff"] or 0) * 100
        s = series_by_name.get(c["descr"])
        spark = _sparkline_svg(s["eff"], spark_bdg, s["color"]) if s else '<span class="spark-empty">—</span>'
        data_attr = f' data-cdl="{_html.escape(c["descr"], quote=True)}"' if s else ""
        # Varianza positiva = Over-budget (Rosso)
        rows_html += f'<tr class="cdl-row{" has-trend" if s else ""}"{data_attr}><td class="cdl-name">{c["descr"]}</td><td class="cdl-spark">{spark}</td><td class="cdl-val">{c["std"]:,.0f}</td><td class="cdl-val">{c["act"]:,.0f}</td><td class="cdl-val" style="color:{C_GREEN if eff >= area_bdg_pct else C_RED}">{eff:.1f}%</td><td class="cdl-val" style="color:{C_RED if c["var"] > 0 else C_GREEN}">€ {c["var"]:+,.0f}</td></tr>'
    for c in [c for c in cdl_list if c.get("addebito")]:
        rows_html += f'<tr class="cdl-row-addebito"><td class="cdl-name">{c["descr"]}</td><td class="cdl-spark"></td><td class="cdl-val cdl-dim">—</td><td class="cdl-val">{c["act"]:,.0f}</td><td class="cdl-val cdl-dim">—</td><td class="cdl-val" style="color:{C_RED if c["var"] > 0 else C_GREEN}">€ +{c["var"]:,.0f}</td></tr>'
    return f'<table class="cdl-table"><thead><tr><th class="cdl-th-name">MACCHINARIO</th><th class="cdl-th-spark">TREND</th><th>STD (h)</th><th>ACT (h)</th><th>EFF %</th><th>VAR €</th></tr></thead><tbody>{rows_html}</tbody></table>'

def _build_section_html(section_id, section_title, df_area, overview_json, area_charts_json, cdl_by_area=None, plant_bdg_excel=None):
    cdl_by_area = cdl_by_area or {a: [] for a in AREE}
    tot_std, tot_act, tot_var = df_area["std"].sum(), df_area["act"].sum(), int(round(df_area["var"].sum()))
    plant_eff = (tot_std / tot_act * 100) if tot_act > 0 else 0.0
    plant_bdg = plant_bdg_excel * 100 if plant_bdg_excel is not None else ((df_area["bdg"].fillna(0) * df_area["std"]).sum() / tot_std * 100 if tot_std > 0 else 40.0)

    area_cards = ""
    for area in AREE:
        aid, color = f"{section_id}_{AREA_IDS[area]}", AREA_COLORS[area]
        cdl_table_html = _build_cdl_table(area, cdl_by_area.get(area, []), (df_area[df_area["area"] == area].iloc[0]["bdg"] * 100 if not df_area[df_area["area"] == area].empty and pd.notna(df_area[df_area["area"] == area].iloc[0]["bdg"]) else 0.0), area_charts_json.get(area))
        has_chart = area in area_charts_json
        chart_div = f'''<div class="cdl-focus-box" id="focusbox-{aid}"><div class="cdl-focus-info" id="finfo-{aid}"></div><div id="chart-{aid}" class="area-chart-container"></div><div class="cdl-chips" id="chips-{aid}"></div></div>''' if has_chart else ""
        detail_div = f'''<div id="detail-{aid}" class="area-detail-wrap" style="display:none;"><div class="cdl-panel{" single" if not (cdl_table_html and has_chart) else ""}" id="panel-{aid}">{f'<div class="cdl-table-wrap">{cdl_table_html}</div>' if cdl_table_html else ""}{chart_div}</div></div>''' if (has_chart or cdl_table_html) else ""
        
        row = df_area[df_area["area"] == area]
        if not row.empty:
            r, e, bdg = row.iloc[0], (row.iloc[0]["eff"] * 100 if pd.notna(row.iloc[0]["eff"]) else 0.0), (row.iloc[0]["bdg"] * 100 if pd.notna(row.iloc[0]["bdg"]) else 0.0)
            mini_kpi = f'''<div class="area-kpi"><div class="kpi-item"><span class="kpi-lbl">EFF</span><span class="kpi-val" style="color:{C_GREEN if e >= bdg else C_RED}">{e:.1f}%</span><span class="kpi-bdg">BDG {bdg:.1f}%</span></div><div class="kpi-sep"></div><div class="kpi-item"><span class="kpi-lbl">STD</span><span class="kpi-val" style="color:{C_STD}">{r['std']:,.0f} h</span></div><div class="kpi-sep"></div><div class="kpi-item"><span class="kpi-lbl">ACT</span><span class="kpi-val" style="color:{C_ACT}">{r['act']:,.0f} h</span></div><div class="kpi-sep"></div><div class="kpi-item"><span class="kpi-lbl">VAR €</span><span class="kpi-val" style="color:{C_RED if r['var'] > 0 else C_GREEN}">€ {r['var']:+,.0f}</span></div></div>'''
        else: mini_kpi = ""
        
        area_cards += f'''<div class="area-card" id="card-{aid}" data-area="{area}" style="--acolor:{color}"><div class="area-header" onclick="toggleArea('{aid}', '{area}', '{section_id}')"><div class="area-title-row"><span class="area-dot"></span><span class="area-name">{area.upper()}</span><span class="area-chevron" id="chev-{aid}">\u25b6</span></div>{mini_kpi}</div>{detail_div}</div>\n'''

    icon = {"day":"\U0001f4c5","week":"\U0001f4c6","month":"\U0001f5d3","ytd":"\U0001f4ca"}.get(section_id,"\U0001f4ca")
    return (
        f'''<div class="section-block" id="section-{section_id}">\n'''
        f'''  <div class="section-header"><span class="section-icon">{icon}</span><span class="section-title">{section_title}</span></div>\n'''
        f'''  <div class="kpi-bar-inner">\n'''
        f'''    <div class="kpi-block"><span class="kpi-lbl">EFF STABILIMENTO</span><span class="kpi-val" style="color:{C_GREEN if plant_eff >= plant_bdg else C_RED}">{plant_eff:.1f}%</span><span class="kpi-bdg-inline">BDG {plant_bdg:.1f}%</span></div>\n'''
        f'''    <div class="sep"></div><div class="kpi-block"><span class="kpi-lbl">STD TOT</span><span class="kpi-val" style="color:{C_STD}">{tot_std:,.0f} h</span></div>\n'''
        f'''    <div class="sep"></div><div class="kpi-block"><span class="kpi-lbl">ACT TOT</span><span class="kpi-val" style="color:{C_ACT}">{tot_act:,.0f} h</span></div>\n'''
        f'''    <div class="sep"></div><div class="kpi-block"><span class="kpi-lbl">VAR \u20ac TOT</span><span class="kpi-val" style="color:{C_RED if tot_var > 0 else C_GREEN}">\u20ac {tot_var:+,.0f}</span></div>\n'''
        f'''  </div>\n''' + _build_area_table(df_area) + "\n"
        f'''  <div id="overview-{section_id}" class="overview-chart-box"></div>\n'''
        f'''  <div class="areas-title">\u25b8 DETTAGLIO PER REPARTO \u2014 clicca per espandere</div>\n''' + area_cards + "</div>\n"
    )

# ─────────────────────────────────────────────────────────────────
#  JS — OFFLINE HYDRATION & INTERACTIONS
# ─────────────────────────────────────────────────────────────────

CDL_FOCUS_JS = r"""
const _cdl = {}; const TOTAL_LIGHT = '#F2F0EA', TOTAL_DARK = '#17181A';
function totalColor() { return DARK ? TOTAL_LIGHT : TOTAL_DARK; }
function themeData(data) { const c = totalColor(); return data.map(t => (t.line && t.line.color === TOTAL_LIGHT) ? { ...t, line: { ...t.line, color: c }, marker: { ...(t.marker || {}), color: c } } : t); }
function cssVar(n) { return getComputedStyle(document.body).getPropertyValue(n).trim(); }
function hexA(hex, a) { const n = parseInt(hex.replace('#', ''), 16); return 'rgba(' + (n >> 16 & 255) + ',' + (n >> 8 & 255) + ',' + (n & 255) + ',' + a + ')'; }
function fmtEur(v) { return '€ ' + (v > 0 ? '+' : '') + Math.round(v).toLocaleString('en-US'); }
function cdlSeries(st, idx) { const p = st.p; if (idx === -1) return { name: 'TOTALE ' + p.area.toUpperCase(), color: totalColor(), ...p.total, isTotal: true }; return p.series[idx]; }
function cdlRange(st) { const p = st.p, f = st.pinned, vals = [p.bdg]; const add = s => s.eff.forEach(v => { if (v != null) vals.push(v); }); if (f == null) { p.series.forEach(add); if (p.total) add(p.total); } else { add(cdlSeries(st, f)); if (p.total) add(p.total); } const lo = Math.min(...vals), hi = Math.max(...vals); const pad = Math.max((hi - lo) * 0.14, 2); return [lo >= 0 ? Math.max(0, lo - pad) : lo - 3, hi + pad]; }
function cdlTrace(st, idx) { const p = st.p, f = st.focus, s = cdlSeries(st, idx); const on = f === idx, dim = f != null && !on; const good = cssVar('--good') || '#3DD68C', bad = cssVar('--bad') || '#FF5D5D'; const t = { type: 'scatter', x: p.labels, y: s.eff, name: s.name, meta: idx, connectgaps: true, cliponaxis: false, line: { shape: 'spline', smoothing: 0.6, color: s.color, width: on ? 3.6 : (dim ? 1.3 : (s.isTotal ? 2.6 : 1.9)), dash: s.isTotal ? 'dot' : 'solid' }, opacity: dim ? (s.isTotal ? 0.35 : 0.07) : (f == null && !s.isTotal ? 0.72 : 1), mode: on ? 'lines+markers+text' : 'lines+markers', marker: { size: on ? 9 : (s.isTotal ? 6 : 4), symbol: s.isTotal ? 'diamond' : 'circle', color: s.color }, }; if (dim || (s.isTotal && !on)) { t.hoverinfo = 'skip'; } else { t.customdata = s.eff.map((_, i) => [s.var[i], s.std[i], s.act[i]]); t.hovertemplate = '<b>' + s.name + '</b><br>%{x}<br>EFF: <b>%{y:.1f}%</b><br>STD: <b>%{customdata[1]:,.0f} h</b><br>ACT: <b>%{customdata[2]:,.0f} h</b><br>VAR: <b>€ %{customdata[0]:+,.0f}</b><extra></extra>'; } if (on) { t.marker = { ...t.marker, color: s.eff.map(v => v == null ? s.color : (v >= p.bdg ? good : bad)), line: { width: 2, color: s.color } }; t.fill = 'tozeroy'; t.fillgradient = { type: 'vertical', colorscale: [[0, hexA(s.color, 0)], [1, hexA(s.color, 0.30)]] }; t.fillcolor = hexA(s.color, 0.12); t.text = s.eff.map(v => v == null ? '' : v.toFixed(1) + '%'); t.textposition = 'top center'; t.textfont = { family: 'IBM Plex Mono, monospace', size: 11, color: getT().font }; } return t; }
function cdlLayout(st) { const p = st.p, r = cdlRange(st); return themeLayout({ height: 380, margin: { t: 16, b: 10, l: 52, r: 16 }, showlegend: false, font: { family: 'IBM Plex Mono, monospace', size: 12 }, hovermode: 'closest', hoverdistance: 40, hoverlabel: { font: { family: 'IBM Plex Mono, monospace', size: 12 } }, xaxis: { tickangle: -35, tickfont: { size: 10.5 }, showgrid: false, fixedrange: true, automargin: true }, yaxis: { ticksuffix: '%', tickfont: { size: 11 }, showgrid: true, gridwidth: 1, zeroline: false, range: r, fixedrange: true, automargin: true }, shapes: [{ type: 'rect', xref: 'paper', x0: 0, x1: 1, y0: r[0], y1: p.bdg, layer: 'below', line: { width: 0 }, fillcolor: 'rgba(255,93,93,0.045)' }, { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: p.bdg, y1: p.bdg, line: { dash: 'dash', width: 1.3, color: '#6B7280' } }], annotations: [{ xref: 'paper', x: 1, y: p.bdg, xanchor: 'right', yanchor: 'bottom', showarrow: false, text: 'bdg ' + p.bdg.toFixed(1) + '%', font: { size: 10, family: 'IBM Plex Mono, monospace' } }], transition: { duration: 320, easing: 'cubic-in-out' }, }); }
function cdlInfo(st, aid) { const el = document.getElementById('finfo-' + aid); if (!el) return; const p = st.p, f = st.focus; if (f == null) { el.innerHTML = '<span class="fi-name"><span class="fi-dot" style="background:' + p.color + ';color:' + p.color + '"></span>' + p.series.length + ' MACCHINE · ' + p.area.toUpperCase() + '</span><span class="fi-hint">Passa sopra ad un elemento per isolarlo · clic per fissarlo</span>'; return; } const s = cdlSeries(st, f); const idx = s.eff.map((v, i) => v == null ? -1 : i).filter(i => i >= 0); const vals = idx.map(i => s.eff[i]); const good = cssVar('--good'), bad = cssVar('--bad'); const kpi = (l, v, c) => '<span class="fi-kpi"><span class="l">' + l + '</span><span class="v"' + (c ? ' style="color:' + c + '"' : '') + '>' + v + '</span></span>'; let html = '<span class="fi-name"><span class="fi-dot" style="background:' + s.color + ';color:' + s.color + '"></span>' + s.name + '</span>'; if (vals.length) { const li = idx[idx.length - 1], last = s.eff[li]; html += kpi('ULTIMO', last.toFixed(1) + '%', last >= p.bdg ? good : bad); const avg = vals.reduce((a, b) => a + b, 0) / vals.length; html += kpi('MEDIA', avg.toFixed(1) + '%', avg >= p.bdg ? good : bad); html += kpi('MIN-MAX', Math.min(...vals).toFixed(1) + '-' + Math.max(...vals).toFixed(1) + '%'); const sv = s.var.reduce((a, v) => a + (v || 0), 0); html += kpi('VAR €', fmtEur(sv), sv > 0 ? bad : good); } if (st.pinned === f) html += '<span class="fi-pin" data-unpin="1" title="Sblocca (Esc)">📌 FISSATO ✕</span>'; el.innerHTML = html; }
function cdlSync(st, aid) { const panel = document.getElementById('panel-' + aid); if (!panel) return; const f = st.focus; panel.classList.toggle('has-focus', f != null); const name = f == null ? null : cdlSeries(st, f).name; panel.querySelectorAll('.cdl-row[data-cdl]').forEach(r => { r.classList.toggle('is-focus', r.dataset.cdl === name); r.classList.toggle('is-pinned', st.pinned != null && r.dataset.cdl === name && st.pinned === f); }); panel.querySelectorAll('.cdl-chip').forEach(c => c.classList.toggle('is-focus', +c.dataset.idx === f)); }
function cdlDraw(aid) { const st = _cdl[aid]; if (!st) return; const order = []; if (st.p.total) order.push(-1); st.p.series.forEach((_, i) => order.push(i)); Plotly.react('chart-' + aid, order.map(i => cdlTrace(st, i)), cdlLayout(st), { responsive: true, displayModeBar: false }); cdlInfo(st, aid); cdlSync(st, aid); }
function cdlFocus(aid, idx) { const st = _cdl[aid]; if (!st || st.pinned != null || st.focus === idx) return; st.focus = idx; cancelAnimationFrame(st.raf); st.raf = requestAnimationFrame(() => cdlDraw(aid)); }
function cdlRelease(aid) { const st = _cdl[aid]; if (!st) return; clearTimeout(st.timer); st.timer = setTimeout(() => cdlFocus(aid, null), 140); }
function cdlTogglePin(aid, idx) { const st = _cdl[aid]; if (!st) return; if (st.pinned === idx) { st.pinned = null; } else { st.pinned = idx; st.focus = idx; } cdlDraw(aid); }
function initCdl(aid, payload) { const st = _cdl[aid] = { p: payload, focus: null, pinned: null, timer: null, raf: null }; const panel = document.getElementById('panel-' + aid); const nameIdx = {}; payload.series.forEach((s, i) => { nameIdx[s.name] = i; }); const chips = document.getElementById('chips-' + aid); if (chips) { let html = ''; if (payload.total) html += '<span class="cdl-chip chip-total" data-idx="-1"><i style="background:' + totalColor() + '"></i>TOTALE ' + payload.area.toUpperCase() + '</span>'; payload.series.forEach((s, i) => { html += '<span class="cdl-chip" data-idx="' + i + '"><i style="background:' + s.color + '"></i>' + s.name + '</span>'; }); chips.innerHTML = html; chips.querySelectorAll('.cdl-chip').forEach(c => { const i = +c.dataset.idx; c.addEventListener('mouseenter', () => cdlFocus(aid, i)); c.addEventListener('click', () => cdlTogglePin(aid, i)); }); } if (panel) { panel.querySelectorAll('.cdl-row[data-cdl]').forEach(r => { const i = nameIdx[r.dataset.cdl]; if (i == null) return; r.addEventListener('mouseenter', () => cdlFocus(aid, i)); r.addEventListener('click', () => cdlTogglePin(aid, i)); }); panel.addEventListener('mouseleave', () => cdlRelease(aid)); panel.addEventListener('click', e => { if (e.target.closest('[data-unpin]')) { st.pinned = null; cdlDraw(aid); } }); } cdlDraw(aid); const gd = document.getElementById('chart-' + aid); gd.addEventListener('mousemove', e => { const i = cdlNearest(aid, e); if (i !== undefined) cdlFocus(aid, i); }); gd.addEventListener('click', () => { if (st.pinned != null) cdlTogglePin(aid, st.pinned); else if (st.focus != null) cdlTogglePin(aid, st.focus); }); }
function cdlNearest(aid, e) { const st = _cdl[aid]; if (!st || st.pinned != null) return undefined; const gd = document.getElementById('chart-' + aid), fl = gd._fullLayout; if (!fl) return undefined; const xa = fl.xaxis, ya = fl.yaxis, r = gd.getBoundingClientRect(); const px = e.clientX - r.left - xa._offset, py = e.clientY - r.top - ya._offset; if (px < -8 || px > xa._length + 8 || py < -8 || py > ya._length + 8) return undefined; const xs = st.p.labels.map(l => xa.d2p(l)); const HYST = 14, MAXD = 70; let best = null, bestD = Infinity, curD = Infinity; st.p.series.forEach((s, k) => { const pts = []; s.eff.forEach((v, i) => { if (v != null) pts.push([xs[i], ya.d2p(v)]); }); if (!pts.length) return; let y; if (px <= pts[0][0]) y = pts[0][1]; else if (px >= pts[pts.length - 1][0]) y = pts[pts.length - 1][1]; else for (let j = 1; j < pts.length; j++) if (px <= pts[j][0]) { const [x0, y0] = pts[j - 1], [x1, y1] = pts[j]; y = y0 + (y1 - y0) * (px - x0) / ((x1 - x0) || 1); break; } const out = px < pts[0][0] - 20 || px > pts[pts.length - 1][0] + 20 ? 40 : 0; const d = Math.abs(y - py) + out; if (d < bestD) { bestD = d; best = k; } if (k === st.focus) curD = d; }); if (best == null || bestD > MAXD) return undefined; if (st.focus != null && st.focus >= 0 && curD - bestD < HYST) return st.focus; return best; }
function replotCdl() { Object.keys(_cdl).forEach(aid => { const chips = document.querySelector('#chips-' + aid + ' .chip-total i'); if (chips) chips.style.background = totalColor(); cdlDraw(aid); }); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') Object.keys(_cdl).forEach(aid => { const st = _cdl[aid]; if (st.pinned != null) { st.pinned = null; st.focus = null; cdlDraw(aid); } }); });
"""

DAY_SWITCH_JS = r"""
const PLOT_CFG = { responsive: true, displayModeBar: false };
function withTpl(spec) { if (!spec) return spec; const s = JSON.parse(JSON.stringify(spec)); if (PLOTLY_TPL && !s.layout.template) s.layout.template = PLOTLY_TPL; return s; }
function initOverview(sid, spec) { _overviewSpecs[sid] = spec; const el = document.getElementById('overview-' + sid); Plotly.newPlot(el, themeData(spec.data), themeLayout(spec.layout), PLOT_CFG); el.on('plotly_click', function (data) { const pt = data.points[0]; if (!pt || !pt.customdata) return; const area = pt.customdata; openArea(sid + '_' + area.toLowerCase().replace(/ /g, '_'), area, sid); }); }
let _bundlesP = null;
function getBundles() { if (!_bundlesP) _bundlesP = (async () => { const bin = Uint8Array.from(atob(DAY_BUNDLES_GZ), c => c.charCodeAt(0)); const stream = new Blob([bin]).stream().pipeThrough(new DecompressionStream('gzip')); return JSON.parse(await new Response(stream).text()); })(); return _bundlesP; }
function swapSection(sid, html, overview, areas) { Object.keys(_cdl).forEach(k => { if (k.startsWith(sid + '_')) delete _cdl[k]; }); Object.keys(_renderedAreas).forEach(k => { if (k.startsWith(sid + '_')) delete _renderedAreas[k]; }); const old = document.getElementById('section-' + sid); old.querySelectorAll('.js-plotly-plot').forEach(el => Plotly.purge(el)); old.outerHTML = html; window['AREA_CHARTS_' + sid] = areas; initOverview(sid, withTpl(overview)); }
async function loadDay(iso) { const all = await getBundles(); const b = all[iso]; if (!b) return false; ['day', 'week', 'month', 'ytd'].forEach(sid => { const s = b.sec[sid]; if (s) swapSection(sid, s.s, s.o, s.a); }); ['day', 'week', 'month', 'ytd'].forEach(pid => { const ap = b.ap[pid], oldBlk = document.getElementById('addped-block-' + pid); if (!ap || !oldBlk) return; oldBlk.querySelectorAll('.js-plotly-plot').forEach(el => Plotly.purge(el)); oldBlk.outerHTML = ap.b; delete _addpedSpecs[pid]; const el = document.getElementById('addped-chart-' + pid); if (ap.p && el) { const spec = withTpl(ap.p); _addpedSpecs[pid] = spec; Plotly.newPlot(el, themeData(spec.data), themeLayout(spec.layout), PLOT_CFG); if (window.ResizeObserver) new ResizeObserver(() => { if (el._fullLayout) Plotly.Plots.resize(el); }).observe(el); } }); document.title = 'Operations Dashboard · OMEGA · ' + b.t; document.getElementById('date-picker').value = iso; return true; }
function dayToast(msg) { let t = document.getElementById('day-toast'); if (!t) { t = document.createElement('div'); t.id = 'day-toast'; document.body.appendChild(t); } t.textContent = msg; t.classList.add('show'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 3500); }
function initDayPicker(currentIso) { const picker = document.getElementById('date-picker'); const days = DAY_LIST; if (!picker || !days.length) return; picker.min = days[0]; picker.max = days[days.length - 1]; let current = currentIso; picker.addEventListener('change', async function () { const chosen = picker.value; if (!chosen || chosen === current) return; let target = days.includes(chosen) ? chosen : null; if (!target) { const prev = days.filter(d => d < chosen); target = prev.length ? prev[prev.length - 1] : days[0]; const fmt = s => s.slice(8, 10) + '/' + s.slice(5, 7); dayToast('Nessun dato per il ' + fmt(chosen) + ' — mostro il ' + fmt(target)); } picker.disabled = true; try { if (await loadDay(target)) current = target; } catch (e) { console.error(e); dayToast('Errore nel caricamento del giorno'); picker.value = current; } finally { picker.disabled = false; } }); window.addEventListener('load', () => setTimeout(() => getBundles().catch(e => console.error(e)), 1500)); }
"""

def _fmt_date_labels(df):
    if df.empty: return df
    d = df.copy()
    d["date"] = d["date"].apply(lambda t: t.strftime("%d/%m") if hasattr(t, "strftime") else str(t))
    return d.rename(columns={"date": "label"})

def _valid_day_cols(dbd_rows, dates_cols):
    return sorted(((ts, ci) for ts, ci in dates_cols if any(_fz(r[ci+OFF_STD]) > 0 for r in dbd_rows if _is_cdl(r))), key=lambda x: x[0])

def _sum_off(row, cols, off): return sum(_fz(row[ci+off]) for _, ci in cols if ci + off < len(row))
def _agg_row(row, cols):
    std = _sum_off(row, cols, OFF_STD); act = _sum_off(row, cols, OFF_ACT)
    bdgh = _sum_off(row, cols, 3); var = _sum_off(row, cols, OFF_VAR)
    return {"std": std, "act": act, "var": int(round(var)), "eff": (std / act) if act else None, "bdg": (std / bdgh) if bdgh else None}

def _agg_period_dbd(dbd_rows, cols):
    areas = []; cdl_by_area = {a: [] for a in AREE}
    for row in dbd_rows:
        if _is_subtotal(row): areas.append({"area": row[3].strip(), **_agg_row(row, cols)})
        elif _is_cdl(row):
            area, descr = _cdl_area(row), str(row[3]).strip()[:35] if row[3] else ""
            if area and descr:
                a = _agg_row(row, cols)
                if a["std"] > 0 or a["act"] > 0: cdl_by_area[area].append({"descr": descr, "std": a["std"], "act": a["act"], "eff": a["eff"], "var": a["var"]})
    for row in dbd_rows:
        area, descr = ADD_PED_ROWS.get(str(row[3]).strip() if row[3] else ""), str(row[3]).strip() if row[3] else ""
        if area:
            act, var = _sum_off(row, cols, OFF_ACT), int(round(_sum_off(row, cols, OFF_VAR)))
            if act > 0 or var != 0: cdl_by_area[area].append({"descr": descr, "std": None, "act": act, "eff": None, "var": var, "addebito": True})
    return pd.DataFrame(areas, columns=["area", "std", "act", "bdg", "eff", "var"]), cdl_by_area

def _agg_trend_dbd(dbd_rows, cols_by_label):
    area_recs, cdl_recs, tot_recs = [], [], []
    rec = lambda a: {"eff": round(a["eff"]*100, 2), "var": a["var"], "std": int(round(a["std"])), "act": int(round(a["act"]))}
    for lbl, cols in cols_by_label:
        for row in dbd_rows:
            if _is_subtotal(row):
                a = _agg_row(row, cols)
                if a["eff"]: area_recs.append({"label": lbl, "area": row[3].strip(), **rec(a)})
            elif _is_cdl(row):
                area, descr = _cdl_area(row), str(row[3]).strip()[:35] if row[3] else ""
                if area and descr:
                    a = _agg_row(row, cols)
                    if a["eff"]: cdl_recs.append({"label": lbl, "area": area, "descr": descr, **rec(a)})
            elif isinstance(row[3], str) and row[3].strip() == PLANT_TOTAL_ROW:
                a = _agg_row(row, cols)
                if a["eff"]: tot_recs.append({"label": lbl, **rec(a)})
    return (pd.DataFrame(area_recs), pd.DataFrame(cdl_recs), pd.DataFrame(tot_recs, columns=["label", "eff", "std", "act", "var"]))

def _agg_addped_trend(dbd_rows, cols_by_label):
    recs = []
    for lbl, cols in cols_by_label:
        for row in dbd_rows:
            serie = ADD_PED_SERIES.get(str(row[3]).strip() if row[3] else "")
            if serie: recs.append({"label": lbl, "serie": serie, "act": _sum_off(row, cols, OFF_ACT), "var": int(round(_sum_off(row, cols, OFF_VAR)))})
    return pd.DataFrame(recs, columns=["label", "serie", "act", "var"])

def _plant_bdg_agg(dbd_rows, cols):
    tot_row = next((r for r in dbd_rows if isinstance(r[3], str) and r[3].strip() == PLANT_TOTAL_ROW), None)
    return _agg_row(tot_row, cols)["bdg"] if tot_row is not None else None

def _until(ts_day): return f' — fino al <span class="ytd-until">{ts_day.strftime("%d/%m/%Y")}</span>'

def _week_label(d):
    y, wk, _ = d.isocalendar()
    ws = date.fromisocalendar(y, wk, 1)
    return f"WK{wk}  {ws.strftime('%d/%m')}–{(ws + timedelta(days=4)).strftime('%d/%m')}"

def _section_parts(sid, title, trend_title, dbd_rows, cols, trend_by_label):
    df_area, cdl_by_area = _agg_period_dbd(dbd_rows, cols)
    df_trend, df_cdl_trend, df_total = _agg_trend_dbd(dbd_rows, trend_by_label)
    ov, ac = _make_section_charts(df_area, df_trend, None, df_cdl_trend, sid, trend_title, df_total)
    html = _build_section_html(sid, title, df_area, ov, ac, cdl_by_area, _plant_bdg_agg(dbd_rows, cols))
    return {"html": html, "overview": ov, "areas": ac}

def _build_day_bundle(dbd_rows, dates_cols, ts_day, ci_day, valid_ci):
    d, ddmm = ts_day.date(), ts_day.strftime('%d/%m')
    has = lambda cols: any(ci in valid_ci for _, ci in cols)
    sections, addped_trend, subtitles = {}, {}, {}

    monday = d - timedelta(days=d.weekday())
    df_area, cdl_by_area = extract_day(dbd_rows, ci_day)
    df_trend, df_cdl_trend = extract_trend_week_to_date(dbd_rows, dates_cols, d)
    wk_cols = [(ts.strftime("%d/%m"), ci) for ts, ci in _valid_week_to_date_cols(dbd_rows, dates_cols, d)]
    trend_title = f"TREND EFF % — {monday.strftime('%d/%m')} → {ddmm}" if monday != d else f"TREND EFF % — {ddmm} (lunedì)"
    ov, ac = _make_section_charts(df_area, _fmt_date_labels(df_trend), None, _fmt_date_labels(df_cdl_trend), "day", trend_title, _extract_total_trend(dbd_rows, wk_cols))
    sections["day"] = {"html": _build_section_html("day", f"DAILY — {ts_day.strftime('%A %d %B %Y').upper()}", df_area, ov, ac, cdl_by_area, plant_bdg_from_total_row(dbd_rows, ci_day)), "overview": ov, "areas": ac}
    addped_trend["day"], subtitles["day"] = _extract_add_ped_trend(dbd_rows, wk_cols), f"Trend {monday.strftime('%d/%m')} → {ddmm}" if monday != d else f"Trend {ddmm} (lunedì)"

    in_range = lambda a, b: [(ts, ci) for ts, ci in dates_cols if a <= ts.date() <= b]
    weeks = []
    for k in range(4, -1, -1):
        ws = monday - timedelta(days=7 * k)
        cols = in_range(ws, d if k == 0 else ws + timedelta(days=6))
        if has(cols): weeks.append((_week_label(ws), cols))
    sections["week"] = _section_parts("week", f"WEEKLY — {_week_label(d)}" + _until(ts_day), "TREND EFF % — ULTIME 5 SETTIMANE", dbd_rows, in_range(monday, d), weeks)
    addped_trend["week"], subtitles["week"] = _agg_addped_trend(dbd_rows, weeks), f"Trend ultime 5 settimane (fino al {ddmm})"

    mese = MESI_IT[d.month - 1]
    mtd = in_range(d.replace(day=1), d)
    days = [(ts.strftime("%d/%m"), [(ts, ci)]) for ts, ci in mtd if ci in valid_ci]
    sections["month"] = _section_parts("month", f"MONTHLY — {mese}" + _until(ts_day), f"TREND EFF % — GIORNI DI {mese}", dbd_rows, mtd, days)
    addped_trend["month"], subtitles["month"] = _agg_addped_trend(dbd_rows, days), f"Trend giorni di {mese} (fino al {ddmm})"

    ytd = in_range(date(d.year, 1, 1), d)
    months = [m for m in [(MESI_IT[mo - 1], [c for c in ytd if c[0].month == mo]) for mo in range(1, d.month + 1)] if has(m[1])]
    sections["ytd"] = _section_parts("ytd", f"YEAR TO DATE {d.year}" + _until(ts_day), f"TREND YTD — MESE PER MESE (FINO AL {ddmm})", dbd_rows, ytd, months)
    addped_trend["ytd"], subtitles["ytd"] = _agg_addped_trend(dbd_rows, months), f"Trend mese per mese YTD (fino al {ddmm})"

    addped = {pid: {"block": _build_addped_block(pid, icon, label, subtitles[pid], addped_trend[pid]), "spec": _make_addped_line_chart(addped_trend[pid], hline_y=70 if pid == "day" else None)} for pid, icon, label in ADDPED_PERIOD_META}
    return {"iso": ts_day.strftime("%Y-%m-%d"), "label": ts_day.strftime("%d/%m/%Y"), "sections": sections, "addped": addped}

def _day_bundles_js(bundles):
    import gzip, base64
    tpl = {}
    def strip(spec_json):
        if spec_json is None: return None
        spec = json.loads(spec_json)
        t = spec.get("layout", {}).pop("template", None)
        if t is not None and "t" not in tpl: tpl["t"] = t
        return spec
    out = {b["iso"]: {"t": b["label"], "sec": {sid: {"s": s["html"], "o": strip(s["overview"]), "a": s["areas"]} for sid, s in b["sections"].items()}, "ap": {pid: {"b": a["block"], "p": strip(a["spec"])} for pid, a in b["addped"].items()}} for b in bundles}
    raw = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = base64.b64encode(gzip.compress(raw, 9)).decode("ascii")
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return dump(sorted(out)), json.dumps(packed), dump(tpl.get("t"))

def build_dashboard():
    dates_cols, dbd_rows = load_dbd()
    ts_day, ci_day = dates_cols[-1]

    valid_days = _valid_day_cols(dbd_rows, dates_cols)
    valid_ci = {ci for _, ci in valid_days}
    print(f"⏳ Pre-generazione bundle SPA per {len(valid_days)} giorni...")
    day_bundles = [_build_day_bundle(dbd_rows, dates_cols, ts, ci, valid_ci) for ts, ci in valid_days]
    day_sel = next((b for b in day_bundles if b["iso"] == ts_day.strftime("%Y-%m-%d")), None) or _build_day_bundle(dbd_rows, dates_cols, ts_day, ci_day, valid_ci)
    day_list_js, day_bundles_js, plotly_tpl_js = _day_bundles_js(day_bundles)

    S, A = day_sel["sections"], day_sel["addped"]
    sec_day, sec_wk, sec_mo, sec_ytd = (S[k]["html"] for k in ("day", "week", "month", "ytd"))
    ov_day, ov_wk, ov_mo, ov_ytd     = (S[k]["overview"] for k in ("day", "week", "month", "ytd"))
    sec_addped = '<div class="section-block" id="section-addped">\n  <div class="section-header"><span class="section-icon">\U0001f9fe</span><span class="section-title">ORE DI SCARTO / REWORK</span></div>\n  <div class="addped-grid">' + "".join(A[pid]["block"] for pid, _, _ in ADDPED_PERIOD_META) + '</div>\n</div>\n'

    gen_ts = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    day_iso = ts_day.strftime('%Y-%m-%d')
    ac_day_js, ac_wk_js, ac_mo_js, ac_ytd_js = (json.dumps(S[k]["areas"]) for k in ("day", "week", "month", "ytd"))
    addped_day_js, addped_wk_js, addped_mo_js, addped_ytd_js = (A[k]["spec"] if A[k]["spec"] is not None else "null" for k in ("day", "week", "month", "ytd"))

    html_doc = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Operations Dashboard · OMEGA · {ts_day.strftime('%d/%m/%Y')}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Baloo+2:wght@600;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin:0; padding:0; }}
    :root {{ --bg-deep: #0B0D10; --ago-hue: rgba(79, 209, 197, 0.10); --text-1: #EDEFF2; --text-2: #8A8F98; --text-3: #575C64; --good: #3DD68C; --bad: #FF5D5D; --glass-border: rgba(255, 255, 255, 0.08); --line-hair: #22252B; --pill-bg: rgba(13, 16, 21, 0.72); --surface: rgba(255, 255, 255, 0.035); --surface2: rgba(255, 255, 255, 0.06); --border: var(--glass-border); --bg: var(--bg-deep); --txt: var(--text-1); --txt-dim: var(--text-2); --grid: var(--line-hair); --plot: transparent; --accent: #4FD1C5; }}
    body.light-mode {{ --bg-deep: #F2F0EA; --ago-hue: rgba(62, 124, 177, 0.09); --text-1: #17181A; --text-2: #5B5F66; --text-3: #9297A0; --good: #1FAE6E; --bad: #E23D3D; --glass-border: rgba(0, 0, 0, 0.09); --line-hair: #DDE0E6; --pill-bg: rgba(255, 255, 255, 0.78); --surface: rgba(0, 0, 0, 0.025); --surface2: rgba(0, 0, 0, 0.045); --border: var(--glass-border); --bg: var(--bg-deep); --txt: var(--text-1); --txt-dim: var(--text-2); --grid: var(--line-hair); --accent: #2F8F86; }}
    body {{ background: var(--bg-deep); color: var(--txt); font-family: 'Space Grotesk', sans-serif; position: relative; transition: background-color .35s ease, color .35s ease; padding-top: 68px; }}
    body::before {{ content: ''; position: fixed; inset: 0; z-index: 0; pointer-events: none; background: radial-gradient(circle at 20% 0%, var(--ago-hue), transparent 55%); }}
    #wrap {{ max-width: 1600px; margin: 0 auto; padding: 20px 24px 60px; position: relative; z-index: 1; }}
    #navbar {{ position: fixed; top: 0; left: 0; right: 0; z-index: 1000; height: 68px; overflow: hidden; display: grid; grid-template-columns: minmax(170px,1fr) minmax(380px,auto) auto minmax(420px,1fr); align-items: center; column-gap: 16px; padding: 0 24px; background: var(--pill-bg); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid var(--glass-border); }}
    .nav-brand {{ justify-self: start; min-width: 0; display: flex; flex-direction: column; gap: 2px; line-height: 1.15; }}
    .brand-text {{ font-family: 'Baloo 2', sans-serif; font-weight: 700; font-size: 19px; letter-spacing: -.01em; color: var(--txt); white-space: nowrap; }}
    .brand-sub {{ font-family: 'IBM Plex Mono', monospace; font-size: 10px; font-weight: 600; letter-spacing: .14em; color: var(--txt-dim); text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .nav-center {{ justify-self: center; display: flex; align-items: center; gap: 10px; min-width: 0; }}
    .nav-links {{ position: relative; display: inline-flex; width: 380px; padding: 4px; background: var(--surface2); backdrop-filter: blur(4px); border: 1px solid var(--glass-border); border-radius: 999px; flex-shrink: 0; }}
    .nav-addped-btn {{ display: flex; align-items: center; gap: 6px; padding: 9px 16px; border-radius: 999px; background: var(--surface2); border: 1px solid var(--glass-border); backdrop-filter: blur(4px); font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; letter-spacing: .05em; color: var(--txt-dim); text-decoration: none; white-space: nowrap; cursor: pointer; transition: all .2s ease; flex-shrink: 0; margin-right: 14px; }}
    .nav-addped-btn:hover {{ color: var(--txt); border-color: var(--text-3); transform: translateY(-1px); }}
    .nav-addped-btn.active {{ color: #0B0D10; background: linear-gradient(135deg, #4FD1C5, #3DD68C); border-color: transparent; }}
    body.light-mode .nav-addped-btn.active {{ color: #F2F0EA; }}
    .nav-slider {{ position: absolute; top: 4px; bottom: 4px; left: 4px; width: calc(25% - 2px); border-radius: 999px; background: linear-gradient(135deg, #4FD1C5, #3DD68C); transition: transform .3s cubic-bezier(.4, 0, .2, 1); z-index: 0; }}
    .nav-link {{ position: relative; z-index: 1; flex: 1; text-align: center; font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; letter-spacing: .05em; padding: 9px 0; border-radius: 999px; border: none; background: transparent; color: var(--txt-dim); text-decoration: none; cursor: pointer; transition: color .2s ease; white-space: nowrap; }}
    .nav-link.active {{ color: #0B0D10; }}
    body.light-mode .nav-link.active {{ color: #F2F0EA; }}
    .nav-right {{ justify-self: end; min-width: 0; display: flex; align-items: center; gap: 10px; }}
    .live-status {{ display: flex; flex-direction: column; align-items: flex-end; gap: 3px; min-width: 0; }}
    .nav-timestamp {{ display: block; font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: .06em; color: var(--txt-dim); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 230px; text-align: right; }}
    .nav-status-label {{ display: flex; align-items: center; justify-content: flex-end; gap: 6px; font-family: 'IBM Plex Mono', monospace; font-size: 10.5px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--txt-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 230px; }}
    .live-dot {{ display: inline-block; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: var(--good); box-shadow: 0 0 8px var(--good); animation: pulse-dot 2s ease-in-out infinite; }}
    @keyframes pulse-dot {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .4; }} }}
    #btn-theme {{ background: var(--surface2); color: var(--txt); border: 1px solid var(--glass-border); width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all .2s ease; }}
    #btn-theme:hover {{ border-color: var(--txt-dim); transform: translateY(-1px); }}
    .date-picker {{ background: var(--surface2); color: var(--txt); border: 1px solid var(--glass-border); font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; border-radius: 10px; cursor: pointer; padding: 8px 10px; height: 34px; flex-shrink: 0; transition: all .2s ease; }}
    .date-picker:hover {{ border-color: var(--txt-dim); transform: translateY(-1px); }}
    .date-picker::-webkit-calendar-picker-indicator {{ filter: var(--date-icon-filter, none); cursor: pointer; }}
    body.light-mode .date-picker {{ --date-icon-filter: none; }}
    body:not(.light-mode) .date-picker {{ --date-icon-filter: invert(1); }}
    .section-block {{ margin-bottom:48px; }}
    .section-header {{ display:flex; align-items:center; gap:10px; margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--line-hair); }}
    .section-icon  {{ font-size:18px; opacity:.85; }}
    .section-title {{ font-family: 'IBM Plex Mono', monospace; font-size:12px; font-weight:600; letter-spacing:.14em; text-transform: uppercase; color: var(--txt-dim); }}
    .kpi-bar-inner {{ display:flex; justify-content:space-around; align-items:center; padding:13px 28px; margin-bottom:14px; border-radius:14px; background: var(--pill-bg); backdrop-filter: blur(16px); border:1px solid var(--glass-border); }}
    .kpi-bar-inner .kpi-lbl {{ display:block; font-family: 'IBM Plex Mono', monospace; font-size:10px; color:var(--txt-dim); font-weight:600; letter-spacing:.12em; margin-bottom:4px; }}
    .kpi-bar-inner .kpi-val {{ font-family: 'Space Grotesk', sans-serif; font-size:23px; font-weight:700; display:block; }}
    .kpi-bar-inner .kpi-bdg-inline {{ font-family: 'IBM Plex Mono', monospace; font-size:10px; color:var(--txt-dim); font-weight:600; display:block; margin-top:2px; }}
    .kpi-bar-inner .sep {{ width:1px; height:38px; background:var(--line-hair); }}
    .overview-chart-box {{ background: var(--surface); border:1px solid var(--glass-border); border-radius:16px; padding:8px; margin-bottom:18px; backdrop-filter: blur(10px); }}
    .areas-title {{ font-family: 'IBM Plex Mono', monospace; font-size:11px; font-weight:600; letter-spacing:.14em; text-transform: uppercase; color: var(--text-3); margin-bottom:12px; padding-left:12px; border-left:2px solid var(--line-hair); }}
    .area-card {{ background: var(--surface); border:1px solid var(--glass-border); border-left:3px solid var(--acolor); border-radius:12px; margin-bottom:7px; overflow:hidden; transition: all .2s ease; backdrop-filter: blur(10px); }}
    .area-card:hover {{ border-color: var(--text-3); transform: translateY(-1px); }}
    .area-header {{ padding:10px 18px; cursor:pointer; display:flex; flex-direction:column; gap:7px; }}
    .area-header:hover {{ background: var(--surface2); }}
    .area-title-row {{ display:flex; align-items:center; gap:9px; }}
    .area-dot   {{ width:7px; height:7px; border-radius:50%; background:var(--acolor); flex-shrink:0; box-shadow: 0 0 8px var(--acolor); }}
    .area-name  {{ font-family: 'IBM Plex Mono', monospace; font-size:11.5px; font-weight:600; letter-spacing:.08em; color:var(--txt); flex:1; }}
    .area-chevron {{ font-size:10px; color:var(--txt-dim); transition:transform .25s; flex-shrink:0; }}
    .area-chevron.open {{ transform:rotate(90deg); }}
    .area-kpi   {{ display:flex; align-items:center; }}
    .kpi-item   {{ display:flex; flex-direction:column; align-items:center; flex:1; gap:2px; }}
    .kpi-lbl    {{ font-family: 'IBM Plex Mono', monospace; font-size:8.5px; color:var(--txt-dim); font-weight:600; letter-spacing:.1em; }}
    .kpi-val    {{ font-family: 'Space Grotesk', sans-serif; font-size:16px; font-weight:700; }}
    .kpi-bdg    {{ font-family: 'IBM Plex Mono', monospace; font-size:8.5px; color:var(--txt-dim); font-weight:600; }}
    .kpi-sep    {{ width:1px; height:34px; background:var(--line-hair); flex-shrink:0; }}
    .area-detail-wrap {{ border-top:1px solid var(--glass-border); padding:11px 14px 10px; background: rgba(0,0,0,0.08); }}
    body.light-mode .area-detail-wrap {{ background: rgba(0,0,0,0.02); }}
    .area-chart-container {{ height:380px; }}
    .ytd-until {{ font-weight:700; color:var(--txt); text-decoration:underline; text-underline-offset:3px; }}
    #day-toast {{ position:fixed; top:80px; left:50%; transform:translate(-50%, -10px); z-index:1100; padding:9px 16px; border-radius:999px; background:var(--pill-bg); backdrop-filter:blur(16px); border:1px solid var(--glass-border); color:var(--txt); font-family:'IBM Plex Mono', monospace; font-size:11px; font-weight:600; letter-spacing:.04em; opacity:0; pointer-events:none; transition:opacity .25s ease, transform .25s ease; }}
    #day-toast.show {{ opacity:1; transform:translate(-50%, 0); }}
    .cdl-panel {{ display:grid; grid-template-columns:minmax(420px, 0.95fr) 1.55fr; gap:14px; align-items:start; }}
    .cdl-panel.single {{ grid-template-columns:1fr; }}
    @media (max-width: 1150px) {{ .cdl-panel {{ grid-template-columns:1fr; }} }}
    .cdl-table-wrap {{ min-width:0; }}
    .cdl-focus-box {{ min-width:0; background: var(--surface2); border:1px solid var(--glass-border); border-radius:12px; padding:10px 12px 8px; }}
    .cdl-focus-info {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap; min-height:38px; padding:2px 4px 8px; border-bottom:1px solid var(--glass-border); font-family:'IBM Plex Mono', monospace; font-size:10px; color:var(--txt-dim); }}
    .fi-name {{ display:flex; align-items:center; gap:8px; font-size:12px; font-weight:600; letter-spacing:.04em; color:var(--txt); margin-right:auto; }}
    .fi-dot  {{ width:9px; height:9px; border-radius:50%; flex-shrink:0; box-shadow:0 0 10px currentColor; }}
    .fi-hint {{ color:var(--text-3); font-weight:500; letter-spacing:.02em; }}
    .fi-kpi  {{ display:flex; flex-direction:column; align-items:flex-end; gap:1px; }}
    .fi-kpi .l {{ font-size:8.5px; font-weight:600; letter-spacing:.1em; color:var(--txt-dim); }}
    .fi-kpi .v {{ font-family:'Space Grotesk', sans-serif; font-size:15px; font-weight:700; color:var(--txt); }}
    .fi-pin  {{ font-size:9px; font-weight:600; letter-spacing:.1em; padding:3px 8px; border-radius:999px; border:1px solid var(--glass-border); color:var(--txt); background:var(--surface); cursor:pointer; }}
    .cdl-chips {{ display:flex; flex-wrap:wrap; gap:6px; padding:8px 2px 2px; }}
    .cdl-chip {{ display:inline-flex; align-items:center; gap:6px; padding:4px 10px 4px 8px; border-radius:999px; border:1px solid var(--glass-border); background:var(--surface); cursor:pointer; font-family:'IBM Plex Mono', monospace; font-size:10px; font-weight:600; color:var(--txt-dim); transition: opacity .2s ease, border-color .2s ease, color .2s ease, transform .2s ease; user-select:none; }}
    .cdl-chip i {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
    .cdl-chip:hover {{ color:var(--txt); transform:translateY(-1px); }}
    .cdl-chip.chip-total {{ border-style:dashed; }}
    .has-focus .cdl-chip {{ opacity:.35; }}
    .has-focus .cdl-chip.is-focus {{ opacity:1; color:var(--txt); border-color:var(--text-3); }}
    .cdl-row.has-trend {{ cursor:pointer; transition: opacity .2s ease, background .2s ease; }}
    .cdl-row.has-trend:hover td {{ background: var(--surface); }}
    .has-focus .cdl-row {{ opacity:.35; }}
    .has-focus .cdl-row.is-focus {{ opacity:1; }}
    .has-focus .cdl-row.is-focus td {{ background: var(--surface); }}
    .has-focus .cdl-row.is-focus .cdl-name {{ color:var(--txt); }}
    .cdl-row.is-pinned .cdl-name::before {{ content:'📌 '; }}
    .cdl-spark {{ padding:2px 6px !important; text-align:center !important; width:104px; }}
    .cdl-table th.cdl-th-spark {{ text-align:center; }}
    .spark {{ display:block; margin:0 auto; overflow:visible; }}
    .spark-bdg {{ stroke:var(--text-3); stroke-width:1; stroke-dasharray:2 2; }}
    .spark-empty {{ color:var(--text-3); }}
    .cdl-table {{ width:100%; border-collapse:collapse; background: var(--surface2); border:1px solid var(--glass-border); border-radius:10px; overflow:hidden; font-size:11px; font-family:'IBM Plex Mono', monospace; }}
    .cdl-table th {{ background: var(--surface); color:var(--txt-dim); font-size:8.5px; font-weight:600; letter-spacing:.08em; padding:5px 8px; border-bottom:1px solid var(--glass-border); text-align:right; }}
    .cdl-table th.cdl-th-name {{ text-align:left; }}
    .cdl-table td {{ padding:5px 8px; text-align:right; border-top:1px solid var(--glass-border); font-size:10.5px; }}
    .cdl-name {{ text-align:left !important; color:var(--txt-dim); font-weight:600; }}
    .cdl-val  {{ font-weight:600; font-family: 'Space Grotesk', sans-serif; white-space:nowrap; }}
    .cdl-row-addebito td {{ font-style: italic; }}
    .cdl-row-addebito .cdl-name {{ font-weight:500; }}
    .cdl-dim  {{ color:var(--txt-dim) !important; font-weight:500 !important; }}
    .area-tables-wrap {{ display:flex; gap:12px; margin-bottom:12px; }}
    .area-tables-col  {{ flex:1; display:flex; flex-direction:column; gap:7px; min-width:0; }}
    .area-table {{ width:100%; border-collapse:collapse; background: var(--surface); border:1px solid var(--glass-border); border-radius:10px; overflow:hidden; font-size:11px; font-family:'IBM Plex Mono', monospace; backdrop-filter: blur(8px); }}
    .area-table th {{ background: var(--surface2); color:var(--txt-dim); font-size:8.5px; font-weight:600; letter-spacing:.09em; padding:4px 8px; border-bottom:1px solid var(--glass-border); text-align:center; }}
    .area-table th.at-area {{ color:var(--txt); font-size:11px; letter-spacing:.09em; text-align:left; padding:6px 10px; font-family:'IBM Plex Mono', monospace; text-transform: uppercase; }}
    .area-table td {{ padding:4px 8px; text-align:right; border-top:1px solid var(--glass-border); }}
    .at-val  {{ font-weight:700; font-size:12px; font-family: 'Space Grotesk', sans-serif; }}
    .at-dim  {{ color:var(--txt-dim) !important; }}
    #section-addped {{ margin-bottom:160px; }}
    .addped-grid {{ display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:16px; height:calc(100vh - 210px); min-height:540px; }}
    @media (max-width: 850px) {{ .addped-grid {{ grid-template-columns:1fr; grid-template-rows:none; height:auto; }} }}
    .addped-block {{ background: var(--surface); border:1px solid var(--glass-border); border-radius:14px; padding:12px 14px; backdrop-filter: blur(10px); display:flex; flex-direction:column; min-height:0; overflow:hidden; }}
    .addped-block-header {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:4px; }}
    .addped-block-icon  {{ font-size:15px; }}
    .addped-block-title {{ font-family:'IBM Plex Mono', monospace; font-size:11px; font-weight:700; letter-spacing:.12em; color:var(--txt); }}
    .addped-block-kpi   {{ font-family:'IBM Plex Mono', monospace; font-size:10px; color:var(--txt-dim); margin-left:auto; white-space:nowrap; }}
    .addped-block-subtitle {{ font-family:'IBM Plex Mono', monospace; font-size:10px; color:var(--text-3); margin-bottom:6px; }}
    .addped-chart-container {{ flex:1; min-height:0; overflow:hidden; }}
    .addped-empty {{ padding:60px 0; text-align:center; color:var(--txt-dim); font-family:'IBM Plex Mono', monospace; font-size:11px; }}
  </style>
</head>
<body>
<nav id="navbar">
  <div class="nav-brand">
    <span class="brand-text">Global Manufacturing</span>
    <span class="brand-sub">STABILIMENTO OMEGA</span>
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
  <a class="nav-addped-btn" id="nav-addped" href="#section-addped">🧾 <span class="addped-btn-label">Rework</span></a>
  <div class="nav-right">
    <div class="live-status">
      <span class="nav-status-label"><span class="live-dot"></span>EFFICIENZA PRODUZIONE</span>
      <span class="nav-timestamp">Generato: {gen_ts}</span>
    </div>
    <input type="date" id="date-picker" class="date-picker" value="{day_iso}" title="Visualizza un altro giorno (Storico)">
    <button id="btn-theme"  onclick="toggleTheme()" title="Cambia tema">☀️</button>
  </div>
</nav>

<div id="wrap">
  {sec_day}
  {sec_wk}
  {sec_mo}
  {sec_ytd}
  {sec_addped}
</div>

<script>
let DARK = window.matchMedia('(prefers-color-scheme: dark)').matches;
const _overviewSpecs = {{}};
const _renderedAreas = {{}};
const OVERVIEW_DAY   = {ov_day}; const OVERVIEW_WEEK  = {ov_wk}; const OVERVIEW_MONTH = {ov_mo}; const OVERVIEW_YTD   = {ov_ytd};
var AREA_CHARTS_day   = {ac_day_js}; var AREA_CHARTS_week  = {ac_wk_js}; var AREA_CHARTS_month = {ac_mo_js}; var AREA_CHARTS_ytd   = {ac_ytd_js};
const ADDPED_DAY   = {addped_day_js}; const ADDPED_WEEK  = {addped_wk_js}; const ADDPED_MONTH = {addped_mo_js}; const ADDPED_YTD   = {addped_ytd_js};
const _addpedSpecs = {{}};
{CDL_FOCUS_JS}
const DAY_LIST    = {day_list_js}; const DAY_BUNDLES_GZ = {day_bundles_js}; const PLOTLY_TPL  = {plotly_tpl_js};
{DAY_SWITCH_JS}

function applyTheme() {{
  const btn = document.getElementById('btn-theme');
  if (DARK) {{ document.body.classList.remove('light-mode'); btn.textContent = '☀️'; }}
  else      {{ document.body.classList.add('light-mode');    btn.textContent = '🌙';  }}
}}
function toggleTheme() {{ DARK = !DARK; applyTheme(); replotAll(); }}
applyTheme();

function getT() {{
  return DARK ? {{ paper:'rgba(0,0,0,0)', plot:'rgba(0,0,0,0)', font:'#EDEFF2', grid:'#22252B', tick:'#8A8F98', zero:'#22252B', subt:'#575C64' }}
              : {{ paper:'rgba(0,0,0,0)', plot:'rgba(0,0,0,0)', font:'#17181A', grid:'#DDE0E6', tick:'#5B5F66', zero:'#DDE0E6', subt:'#9297A0' }};
}}
function themeLayout(layout) {{
  const T = getT();
  const upd = {{ ...layout, paper_bgcolor:T.paper, plot_bgcolor:T.plot, font:{{ ...layout.font, color:T.font }} }};
  Object.keys(upd).forEach(k => {{
    if (k.startsWith('xaxis') || k.startsWith('yaxis')) {{ upd[k] = {{ ...upd[k], gridcolor:T.grid, zerolinecolor:T.zero, tickfont:{{ ...((upd[k]||{{}}).tickfont||{{}}), color:T.tick }} }}; }}
  }});
  if (upd.annotations) {{ upd.annotations = upd.annotations.map(a => ({{ ...a, font:{{ ...(a.font||{{}}), color:T.subt }} }})); }}
  return upd;
}}
function replotAll() {{
  ['day','week','month','ytd'].forEach(sid => {{ const el = document.getElementById('overview-' + sid); if (el && el._fullLayout && _overviewSpecs[sid]) {{ Plotly.react('overview-' + sid, themeData(_overviewSpecs[sid].data), themeLayout(_overviewSpecs[sid].layout)); }} }});
  replotCdl();
  ['day','week','month','ytd'].forEach(pid => {{ const el = document.getElementById('addped-chart-' + pid); if (el && el._fullLayout && _addpedSpecs[pid]) {{ Plotly.react('addped-chart-' + pid, themeData(_addpedSpecs[pid].data), themeLayout(_addpedSpecs[pid].layout)); }} }});
}}

function openArea(aid, area, sid) {{
  const detailDiv = document.getElementById('detail-' + aid);
  const chev = document.getElementById('chev-' + aid);
  const card = document.getElementById('card-' + aid);
  if (!detailDiv) return;
  if (detailDiv.style.display !== 'none') {{ detailDiv.style.display = 'none'; chev.classList.remove('open'); }}
  else {{
    detailDiv.style.display = 'block'; chev.classList.add('open');
    if (!_renderedAreas[aid]) {{
      _renderedAreas[aid] = true;
      requestAnimationFrame(() => requestAnimationFrame(() => {{
        const charts = window['AREA_CHARTS_' + sid];
        if (charts && charts[area] && document.getElementById('chart-' + aid)) {{ initCdl(aid, charts[area]); }}
        setTimeout(() => card.scrollIntoView({{behavior:'smooth', block:'nearest'}}), 80);
      }}));
    }} else {{
      if (_cdl[aid]) Plotly.Plots.resize('chart-' + aid);
      setTimeout(() => card.scrollIntoView({{behavior:'smooth', block:'nearest'}}), 50);
    }}
  }}
}}
function toggleArea(aid, area, sid) {{ openArea(aid, area, sid); }}

(function initOverviews() {{ [['day', OVERVIEW_DAY], ['week', OVERVIEW_WEEK], ['month', OVERVIEW_MONTH], ['ytd', OVERVIEW_YTD]].forEach(function([sid, spec]) {{ initOverview(sid, spec); }}); }})();
(function initAddPed() {{
  const pairs = [['day', ADDPED_DAY], ['week', ADDPED_WEEK], ['month', ADDPED_MONTH], ['ytd', ADDPED_YTD]];
  const pids = [];
  pairs.forEach(function([pid, spec]) {{
    if (!spec) return;
    _addpedSpecs[pid] = spec;
    const el = document.getElementById('addped-chart-' + pid);
    if (el) {{ Plotly.newPlot(el.id, themeData(spec.data), themeLayout(spec.layout), {{responsive:true, displayModeBar:false}}); pids.push(pid); }}
  }});
  function resizeAllAddped() {{ pids.forEach(function(pid) {{ const el = document.getElementById('addped-chart-' + pid); if (el && el._fullLayout) {{ Plotly.Plots.resize(el); }} }}); }}
  window.addEventListener('load', function() {{ setTimeout(resizeAllAddped, 60); }}); setTimeout(resizeAllAddped, 300);
  if (window.ResizeObserver) {{ const ro = new ResizeObserver(function() {{ resizeAllAddped(); }}); pids.forEach(function(pid) {{ const el = document.getElementById('addped-chart-' + pid); if (el) ro.observe(el); }}); }}
}})();

initDayPicker('{day_iso}');

(function() {{
  const SECTIONS = ['day','week','month','ytd','addped']; const PILL = ['day','week','month','ytd']; const OFFSET = 68; const slider = document.getElementById('navSlider');
  function updateActive() {{
    let current = SECTIONS[0];
    SECTIONS.forEach(function(sid) {{ const el = document.getElementById('section-' + sid); if (el && el.getBoundingClientRect().top <= OFFSET + 10) current = sid; }});
    SECTIONS.forEach(function(sid) {{ const link = document.getElementById('nav-' + sid); if (link) link.classList.toggle('active', sid === current); }});
    if (slider && PILL.includes(current)) {{ slider.style.transform = 'translateX(' + (PILL.indexOf(current) * 100) + '%)'; }}
  }}
  document.querySelectorAll('.nav-link, .nav-addped-btn').forEach(function(link) {{
    link.addEventListener('click', function(e) {{
      const target = document.querySelector(this.getAttribute('href'));
      if (!target) return; e.preventDefault();
      window.scrollTo({{ top: target.getBoundingClientRect().top + window.scrollY - OFFSET + 2, behavior: 'smooth' }});
    }});
  }});
  window.addEventListener('scroll', updateActive, {{ passive: true }}); updateActive();
}})();
</script>
</body>
</html>"""

    os.makedirs(OUTPUT_DIR_LATEST, exist_ok=True)
    latest_path = os.path.join(OUTPUT_DIR_LATEST, LATEST_FILENAME)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print("═" * 65)
    print(f"🚀 DASHBOARD GENERATA CON SUCCESSO!")
    print(f"   🔗 Apri questo file nel browser: {os.path.abspath(latest_path)}")
    print("═" * 65)

if __name__ == "__main__":
    build_dashboard()
