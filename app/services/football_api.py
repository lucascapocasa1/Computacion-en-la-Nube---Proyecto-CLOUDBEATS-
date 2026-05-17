"""
football_api.py — Comunicación con api-sports.io

Zona horaria: America/Argentina/Buenos_Aires (UTC-3).
Bookmaker:    Bet365 (ID 6).
Fallback:     Si season actual devuelve played=0, reintenta con 2024.

Factor local/visitante: /teams/statistics separa stats de home y away.
Stats en vivo:          /fixtures/statistics durante partidos en curso.
"""

import requests, logging
from datetime import datetime
from zoneinfo  import ZoneInfo
from config    import API_KEY, BASE_URL, IMPORTANT_LEAGUES

HEADERS          = {"x-apisports-key": API_KEY}
FALLBACK_SEASON  = 2024
TZ_AR            = ZoneInfo("America/Argentina/Buenos_Aires")
BOOKMAKER_BET365 = 6
LIVE_STATUSES    = {"1H", "2H", "HT", "ET", "BT", "P", "SUSP", "INT", "LIVE"}

log = logging.getLogger("cloudbets")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(endpoint, params):
    resp = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _to_ar_time(utc_iso):
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    return dt.astimezone(TZ_AR).strftime("%H:%M")

def _now_ar():
    return datetime.now(TZ_AR)

def _int(v):
    try:    return int(v) if v is not None else 0
    except: return 0

def _float(v):
    try:    return float(v) if v is not None else 0.0
    except: return 0.0

def _empty_stats():
    return {k: 0.0 for k in (
        "corners", "yellow_cards", "red_cards", "offsides",
        "goals_scored", "goals_conceded", "shots_on_goal", "fouls"
    )}

def _sum_cards(d):
    total = 0
    for pd in d.values():
        if isinstance(pd, dict):
            total += _int(pd.get("total", 0))
    return total


# ── Partidos del día ──────────────────────────────────────────────────────────

def get_today_matches():
    today_ar = _now_ar().strftime("%Y-%m-%d")
    log.info(f"Buscando partidos para fecha Argentina: {today_ar}")
    data    = _get("fixtures", {"date": today_ar})
    matches = []
    for m in data.get("response", []):
        if m["league"]["id"] not in IMPORTANT_LEAGUES:
            continue
        status_short = m["fixture"]["status"]["short"]
        matches.append({
            "id":        m["fixture"]["id"],
            "home":      m["teams"]["home"]["name"],
            "away":      m["teams"]["away"]["name"],
            "time":      _to_ar_time(m["fixture"]["date"]),
            "league":    m["league"]["name"],
            "league_id": m["league"]["id"],
            "season":    m["league"]["season"],
            "status":    status_short,
            "live":      status_short in LIVE_STATUSES,
            "finished":  status_short == "FT",
            "minute":    m["fixture"]["status"].get("elapsed"),
        })
    log.info(f"Partidos: {len(matches)} ({sum(1 for m in matches if m['live'])} en vivo)")
    return matches


# ── Equipos de un fixture ─────────────────────────────────────────────────────

def get_fixture_teams(fixture_id):
    data = _get("fixtures", {"id": fixture_id})
    resp = data.get("response", [])
    if not resp:
        raise ValueError(f"Fixture {fixture_id} no encontrado.")
    m = resp[0]
    return {
        "home_id":   m["teams"]["home"]["id"],
        "home_name": m["teams"]["home"]["name"],
        "away_id":   m["teams"]["away"]["id"],
        "away_name": m["teams"]["away"]["name"],
        "league_id": m["league"]["id"],
        "season":    m["league"]["season"],
        "status":    m["fixture"]["status"]["short"],
        "minute":    m["fixture"]["status"].get("elapsed"),
    }


# ── Stats de temporada con factor local/visitante ─────────────────────────────

def get_team_season_stats(team_id, league_id, season, is_home: bool):
    """
    Obtiene las stats de la temporada.
    `is_home` determina si usamos promedios de local o de visita
    de /teams/statistics, lo cual mejora la precisión del modelo.
    Reintenta con FALLBACK_SEASON si no hay datos.
    """
    stats = _fetch_stats(team_id, league_id, season, is_home)
    if stats is None and season != FALLBACK_SEASON:
        log.warning(f"  Sin datos season={season}, reintentando con {FALLBACK_SEASON}")
        stats = _fetch_stats(team_id, league_id, FALLBACK_SEASON, is_home)
    return stats or _empty_stats()


