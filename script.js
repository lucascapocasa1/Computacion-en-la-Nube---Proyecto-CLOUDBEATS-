/* ================================================================
   CloudBets — script.js
   Computación en la Nube · 2025
   ================================================================ */

const API_BASE = "http://localhost:8000";
const HISTORY_KEY = "cloudbets_history";
const MAX_HISTORY = 10;

/* ── Metadatos estáticos ─────────────────────────────────────── */
const LEAGUES = [
  { id:39,  name:"Premier League",      flag:"🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
  { id:140, name:"La Liga",             flag:"🇪🇸" },
  { id:135, name:"Serie A",             flag:"🇮🇹" },
  { id:78,  name:"Bundesliga",          flag:"🇩🇪" },
  { id:61,  name:"Ligue 1",             flag:"🇫🇷" },
  { id:2,   name:"Champions League",    flag:"🏆" },
  { id:11,  name:"Copa Libertadores",   flag:"🌎" },
  { id:13,  name:"Copa Sudamericana",   flag:"🌎" },
  { id:128, name:"Liga Profesional AR", flag:"🇦🇷" },
  { id:130, name:"Primera Nacional AR", flag:"🇦🇷" },
];

const STAT_META = [
  { key:"corners",        label:"Corners",          icon:"⛳" },
  { key:"yellow_cards",   label:"Amarillas",         icon:"🟨" },
  { key:"red_cards",      label:"Rojas",             icon:"🟥" },
  { key:"offsides",       label:"Offsides",          icon:"🚩" },
  { key:"goals_scored",   label:"Goles a favor",     icon:"⚽" },
  { key:"goals_conceded", label:"Goles en contra",   icon:"🥅" },
  { key:"shots_on_goal",  label:"Tiros al arco",     icon:"🎯" },
  { key:"fouls",          label:"Faltas",            icon:"💥" },
];

const LIVE_STAT_META = [
  { key:"possession",    label:"Posesión",       bar:true  },
  { key:"shots_total",   label:"Tiros totales",  bar:true  },
  { key:"shots_on_goal", label:"Al arco",        bar:true  },
  { key:"corners",       label:"Corners",        bar:true  },
  { key:"fouls",         label:"Faltas",         bar:true  },
  { key:"yellow_cards",  label:"Amarillas",      bar:false },
  { key:"offsides",      label:"Offsides",       bar:false },
  { key:"saves",         label:"Atajadas",       bar:false },
];

const EVENT_ICONS = {
  "Normal Goal":"⚽", "Own Goal":"⚽(OG)", "Penalty":"⚽(P)", "Missed Penalty":"❌",
  "Yellow Card":"🟨", "Red Card":"🟥",     "Yellow Red Card":"🟨🟥",
  "subst":"🔄",       "Var":"📺",
};

/* ── Estado global ───────────────────────────────────────────── */
let currentFixtureId   = null;
let currentMatchData   = null;   // último resultado completo (para PDF e historial)
let liveRefreshTimer   = null;
let standingsOpen      = false;
let historyOpen        = false;

/* ── Utilidades ──────────────────────────────────────────────── */
const $  = id => document.getElementById(id);
const qs = sel => document.querySelector(sel);

function showError(msg) {
  const el = $("error-box");
  el.textContent = "❌ " + msg;
  el.classList.add("visible");
}
function clearError()  { $("error-box").classList.remove("visible"); }
function setLoading(t) { $("loading").classList.add("visible"); $("loading-text").textContent = t; }
function stopLoading() { $("loading").classList.remove("visible"); }

/* ── Navbar: dropdowns ───────────────────────────────────────── */
function toggleStandings() {
  standingsOpen = !standingsOpen;
  if (standingsOpen && historyOpen) toggleHistory();   // cerrar el otro
  $("standings-dropdown").classList.toggle("open", standingsOpen);
  $("btn-standings").classList.toggle("active", standingsOpen);
}

function toggleHistory() {
  historyOpen = !historyOpen;
  if (historyOpen && standingsOpen) toggleStandings(); // cerrar el otro
  $("history-dropdown").classList.toggle("open", historyOpen);
  renderHistoryPanel();
}

// Cerrar dropdowns al hacer click fuera
document.addEventListener("click", e => {
  const inStandings = e.target.closest("#standings-dropdown") || e.target.closest("#btn-standings");
  const inHistory   = e.target.closest("#history-dropdown")   || e.target.closest("#btn-history");
  if (!inStandings && standingsOpen) toggleStandings();
  if (!inHistory   && historyOpen)   toggleHistory();
});

/* ── Tabla de posiciones ─────────────────────────────────────── */
function buildLeagueList() {
  const list = $("league-list");
  list.innerHTML = "";
  LEAGUES.forEach(lg => {
    const btn = document.createElement("button");
    btn.className = "league-btn";
    btn.innerHTML = `<span>${lg.flag}</span>${lg.name}`;
    btn.onclick = e => { e.stopPropagation(); loadStandings(lg.id, btn); };
    list.appendChild(btn);
  });
}

async function loadStandings(leagueId, btnEl) {
  document.querySelectorAll(".league-btn").forEach(b => b.classList.remove("active"));
  btnEl.classList.add("active");

  const container = $("dropdown-standings");
  container.innerHTML = `<div class="standings-loading">Cargando tabla...</div>`;

  try {
    const res  = await fetch(`${API_BASE}/analyze/standings?league_id=${leagueId}`);
    if (!res.ok) throw new Error("Sin datos para esa liga");
    renderStandings(await res.json(), container);
  } catch(e) {
    container.innerHTML = `<div class="standings-loading" style="color:var(--red)">❌ ${e.message}</div>`;
  }
}

function renderStandings(data, container) {
  const groups = data.standings || [];
  if (!groups.length) {
    container.innerHTML = `<div class="standings-loading">Sin datos disponibles</div>`;
    return;
  }

  let html = `<div class="standings-league-name">${data.league_name} · ${data.season}</div>`;

  groups.forEach(group => {
    html += `<table class="standings-table">
      <thead><tr>
        <th>#</th><th>Equipo</th><th>PJ</th><th>G</th><th>E</th>
        <th>P</th><th>GD</th><th>Pts</th><th>Forma</th>
      </tr></thead><tbody>`;

    group.forEach(row => {
      const desc   = (row.description || "").toLowerCase();
      const rowCls = desc.includes("champions") ? "row-cl"
                   : (desc.includes("europa") || desc.includes("conference")) ? "row-euro"
                   : desc.includes("relega") ? "row-rel" : "";

      const formDots = (row.form || "").split("").slice(-5)
        .map(r => `<div class="form-dot ${r}"></div>`).join("");

      const gdSign = row.goal_diff > 0 ? "+" : "";
      const gdColor = row.goal_diff >= 0 ? "var(--green)" : "var(--red)";

      html += `<tr class="${rowCls}">
        <td>${row.rank}</td>
        <td title="${row.team_name}">${row.team_name}</td>
        <td>${row.played}</td><td>${row.won}</td><td>${row.draw}</td><td>${row.lost}</td>
        <td style="color:${gdColor}">${gdSign}${row.goal_diff}</td>
        <td class="pts-cell">${row.points}</td>
        <td><div class="form-dots">${formDots}</div></td>
      </tr>`;
    });
    html += `</tbody></table>`;
  });

  container.innerHTML = html;
}

/* ── Historial (localStorage) ────────────────────────────────── */
function getHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; }
  catch { return []; }
}

