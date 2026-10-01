"""
╔══════════════════════════════════════════════════════════════════╗
║         SUPPLY CHAIN COMMAND DECK — GLOBAL OPS                   ║
║         Design: Hybrid "Twin Thread" + "Pressure Gauge"          ║
║         Output: Serverless Offline HTML SPA                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import random
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
#  CONFIGURAZIONE
# ─────────────────────────────────────────────────────────────────

OUTPUT_DIR = "./output"
OUTPUT_FILE_NAME = "supply_chain_command_deck.html"

# ─────────────────────────────────────────────────────────────────
#  GENERATORE DATI IN-MEMORY (Simulazione Aggregazione Multi-Plant)
# ─────────────────────────────────────────────────────────────────

def _generate_plant_data(period_multiplier, base_std, target_bdg):
    """Genera dati realistici per un singolo stabilimento scalati per periodo."""
    std = random.uniform(base_std * 0.9, base_std * 1.1) * period_multiplier
    act = std * random.uniform(0.85, 1.25)  # Varianza realistica
    eff = (std / act * 100) if act > 0 else 0.0
    var = (std - act) * 45.0  # Costo orario standard simulato a 45€/h
    
    return {
        "eff": round(eff, 1),
        "bdg": round(target_bdg, 1),
        "std": int(round(std)),
        "act": int(round(act)),
        "var": int(round(var))
    }

def _combine_plants(plant_a, plant_b, target_bdg):
    """Aggrega matematicamente due plant per il total di Supply Chain."""
    std = plant_a["std"] + plant_b["std"]
    act = plant_a["act"] + plant_b["act"]
    var = plant_a["var"] + plant_b["var"]
    eff = (std / act * 100) if act > 0 else 0.0
    
    return {
        "eff": round(eff, 1),
        "bdg": round(target_bdg, 1),
        "std": std,
        "act": act,
        "var": var
    }

def build_period_payload(caption, multiplier):
    """Costruisce il nodo JSON esatto che il frontend si aspetta."""
    bdg_alpha, bdg_beta, bdg_global = 85.0, 82.0, 83.5
    
    alpha = _generate_plant_data(multiplier, base_std=800, target_bdg=bdg_alpha)
    beta  = _generate_plant_data(multiplier, base_std=600, target_bdg=bdg_beta)
    glob  = _combine_plants(alpha, beta, target_bdg=bdg_global)
    
    return {
        "caption": caption,
        "alpha": alpha,
        "beta": beta,
        "global": glob
    }

def generate_mock_payload():
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    
    # Moltiplicatori di volume per i vari periodi (1 giorno, 5 giorni, 20 giorni, 150 giorni)
    return {
        "day":   build_period_payload(f"DAILY · {today.strftime('%A %d %B %Y').upper()}", 1),
        "week":  build_period_payload(f"WEEK · {week_start.strftime('%d/%m')} - {today.strftime('%d/%m')}", 5),
        "month": build_period_payload(f"MONTHLY · {today.strftime('%B %Y').upper()}", 22),
        "ytd":   build_period_payload(f"YEAR TO DATE {today.year}", 180)
    }

# ─────────────────────────────────────────────────────────────────
#  TEMPLATE HTML / JS (Sanitizzato e reso Serverless)
# ─────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Supply Chain · Command Deck</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Baloo+2:wght@600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --bg-deep: #0B0D10;
    --alpha-hue: rgba(79, 209, 197, 0.11);
    --beta-hue: rgba(255, 122, 51, 0.11);
    --text-1: #EDEFF2;
    --text-2: #8A8F98;
    --text-3: #484D54;
    --good: #3DD68C;
    --bad: #FF5D5D;
    --glass-border: rgba(255, 255, 255, 0.08);
    --line-hair: #22252B;
    --tick-color: #22262E;
    --bdg-mark-color: #ffffff;
    --pill-bg: rgba(13, 16, 21, 0.75);
    --thread-color: rgba(255, 255, 255, 0.04);
  }
  body.light-mode {
    --bg-deep: #F2F0EA;
    --alpha-hue: rgba(62, 124, 177, 0.10);
    --beta-hue: rgba(201, 132, 62, 0.10);
    --text-1: #17181A;
    --text-2: #5B5F66;
    --text-3: #9297A0;
    --good: #1FAE6E;
    --bad: #E23D3D;
    --glass-border: rgba(0, 0, 0, 0.09);
    --line-hair: #DDE0E6;
    --tick-color: #D3D7DE;
    --bdg-mark-color: #17181A;
    --pill-bg: rgba(255, 255, 255, 0.75);
    --thread-color: rgba(0, 0, 0, 0.06);
  }
  *,*::before,*::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg-deep); color: var(--text-1); font-family: 'Space Grotesk', sans-serif;
    min-height: 100vh; overflow: hidden; position: relative; transition: background-color .35s ease, color .35s ease;
  }

  .halves { position: absolute; inset: 0; display: flex; z-index: 0; pointer-events: none; }
  .half { flex: 1; position: relative; }
  .half.alpha { background: radial-gradient(circle at 35% 50%, var(--alpha-hue), transparent 60%); }
  .half.beta { background: radial-gradient(circle at 65% 50%, var(--beta-hue), transparent 60%); }

  header {
    position: fixed; top: 0; left: 0; right: 0; z-index: 20;
    display: flex; justify-content: space-between; align-items: center; padding: 24px 32px; pointer-events: none;
  }
  .brand { display: flex; align-items: center; }
  .brand-text { font-family: 'Baloo 2', sans-serif; font-weight: 700; font-size: 28px; letter-spacing: -.01em; color: var(--text-1); user-select: none; }
  
  .eyebrow { font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: .16em; text-transform: uppercase; color: var(--text-2); }
  
  .live-status { text-align: right; }
  .live-dot {
    display: inline-block; width: 6px; height: 6px; border-radius: 50%;
    background: var(--good); margin-right: 7px; vertical-align: middle;
    box-shadow: 0 0 10px var(--good); animation: pulse-dot 2s ease-in-out infinite;
  }
  @keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: .4; } }

  .header-actions { display: flex; align-items: center; gap: 10px; pointer-events: auto; }
  .icon-btn {
    background: var(--pill-bg); backdrop-filter: blur(14px); color: var(--text-1); border: 1px solid var(--glass-border);
    width: 34px; height: 34px; border-radius: 10px; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all .2s ease;
  }
  .icon-btn:hover { border-color: var(--text-2); transform: translateY(-1px); }

  .nav-wrap { position: fixed; top: 22px; left: 50%; transform: translateX(-50%); z-index: 30; }
  .nav-pills {
    position: relative; display: inline-flex; width: 440px; padding: 4px; background: var(--pill-bg); backdrop-filter: blur(20px); border: 1px solid var(--glass-border); border-radius: 999px;
  }
  .nav-pills button {
    position: relative; z-index: 1; flex: 1; text-align: center; font-family: 'IBM Plex Mono', monospace; font-size: 11px; font-weight: 600; letter-spacing: .06em; padding: 8px 0; border-radius: 999px; border: none; background: transparent; color: var(--text-2); cursor: pointer; transition: color .2s ease;
  }
  .nav-pills button.active { color: #0B0D10; }
  .nav-slider {
    position: absolute; top: 4px; bottom: 4px; left: 4px; width: calc(25% - 2px); border-radius: 999px; background: linear-gradient(135deg, #4FD1C5, #FF7A33); transition: transform .3s cubic-bezier(.4, 0, .2, 1); z-index: 0;
  }
  
  .period-caption {
    position: fixed; top: 78px; left: 50%; transform: translateX(-50%); z-index: 30; font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--text-3); letter-spacing: .08em;
  }

  .thread-wrap { position: fixed; top: 0; bottom: 0; left: 50%; width: 1px; z-index: 5; transform: translateX(-50%); }
  .thread-line { position: absolute; inset: 0; background: var(--thread-color); }
  .thread-shimmer {
    position: absolute; left: -1px; width: 3px; height: 250px; background: linear-gradient(180deg, transparent, #4FD1C5, #FF7A33, transparent);
    animation: shimmer-flow 4s linear infinite; opacity: .4; filter: blur(1px);
  }
  @keyframes shimmer-flow { 0% { top: -250px; } 100% { top: 100%; } }

  .stage {
    position: relative; z-index: 10; height: 100vh; width: 100vw; display: flex; align-items: center; justify-content: space-between; padding: 0 6%;
  }
  
  .gauge-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 320px; }
  .gauge-container.center-deck { position: absolute; left: 50%; top: 52%; transform: translate(-50%, -50%); z-index: 12; width: 440px; }
  
  .plant-label { font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; letter-spacing: .25em; text-transform: uppercase; margin-bottom: 20px; text-align: center; }
  .gauge-container.alpha .plant-label { color: #4FD1C5; }
  .gauge-container.beta .plant-label { color: #FF7A33; }
  .gauge-container.center-deck .plant-label { color: var(--text-1); font-size: 13px; margin-bottom: 25px; }

  svg.dial { overflow: visible; display: block; margin: 0 auto; }
  .dial-track { fill: none; stroke: var(--line-hair); stroke-linecap: round; }
  .dial-progress { fill: none; stroke-linecap: round; transition: stroke-dashoffset 0.8s cubic-bezier(.4, 0, .2, 1), stroke 0.4s ease; }
  .dial-tick { stroke: var(--tick-color); stroke-width: 1.5; }
  .dial-bdg-mark { stroke: var(--bdg-mark-color); stroke-width: 3; stroke-linecap: round; opacity: 0.9; }
  .dial-needle-line { stroke-linecap: round; transition: x2 0.8s cubic-bezier(.4, 0, .2, 1), y2 0.8s cubic-bezier(.4, 0, .2, 1), stroke 0.4s ease; }
  .dial-center-dot { fill: var(--bg-deep); stroke: var(--line-hair); stroke-width: 2.5; }
  
  .dial-value { font-family: 'Space Grotesk', sans-serif; font-weight: 700; fill: var(--text-1); text-anchor: middle; transition: fill 0.3s ease; }
  .dial-delta { font-family: 'IBM Plex Mono', monospace; font-weight: 500; fill: var(--text-2); text-anchor: middle; }

  .telemetry { display: flex; gap: 32px; margin-top: 30px; justify-content: center; width: 100%; }
  .gauge-container.center-deck .telemetry { gap: 48px; margin-top: 40px; }
  .tag { text-align: center; }
  .tag .k { font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: .12em; color: var(--text-3); text-transform: uppercase; margin-bottom: 6px; }
  .tag .v { font-family: 'IBM Plex Mono', monospace; font-size: 15px; font-weight: 600; color: var(--text-1); }
  .gauge-container.center-deck .tag .v { font-size: 17px; }
  .tag .v.pos { color: var(--bad); }
  .tag .v.neg { color: var(--good); }

  @media (max-width: 1200px) {
    .stage { flex-direction: column; height: auto; padding: 140px 0 60px; gap: 80px; }
    .gauge-container.center-deck { position: static; transform: none; }
    .thread-wrap { display: none; }
  }
</style>
</head>
<body>

<div class="halves">
  <div class="half alpha"></div>
  <div class="half beta"></div>
</div>

<header>
  <div class="brand">
    <span class="brand-text">TechCorp Global</span>
  </div>
  <div class="header-actions">
    <div class="live-status">
      <div class="eyebrow"><span class="live-dot"></span>SUPPLY CHAIN EFFICIENCY</div>
      <div class="eyebrow" style="margin-top:4px;" id="genTime">--:--</div>
    </div>
    <button id="btn-theme" class="icon-btn" onclick="toggleTheme()" title="Cambia tema">🌙</button>
  </div>
</header>

<div class="nav-wrap">
  <div class="nav-pills" id="navPills">
    <div class="nav-slider" id="navSlider"></div>
    <button data-period="day" class="active">Daily</button>
    <button data-period="week">Weekly</button>
    <button data-period="month">Monthly</button>
    <button data-period="ytd">YTD</button>
  </div>
</div>
<div class="period-caption" id="periodCaption">...</div>

<div class="thread-wrap">
  <div class="thread-line"></div>
  <div class="thread-shimmer"></div>
</div>

<div class="stage">
  <div class="gauge-container alpha">
    <div class="plant-label">PLANT ALPHA</div>
    <svg class="dial" width="220" height="220" id="dialAlpha"></svg>
    <div class="telemetry" id="telAlpha"></div>
  </div>

  <div class="gauge-container center-deck">
    <div class="plant-label">GLOBAL SUPPLY CHAIN</div>
    <svg class="dial" width="320" height="320" id="dialGlobal"></svg>
    <div class="telemetry" id="telGlobal"></div>
  </div>

  <div class="gauge-container beta">
    <div class="plant-label">PLANT BETA</div>
    <svg class="dial" width="220" height="220" id="dialBeta"></svg>
    <div class="telemetry" id="telBeta"></div>
  </div>
</div>

<script>
const DATA = /*JSON_PAYLOAD*/;

const GMIN = 0, GMAX = 100, SWEEP = 270, START = 135;

function polar(cx, cy, r, angleDeg) {
  const rad = (angleDeg) * Math.PI / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx, cy, r, a0, a1) {
  const p0 = polar(cx, cy, r, a0), p1 = polar(cx, cy, r, a1);
  return `M ${p0.x} ${p0.y} A ${r} ${r} 0 1 1 ${p1.x} ${p1.y}`;
}

function buildDial(svgEl, size, isBig) {
  const cx = size / 2, cy = size / 2;
  const r = isBig ? size * 0.38 : size * 0.36;
  const strokeW = isBig ? 10 : 7.5;
  svgEl.innerHTML = "";
  
  const ns = "http://www.w3.org/2000/svg";
  svgEl.setAttribute("viewBox", `0 0 ${size} ${size}`);

  const END = START + SWEEP;

  const track = document.createElementNS(ns, "path");
  track.setAttribute("class", "dial-track");
  track.setAttribute("stroke-width", strokeW);
  track.setAttribute("d", arcPath(cx, cy, r, START, END));
  svgEl.appendChild(track);

  for(let v=0; v<=GMAX; v+=10) {
    const angle = START + (v / GMAX) * SWEEP;
    const p1 = polar(cx, cy, r + (isBig?6:5), angle);
    const p2 = polar(cx, cy, r + (isBig?14:11), angle);
    const tick = document.createElementNS(ns, "line");
    tick.setAttribute("class", "dial-tick");
    tick.setAttribute("x1", p1.x); tick.setAttribute("y1", p1.y);
    tick.setAttribute("x2", p2.x); tick.setAttribute("y2", p2.y);
    svgEl.appendChild(tick);
  }

  const progress = document.createElementNS(ns, "path");
  progress.setAttribute("class", "dial-progress");
  progress.setAttribute("id", svgEl.id + "_progress");
  progress.setAttribute("stroke-width", strokeW);
  progress.setAttribute("d", arcPath(cx, cy, r, START, END));
  const totalLen = 2 * Math.PI * r * (SWEEP / 360);
  progress.setAttribute("stroke-dasharray", totalLen);
  progress.setAttribute("stroke-dashoffset", totalLen);
  svgEl.appendChild(progress);

  const bdgMark = document.createElementNS(ns, "line");
  bdgMark.setAttribute("class", "dial-bdg-mark");
  bdgMark.setAttribute("id", svgEl.id + "_bdgmark");
  svgEl.appendChild(bdgMark);

  const needleLine = document.createElementNS(ns, "line");
  needleLine.setAttribute("class", "dial-needle-line");
  needleLine.setAttribute("id", svgEl.id + "_needle");
  needleLine.setAttribute("x1", cx); needleLine.setAttribute("y1", cy);
  needleLine.setAttribute("x2", cx); needleLine.setAttribute("y2", cy);
  needleLine.setAttribute("stroke-width", isBig ? 4 : 2.8);
  svgEl.appendChild(needleLine);

  const centerDot = document.createElementNS(ns, "circle");
  centerDot.setAttribute("class", "dial-center-dot");
  centerDot.setAttribute("cx", cx); centerDot.setAttribute("cy", cy);
  centerDot.setAttribute("r", isBig ? 6 : 4.5);
  svgEl.appendChild(centerDot);

  const valText = document.createElementNS(ns, "text");
  valText.setAttribute("class", "dial-value");
  valText.setAttribute("id", svgEl.id + "_val");
  valText.setAttribute("x", cx); 
  valText.setAttribute("y", cy + (isBig ? size * 0.32 : size * 0.34));
  valText.setAttribute("font-size", isBig ? "48px" : "34px");
  svgEl.appendChild(valText);

  const deltaText = document.createElementNS(ns, "text");
  deltaText.setAttribute("class", "dial-delta");
  deltaText.setAttribute("id", svgEl.id + "_delta");
  deltaText.setAttribute("x", cx); 
  deltaText.setAttribute("y", cy + (isBig ? size * 0.32 + 26 : size * 0.34 + 20));
  deltaText.setAttribute("font-size", isBig ? "12.5px" : "11px");
  svgEl.appendChild(deltaText);

  return { cx, cy, r, len: totalLen, isBig };
}

const geomAlpha  = buildDial(document.getElementById('dialAlpha'), 220, false);
const geomBeta   = buildDial(document.getElementById('dialBeta'), 220, false);
const geomGlobal = buildDial(document.getElementById('dialGlobal'), 320, true);

function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

function animateNumber(el, from, to, suffix, decimals, duration) {
  const start = performance.now();
  function frame(now) {
    const t = Math.min(1, (now - start) / duration);
    const val = from + (to - from) * easeOutCubic(t);
    el.textContent = val.toFixed(decimals) + suffix;
    if(t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function updateDial(svgId, geom, d) {
  const progress = document.getElementById(svgId + '_progress');
  const needle   = document.getElementById(svgId + '_needle');
  const bdgMark  = document.getElementById(svgId + '_bdgmark');
  const valEl    = document.getElementById(svgId + '_val');
  const deltaEl  = document.getElementById(svgId + '_delta');

  const goodCol = getComputedStyle(document.documentElement).getPropertyValue('--good').trim();
  const badCol  = getComputedStyle(document.documentElement).getPropertyValue('--bad').trim();
  const color   = d.eff >= d.bdg ? goodCol : badCol;

  const effPct = Math.min(Math.max(d.eff, GMIN), GMAX) / GMAX;
  const effAngle = START + effPct * SWEEP;
  const needleLen = geom.r - (geom.isBig ? 14 : 11);
  const needlePos = polar(geom.cx, geom.cy, needleLen, effAngle);
  
  needle.setAttribute('x2', needlePos.x);
  needle.setAttribute('y2', needlePos.y);
  needle.setAttribute('stroke', color);

  const offset = geom.len * (1 - effPct);
  progress.style.stroke = color;
  progress.style.strokeDashoffset = offset;

  const bdgPct = Math.min(Math.max(d.bdg, GMIN), GMAX) / GMAX;
  const bdgAngle = START + bdgPct * SWEEP;
  const p1 = polar(geom.cx, geom.cy, geom.r - (geom.isBig?5:4), bdgAngle);
  const p2 = polar(geom.cx, geom.cy, geom.r + (geom.isBig?12:9), bdgAngle);
  bdgMark.setAttribute('x1', p1.x); bdgMark.setAttribute('y1', p1.y);
  bdgMark.setAttribute('x2', p2.x); bdgMark.setAttribute('y2', p2.y);

  valEl.style.fill = color;
  const prevVal = parseFloat(valEl.textContent) || 0;
  animateNumber(valEl, prevVal, d.eff, '%', 1, 800);

  const delta = d.eff - d.bdg;
  deltaEl.textContent = `BDG ${d.bdg.toFixed(1)}%  ·  ${delta >= 0 ? '+' : ''}${delta.toFixed(1)} pt`;
}

function fmtInt(n) { return Math.round(n).toLocaleString('en-US'); }

function updateTelemetry(elId, d) {
  const el = document.getElementById(elId);
  el.innerHTML = `
    <div class="tag"><div class="k">STD (H)</div><div class="v">${fmtInt(d.std)}</div></div>
    <div class="tag"><div class="k">ACT (H)</div><div class="v">${fmtInt(d.act)}</div></div>
    <div class="tag"><div class="k">VAR</div><div class="v ${d.var > 0 ? 'pos' : 'neg'}">${d.var >= 0 ? '+' : ''}€ ${fmtInt(d.var)}</div></div>
  `;
}

function render(period) {
  const d = DATA[period];
  document.getElementById('periodCaption').textContent = d.caption;
  updateDial('dialAlpha',  geomAlpha, d.alpha);
  updateDial('dialBeta',   geomBeta, d.beta);
  updateDial('dialGlobal', geomGlobal, d.global);
  updateTelemetry('telAlpha',  d.alpha);
  updateTelemetry('telBeta',   d.beta);
  updateTelemetry('telGlobal', d.global);
}

const pillButtons = document.querySelectorAll('.nav-pills button');
const slider = document.getElementById('navSlider');
pillButtons.forEach((btn, idx) => {
  btn.addEventListener('click', () => {
    pillButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    slider.style.transform = `translateX(${idx * 100}%)`;
    render(btn.dataset.period);
  });
});

const GEN_TS = "/*GEN_TS*/";
document.getElementById('genTime').textContent = "Updated: " + GEN_TS;

let DARK = window.matchMedia('(prefers-color-scheme: dark)').matches;
function applyTheme() {
  const btn = document.getElementById('btn-theme');
  if (DARK) { document.body.classList.remove('light-mode'); btn.textContent = '🌙'; }
  else      { document.body.classList.add('light-mode');    btn.textContent = '☀️️'; }
}
function toggleTheme() { DARK = !DARK; applyTheme(); }
applyTheme();

render('day');
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────
#  ESECUZIONE E GENERAZIONE FILE FOTOGRAFIA STATICA
# ─────────────────────────────────────────────────────────────────

def build_dashboard():
    print("⏳ Generazione metriche Supply Chain multi-plant aggregate...")
    payload = generate_mock_payload()

    print("⏳ Compilazione template SVG Vettoriale Offline...")
    html = HTML_TEMPLATE.replace("/*JSON_PAYLOAD*/", json.dumps(payload))
    html = html.replace("/*GEN_TS*/", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE_NAME)
    
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    print("═" * 65)
    print("🚀 COMMAND DECK GENERATO CON SUCCESSO!")
    print(f"   🔗 Apri nel browser: {os.path.abspath(final_path)}")
    print("═" * 65)

if __name__ == "__main__":
    build_dashboard()