def _fetch_stats(team_id, league_id, season, is_home: bool):
    log.info(f"[teams/statistics] team={team_id} league={league_id} season={season} is_home={is_home}")
    data = _get("teams/statistics", {"team": team_id, "league": league_id, "season": season})
    r    = data.get("response", {})
    if not r:
        return None

    # Elegir contexto: home o away según el rol del equipo en este partido
    ctx   = "home" if is_home else "away"
    total = r.get("fixtures", {}).get("played", {})
    played = _int(total.get(ctx, 0))
    log.info(f"  partidos jugados como {'local' if is_home else 'visita'}: {played}")

    if played == 0:
        # Fallback: usar total si el desglose no tiene datos
        played = _int(total.get("total", 0))
        if played == 0:
            return None
        ctx = "total"   # usar goles totales
        log.warning(f"  Usando stats totales como fallback (played_ctx=0)")

    # Goles: api devuelve promedios separados por home/away/total
    goals_for     = r.get("goals", {}).get("for",     {})
    goals_against = r.get("goals", {}).get("against", {})
    goals_scored   = _float(goals_for.get("average",    {}).get(ctx) or goals_for.get("average",    {}).get("total"))
    goals_conceded = _float(goals_against.get("average", {}).get(ctx) or goals_against.get("average", {}).get("total"))

    # Tarjetas: solo vienen en total, dividir por played_total
    played_total   = _int(r.get("fixtures", {}).get("played", {}).get("total", 0)) or played
    yellow_avg     = round(_sum_cards(r.get("cards", {}).get("yellow", {})) / played_total, 2)
    red_avg        = round(_sum_cards(r.get("cards", {}).get("red",    {})) / played_total, 2)

    log.info(f"  goles: {goals_scored} marcados, {goals_conceded} concedidos")

    # Corners, offsides, tiros, faltas: de últimos 5 partidos FT en ese contexto
    corners, offsides, shots, fouls = _get_match_averages(team_id, league_id, season, is_home)

    stats = {
        "corners":        corners,
        "yellow_cards":   yellow_avg,
        "red_cards":      red_avg,
        "offsides":       offsides,
        "goals_scored":   goals_scored,
        "goals_conceded": goals_conceded,
        "shots_on_goal":  shots,
        "fouls":          fouls,
    }
    log.info(f"  STATS FINALES team={team_id} ctx={ctx}: {stats}")
    return stats


def _get_match_averages(team_id, league_id, season, is_home: bool):
    """
    Últimos 5 partidos FT del equipo EN ESE CONTEXTO (local o visita).
    Promedia corners, offsides, tiros y faltas.
    """
    params = {
        "team": team_id, "league": league_id,
        "season": season, "last": 5, "status": "FT",
    }
    if is_home:
        params["venue"] = "home"
    else:
        params["venue"] = "away"

    fix_data = _get("fixtures", params)
    fixtures  = fix_data.get("response", [])
    log.info(f"  partidos FT {'local' if is_home else 'visita'}: {len(fixtures)}")

    if not fixtures:
        # Si no hay suficientes partidos en ese contexto, usar todos
        params.pop("venue")
        fix_data = _get("fixtures", params)
        fixtures  = fix_data.get("response", [])

    if not fixtures:
        return (5.0, 2.0, 4.0, 12.0)

    c_list, o_list, s_list, f_list = [], [], [], []
    for fix in fixtures:
        fid    = fix["fixture"]["id"]
        s_data = _get("fixtures/statistics", {"fixture": fid, "team": team_id})
        s_resp = s_data.get("response", [])
        if not s_resp:
            continue
        sv = {s["type"]: s["value"] for s in s_resp[0].get("statistics", [])}
        log.info(f"    fixture={fid} tipos: {list(sv.keys())[:6]}...")
        c = _int(sv.get("Corner Kicks"))
        o = _int(sv.get("Offsides"))
        s = _int(sv.get("Shots on Goal"))
        f = _int(sv.get("Fouls"))
        if c + o + s + f > 0:
            c_list.append(c); o_list.append(o); s_list.append(s); f_list.append(f)

    def avg(lst, fb): return round(sum(lst)/len(lst), 1) if lst else fb
    return avg(c_list, 5.0), avg(o_list, 2.0), avg(s_list, 4.0), avg(f_list, 12.0)


# ── Stats en vivo del partido ─────────────────────────────────────────────────

def get_live_fixture_stats(fixture_id):
    """
    /fixtures/statistics para un partido en curso o terminado.
    Devuelve posesión, tiros, corners, faltas acumuladas hasta ese momento.
    Retorna lista de dos dicts (home, away) o [] si no hay datos.
    Costo: 1 llamada.
    """
    try:
        data = _get("fixtures/statistics", {"fixture": fixture_id})
    except Exception as e:
        log.warning(f"Stats en vivo no disponibles fixture={fixture_id}: {e}")
        return []

    resp = data.get("response", [])
    result = []
    for block in resp:
        sv = {s["type"]: s["value"] for s in block.get("statistics", [])}
        result.append({
            "team_id":   block["team"]["id"],
            "team_name": block["team"]["name"],
            "possession":    sv.get("Ball Possession", "—"),
            "shots_total":   _int(sv.get("Total Shots")),
            "shots_on_goal": _int(sv.get("Shots on Goal")),
            "corners":       _int(sv.get("Corner Kicks")),
            "fouls":         _int(sv.get("Fouls")),
            "yellow_cards":  _int(sv.get("Yellow Cards")),
            "red_cards":     _int(sv.get("Red Cards")),
            "offsides":      _int(sv.get("Offsides")),
            "saves":         _int(sv.get("Goalkeeper Saves")),
            "passes_acc":    sv.get("Passes accurate", "—"),
        })
    log.info(f"  Stats en vivo: {len(result)} equipos para fixture={fixture_id}")
    return result