function saveToHistory(matchData) {
  const history = getHistory().filter(h => h.fixture_id !== matchData.fixture_id);
  history.unshift({
    fixture_id: matchData.fixture_id,
    home:       matchData.match.home,
    away:       matchData.match.away,
    league_id:  matchData.match.league_id,
    season:     matchData.match.season,
    saved_at:   new Date().toISOString(),
    best_bet:   matchData.recommendations?.safe?.bet || "—",
  });
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
}

function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
  renderHistoryPanel();
}

function renderHistoryPanel() {
  const container = $("history-list");
  const history   = getHistory();

  if (!history.length) {
    container.innerHTML = `<p class="history-empty">Sin análisis guardados todavía.<br>Analizá un partido para empezar.</p>`;
    return;
  }

  container.innerHTML = history.map(h => {
    const date = new Date(h.saved_at).toLocaleString("es-AR", {
      day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit"
    });
    return `<div class="history-item" onclick="reloadFromHistory(${h.fixture_id})">
      <div class="history-teams">${h.home} vs ${h.away}</div>
      <div class="history-meta">Liga ${h.league_id} · ${h.season} · ${h.best_bet}</div>
      <div class="history-date">${date}</div>
    </div>`;
  }).join("");
}

async function reloadFromHistory(fixtureId) {
  if (historyOpen) toggleHistory();
  runAnalysisByFixture(fixtureId);
}