# ── Alineaciones ──────────────────────────────────────────────────────────────

def get_fixture_lineups(fixture_id):
    try:
        data = _get("fixtures/lineups", {"fixture": fixture_id})
    except Exception as e:
        log.warning(f"Lineups no disponibles fixture={fixture_id}: {e}")
        return {}

    resp = data.get("response", [])
    if not resp:
        return {}

    result = {}
    for block in resp:
        result[block["team"]["name"]] = {
            "team_id":   block["team"]["id"],
            "team_name": block["team"]["name"],
            "formation": block.get("formation", "—"),
            "coach":     block.get("coach", {}).get("name", "—"),
            "startXI": [
                {"name": p["player"]["name"], "number": p["player"]["number"],
                 "pos":  p["player"]["pos"],  "grid":   p["player"]["grid"]}
                for p in block.get("startXI", [])
            ],
            "substitutes": [
                {"name": p["player"]["name"], "number": p["player"]["number"],
                 "pos":  p["player"]["pos"]}
                for p in block.get("substitutes", [])
            ],
        }
    log.info(f"  Lineups: {list(result.keys())}")
    return result


# ── Eventos ───────────────────────────────────────────────────────────────────

def get_fixture_events(fixture_id):
    try:
        data = _get("fixtures/events", {"fixture": fixture_id})
    except Exception as e:
        log.warning(f"Eventos no disponibles fixture={fixture_id}: {e}")
        return []

    events = []
    for e in data.get("response", []):
        events.append({
            "minute":   e.get("time", {}).get("elapsed", 0),
            "extra":    e.get("time", {}).get("extra"),
            "team":     e.get("team", {}).get("name", ""),
            "team_id":  e.get("team", {}).get("id"),
            "player":   e.get("player", {}).get("name", ""),
            "assist":   e.get("assist", {}).get("name", ""),
            "type":     e.get("type", ""),
            "detail":   e.get("detail", ""),
            "comments": e.get("comments"),
        })
    log.info(f"  Eventos: {len(events)} para fixture={fixture_id}")
    return events


# ── Tabla de posiciones ───────────────────────────────────────────────────────

def get_standings(league_id, season=None):
    s = season or FALLBACK_SEASON
    log.info(f"[standings] league={league_id} season={s}")
    try:
        data = _get("standings", {"league": league_id, "season": s})
    except Exception as e:
        log.warning(f"Standings no disponibles: {e}")
        return {}

    resp = data.get("response", [])
    if not resp:
        return {}

    league_info    = resp[0].get("league", {})
    raw_standings  = league_info.get("standings", [])

    def parse_row(row):
        return {
            "rank":          row.get("rank"),
            "team_id":       row.get("team", {}).get("id"),
            "team_name":     row.get("team", {}).get("name"),
            "points":        row.get("points"),
            "played":        row.get("all", {}).get("played"),
            "won":           row.get("all", {}).get("win"),
            "draw":          row.get("all", {}).get("draw"),
            "lost":          row.get("all", {}).get("lose"),
            "goals_for":     row.get("all", {}).get("goals", {}).get("for"),
            "goals_against": row.get("all", {}).get("goals", {}).get("against"),
            "goal_diff":     row.get("goalsDiff"),
            "form":          row.get("form", ""),
            "description":   row.get("description", ""),
        }

    return {
        "league_id":   league_id,
        "league_name": league_info.get("name"),
        "season":      league_info.get("season"),
        "standings":   [[parse_row(r) for r in g] for g in raw_standings],
    }


# ── Cuotas Bet365 ─────────────────────────────────────────────────────────────

_BET_LABELS = {
    "Goals Over/Under":   "goals",
    "Corners Over/Under": "corners",
    "Cards Over/Under":   "yellow_cards",
    "Both Teams Score":   "btts",
}

def get_fixture_odds(fixture_id):
    try:
        data = _get("odds", {"fixture": fixture_id, "bookmaker": BOOKMAKER_BET365})
    except Exception as e:
        log.warning(f"Cuotas no disponibles fixture={fixture_id}: {e}")
        return {}

    resp = data.get("response", [])
    if not resp:
        return {}

    odds_out = {}
    for bk in resp[0].get("bookmakers", []):
        for bet in bk.get("bets", []):
            mkey = _BET_LABELS.get(bet.get("name", ""))
            if not mkey:
                continue
            for outcome in bet.get("values", []):
                label = outcome.get("value", "").lower()
                try:   odd_val = float(outcome.get("odd", 0))
                except: continue
                if not odd_val: continue
                if label.startswith("over"):
                    odds_out[f"{mkey}_over_{label.replace('over','').strip()}"] = odd_val
                elif label.startswith("under"):
                    odds_out[f"{mkey}_under_{label.replace('under','').strip()}"] = odd_val
                elif label == "yes":
                    odds_out[f"{mkey}_yes"] = odd_val
                elif label == "no":
                    odds_out[f"{mkey}_no"] = odd_val

    log.info(f"  Cuotas Bet365: {len(odds_out)} mercados")
    return odds_out