/* ── Partidos del día ────────────────────────────────────────── */
async function loadMatches() {
  try {
    const res     = await fetch(`${API_BASE}/matches/today`);
    if (!res.ok)  throw new Error("No se pudieron cargar los partidos");
    const matches = await res.json();
    const list    = $("matches-list");
    list.innerHTML = "";

    if (!matches.length) {
      list.innerHTML = `<p style="color:var(--muted);font-family:var(--font-m);font-size:13px;">
        No hay partidos hoy en las ligas configuradas.</p>`;
      return;
    }

    matches.forEach(match => {
      const el = document.createElement("div");
      el.className = "match-item" + (match.live ? " live-match" : "");

      let badge = match.live
        ? `<span class="badge-live">🔴 EN VIVO ${match.minute ? match.minute+"'" : ""}</span>`
        : match.finished
          ? `<span class="badge-finished">✓ FINALIZADO</span>`
          : `<span class="badge-time">${match.time || "—"} ART</span>`;

      el.innerHTML = `
        <div>
          <div class="match-teams">${match.home} vs ${match.away}</div>
          <div class="match-details">
            <span class="match-league">${match.league}</span>
            ${badge}
          </div>
        </div>
        <button class="btn-analyze">VER CUOTAS</button>`;

      const analyze = () => {
        document.querySelectorAll(".match-item").forEach(i => i.classList.remove("selected"));
        el.classList.add("selected");
        runAnalysisByFixture(match.id);
      };

      el.querySelector(".btn-analyze").onclick = e => { e.stopPropagation(); analyze(); };
      el.onclick = analyze;
      list.appendChild(el);
    });

  } catch(e) { showError(e.message); }
}

/* ── Análisis principal ──────────────────────────────────────── */
async function runAnalysisByFixture(fixtureId) {
  currentFixtureId = fixtureId;
  clearError();
  stopLiveRefresh();
  setLoading("ANALIZANDO PARTIDO...");

  // Limpiar estado anterior
  $("content-tabs").classList.remove("visible");
  $("recs-section").classList.remove("visible");
  $("live-stats-section").classList.remove("visible");
  $("stats-grid").innerHTML   = "";
  $("lineups-grid").innerHTML = "";
  $("events-list").innerHTML  = "";
  switchTab("stats");

  try {
    const [anaRes, linRes, evRes] = await Promise.all([
      fetch(`${API_BASE}/analyze?fixture_id=${fixtureId}`),
      fetch(`${API_BASE}/analyze/lineups?fixture_id=${fixtureId}`),
      fetch(`${API_BASE}/analyze/events?fixture_id=${fixtureId}`),
    ]);

    if (!anaRes.ok) throw new Error(await anaRes.text());

    const data    = await anaRes.json();
    const lineups = linRes.ok ? await linRes.json() : {};
    const events  = evRes.ok  ? await evRes.json()  : [];

    // Guardar referencia para PDF e historial
    currentMatchData = { ...data, fixture_id: fixtureId };
    saveToHistory(currentMatchData);

    stopLoading();
    renderMatchHeader(data.match);
    renderStats(data.home_stats, data.away_stats);
    renderRecs(data.recommendations);
    renderLineups(lineups, data.match.home, data.match.away);
    renderEvents(events);

    $("content-tabs").classList.add("visible", "animate-in");
    $("btn-export-pdf").classList.add("visible");
    $("match-header").scrollIntoView({ behavior: "smooth" });

    // Si está en vivo: cargar stats en vivo + auto-refresh cada 60s
    if (data.match.status && ["1H","2H","HT","ET","P"].includes(data.match.status)) {
      await loadLiveStats(fixtureId);
      startLiveRefresh(fixtureId);
    }

  } catch(e) {
    stopLoading();
    showError(e.message);
  }
}

async function runDemo() {
  clearError();
  stopLiveRefresh();
  setLoading("CARGANDO DEMO — BOCA VS RIVER...");
  try {
    const res = await fetch(`${API_BASE}/analyze/demo`);
    if (!res.ok) throw new Error(`Error ${res.status}`);
    const data = await res.json();
    currentMatchData = { ...data, fixture_id: 0 };
    stopLoading();
    renderMatchHeader(data.match);
    renderStats(data.home_stats, data.away_stats);
    renderRecs(data.recommendations);
    renderLineups({}, data.match.home, data.match.away);
    renderEvents([]);
    $("content-tabs").classList.add("visible", "animate-in");
    $("btn-export-pdf").classList.add("visible");
  } catch(e) {
    stopLoading();
    showError("¿Está corriendo el backend en localhost:8000? — " + e.message);
  }
}

/* ── Render: cabecera del partido ────────────────────────────── */
function renderMatchHeader(match) {
  $("home-name").textContent = match.home;
  $("away-name").textContent = match.away;

  const isLive = match.status && ["1H","2H","HT","ET","P"].includes(match.status);
  const liveIndicator = isLive
    ? `<span class="live-indicator"><span class="live-dot"></span>EN VIVO ${match.minute ? match.minute+"'" : ""}</span>`
    : "";

  $("match-header-top").innerHTML = `
    <div class="vs-row">
      <div class="team-name">${match.home}</div>
      <div class="vs-badge">VS</div>
      <div class="team-name">${match.away}</div>
    </div>
    ${liveIndicator}`;

  $("match-meta").textContent =
    `Liga ${match.league_id} · Temporada ${match.season}` +
    (match.has_real_odds ? " · ✓ Cuotas Bet365 reales" : " · Cuotas estimadas") +
    (match.demo ? " · MODO DEMO" : "");

  $("match-header").classList.add("visible", "animate-in");
}

/* ── Render: estadísticas de temporada ───────────────────────── */
function renderStats(home, away) {
  const grid = $("stats-grid");
  grid.innerHTML = "";
  STAT_META.forEach(({ key, label, icon }) => {
    const hv  = +(home[key] ?? 0);
    const av  = +(away[key] ?? 0);
    const tot = Math.round((hv + av) * 10) / 10;
    const pct = Math.min(100, (tot / Math.max(tot, 12)) * 100);
    grid.innerHTML += `
      <div class="stat-card">
        <div class="stat-label">${icon} ${label}</div>
        <div class="stat-values">
          <div><div class="stat-val home">${hv}</div><div class="stat-sublabel">Local</div></div>
          <div><div class="stat-val away">${av}</div><div class="stat-sublabel">Visita</div></div>
          <div><div class="stat-val combined">${tot}</div><div class="stat-sublabel">Total</div></div>
        </div>
        <div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%"></div></div>
      </div>`;
  });
}

/* ── Stats en vivo ───────────────────────────────────────────── */
async function loadLiveStats(fixtureId) {
  try {
    const res  = await fetch(`${API_BASE}/analyze/live-stats?fixture_id=${fixtureId}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.length) return;
    renderLiveStats(data);
    $("live-stats-section").classList.add("visible");
  } catch { /* silencioso — no bloquear si falla */ }
}

function renderLiveStats(teams) {
  // teams[0]=local, teams[1]=visita
  const home = teams[0] || {};
  const away = teams[1] || {};

  $("live-refresh-time").textContent = `Última actualización: ${new Date().toLocaleTimeString("es-AR")}`;

  const grid = $("live-stats-grid");
  grid.innerHTML = "";

  LIVE_STAT_META.forEach(({ key, label, bar }) => {
    let hv = home[key] ?? 0;
    let av = away[key] ?? 0;

    // La posesión viene como "55%" — extraer número
    if (key === "possession") {
      hv = parseInt(hv) || 0;
      av = parseInt(av) || 0;
    } else {
      hv = +hv || 0;
      av = +av || 0;
    }

    const total = hv + av || 1;
    const hPct  = Math.round((hv / total) * 100);
    const aPct  = 100 - hPct;

    const barHtml = bar ? `
      <div class="live-stats-bar-wrap">
        <div class="live-bar home" style="width:${hPct}%"></div>
        <div class="live-bar away" style="width:${aPct}%"></div>
      </div>` : "";

    const suffix = key === "possession" ? "%" : "";

    grid.innerHTML += `
      <div class="live-stat-row">
        <div class="live-stat-home">${hv}${suffix}</div>
        ${barHtml}
        <div class="live-stat-label">${label}</div>
        ${barHtml}
        <div class="live-stat-away">${av}${suffix}</div>
      </div>`;
  });
}

function startLiveRefresh(fixtureId) {
  liveRefreshTimer = setInterval(() => loadLiveStats(fixtureId), 60_000);
}

function stopLiveRefresh() {
  if (liveRefreshTimer) { clearInterval(liveRefreshTimer); liveRefreshTimer = null; }
}

/* ── Render: recomendaciones ─────────────────────────────────── */
function renderRecs(recs) {
  const grid = $("recs-grid");
  grid.innerHTML = "";

  [
    { rec: recs.safe,     level: "safe",     label: "🟢 MEJOR EV"    },
    { rec: recs.risky,    level: "risky",    label: "🟡 2° MEJOR EV" },
    { rec: recs.longshot, level: "longshot", label: "🔴 3° MEJOR EV" },
  ].forEach(({ rec, level, label }) => {
    if (!rec) return;
    const probPct  = rec.our_probability ?? (Math.round(rec.confidence * 100) + "%");
    const probNum  = parseFloat(probPct);
    const hasValue = rec.has_value ?? (rec.ev_raw > 0);
    const evColor  = hasValue ? "var(--green)" : "var(--red)";
    const clr      = level === "safe" ? "green" : level === "risky" ? "yellow" : "red";

    grid.innerHTML += `
      <div class="rec-card ${level} animate-in">
        <div class="rec-level ${level}">
          ${label}
          <span class="value-badge ${hasValue ? "positive" : "negative"}">
            ${hasValue ? "✓ CON VALOR" : "SIN VALOR"}
          </span>
        </div>
        <div class="rec-market">${rec.market}</div>
        <div class="rec-bet">${rec.bet}</div>
        <div class="rec-meta">
          <div class="meta-item">
            <div class="meta-val ${clr}">${probPct}</div>
            <div class="meta-label">Prob. propia</div>
          </div>
          <div class="meta-item">
            <div class="meta-val" style="color:var(--gold)">${rec.house_odds ?? rec.estimated_odds}</div>
            <div class="meta-label">Cuota Bet365</div>
          </div>
          <div class="meta-item">
            <div class="meta-val" style="color:${evColor}">${rec.expected_value}</div>
            <div class="meta-label">EV</div>
          </div>
        </div>
        <div class="confidence-bar">
          <div class="confidence-fill ${level}" style="width:${probNum}%"></div>
        </div>
        <div class="rec-description">${rec.description}</div>
        <div class="betano-tag">📍 Bet365 · ${rec.betano_market}</div>
      </div>`;
  });

  $("recs-section").classList.add("visible", "animate-in");
}

/* ── Render: alineaciones ────────────────────────────────────── */
function renderLineups(lineups, homeName, awayName) {
  const grid = $("lineups-grid");
  grid.innerHTML = "";

  const teamNames = Object.keys(lineups);
  if (!teamNames.length) {
    grid.innerHTML = `<div style="grid-column:1/-1;color:var(--muted);font-family:var(--font-m);
      font-size:13px;padding:32px;text-align:center;">
      Alineaciones no disponibles todavía (se publican ~1h antes del partido)</div>`;
    return;
  }

  teamNames
    .sort((a, b) => a === homeName ? -1 : b === homeName ? 1 : 0)
    .forEach(name => {
      const team   = lineups[name];
      const isHome = name === homeName;

      // Agrupar por fila del grid ("1:1" → fila 1)
      const rows = {};
      team.startXI.forEach(p => {
        if (!p.grid) return;
        const row = p.grid.split(":")[0];
        (rows[row] = rows[row] || []).push(p);
      });

      const fieldHTML = Object.keys(rows).sort((a,b) => +a - +b).map(r =>
        `<div class="field-row">${rows[r].map(p => `
          <div class="player-chip ${p.pos === "G" ? "gk" : ""}">
            <div class="player-num">${p.number ?? ""}</div>
            <div class="player-name-chip">${lastName(p.name)}</div>
          </div>`).join("")}</div>`
      ).join("");

      const subsHTML = (team.substitutes || []).map(p =>
        `<div class="sub-item">
          <span class="sub-num">${p.number ?? ""}</span>
          <span>${p.name ?? ""}</span>
        </div>`
      ).join("") || `<div class="sub-item" style="font-size:11px">—</div>`;

      grid.innerHTML += `
        <div class="lineup-card animate-in">
          <div class="lineup-header">
            <div class="lineup-team" style="color:${isHome ? "var(--accent)" : "var(--accent2)"}">
              ${team.team_name}
            </div>
            <div class="lineup-meta">Formación: ${team.formation} · DT: ${team.coach}</div>
          </div>
          <div class="lineup-field">${fieldHTML}</div>
          <div class="subs-list">
            <div class="subs-title">Suplentes</div>
            ${subsHTML}
          </div>
        </div>`;
    });
}

/* ── Render: eventos ─────────────────────────────────────────── */
function renderEvents(events) {
  const list = $("events-list");
  list.innerHTML = "";

  const relevant = events.filter(e => ["Goal","Card","subst"].includes(e.type));
  if (!relevant.length) {
    list.innerHTML = `<div style="color:var(--muted);font-family:var(--font-m);font-size:13px;
      padding:24px;text-align:center;">
      Sin eventos registrados aún.</div>`;
    return;
  }

  relevant.forEach(ev => {
    const icon   = EVENT_ICONS[ev.detail] ?? (ev.type === "subst" ? "🔄" : ev.type === "Card" ? "🟨" : "⚽");
    const min    = ev.extra ? `${ev.minute}+${ev.extra}'` : `${ev.minute}'`;
    const detail = ev.assist ? `${ev.detail} · Asist: ${ev.assist}` : ev.detail;

    list.innerHTML += `
      <div class="event-item animate-in">
        <div class="event-min">${min}</div>
        <div class="event-icon">${icon}</div>
        <div class="event-body">
          <div class="event-player">${ev.player || "—"}</div>
          <div class="event-detail">${detail || ""}</div>
        </div>
        <div class="event-team">${ev.team || ""}</div>
      </div>`;
  });
}

/* ── Tabs ────────────────────────────────────────────────────── */
function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b, i) => {
    b.classList.toggle("active", ["stats","lineups","events"][i] === name);
  });
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  $(`panel-${name}`).classList.add("active");
}

/* ── Exportar PDF ────────────────────────────────────────────── */
function exportPDF() {
  if (!currentMatchData) return;

  const { match, home_stats, away_stats, recommendations } = currentMatchData;
  const recs = recommendations || {};

  const rows = STAT_META.map(({ key, label, icon }) => {
    const hv  = +(home_stats[key] ?? 0);
    const av  = +(away_stats[key] ?? 0);
    return `<tr>
      <td>${icon} ${label}</td>
      <td style="color:#00e5ff;text-align:center">${hv}</td>
      <td style="color:#ff3d71;text-align:center">${av}</td>
      <td style="color:#ffd60a;text-align:center">${Math.round((hv+av)*10)/10}</td>
    </tr>`;
  }).join("");

  const recRows = ["safe","risky","longshot"].map((level, i) => {
    const rec = recs[level];
    if (!rec) return "";
    const labels = ["🟢 Mejor EV","🟡 2° Mejor EV","🔴 3° Mejor EV"];
    return `<tr>
      <td>${labels[i]}</td>
      <td>${rec.market}</td>
      <td><strong>${rec.bet}</strong></td>
      <td style="text-align:center">${rec.our_probability ?? "—"}</td>
      <td style="text-align:center">${rec.house_odds ?? rec.estimated_odds ?? "—"}</td>
      <td style="text-align:center;color:${rec.has_value?"#00e096":"#ff3d71"}">${rec.expected_value}</td>
    </tr>`;
  }).join("");

  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"/>
  <title>CloudBets — ${match.home} vs ${match.away}</title>
  <style>
    body { font-family: Arial, sans-serif; font-size: 13px; color: #111; margin: 32px; }
    h1   { font-size: 26px; margin-bottom: 4px; }
    h2   { font-size: 16px; color: #444; margin: 20px 0 8px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
    .meta { color: #666; font-size: 11px; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
    th    { background: #f0f0f0; padding: 7px 10px; text-align: left; font-size: 11px; }
    td    { padding: 6px 10px; border-bottom: 1px solid #eee; }
    .disclaimer { font-size: 10px; color: #888; margin-top: 24px; border-top: 1px solid #eee; padding-top: 10px; }
  </style></head><body>
  <h1>${match.home} vs ${match.away}</h1>
  <p class="meta">Liga ${match.league_id} · Temporada ${match.season} · ${new Date().toLocaleString("es-AR")}
    ${match.has_real_odds ? " · Cuotas Bet365 reales" : " · Cuotas estimadas"}</p>

  <h2>Estadísticas de Temporada</h2>
  <table>
    <thead><tr><th>Estadística</th><th>Local</th><th>Visita</th><th>Total</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>

  <h2>Apuestas Recomendadas por EV</h2>
  <table>
    <thead><tr><th>Nivel</th><th>Mercado</th><th>Apuesta</th><th>Prob.</th><th>Cuota</th><th>EV</th></tr></thead>
    <tbody>${recRows}</tbody>
  </table>

  <p class="disclaimer">⚠️ Estas recomendaciones son estimaciones estadísticas. No garantizan ganancias. Apostá con responsabilidad. · CloudBets · Computación en la Nube</p>
  </body></html>`;

  // Abrir ventana y disparar impresión (el navegador la convierte en PDF)
  const win = window.open("", "_blank");
  win.document.write(html);
  win.document.close();
  win.focus();
  setTimeout(() => { win.print(); win.close(); }, 400);
}

/* ── Helpers ─────────────────────────────────────────────────── */
function lastName(fullName) {
  if (!fullName) return "—";
  const parts = fullName.trim().split(" ");
  return parts[parts.length - 1];
}

/* ── Init ────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  buildLeagueList();
  loadMatches();
});