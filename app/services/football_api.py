"""
football_api.py
Comunicación con api-sports.io.

NOTA IMPORTANTE sobre el plan gratuito:
  El plan free solo tiene estadísticas completas hasta la temporada 2024.
  Si la temporada actual (ej: 2025) no devuelve datos (played=0),
  el código hace fallback automático a la última temporada disponible (2024).
"""

import requests
import logging
from datetime import datetime
from config import API_KEY, BASE_URL, IMPORTANT_LEAGUES

HEADERS  = {"x-apisports-key": API_KEY}
FALLBACK_SEASON = 2024   # última temporada con datos completos en el plan free

log = logging.getLogger("cloudbets")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict) -> dict:
    resp = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _fmt_time(utc_iso: str) -> str:
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    return dt.strftime("%H:%M")

def _int(value) -> int:
    try:    return int(value) if value is not None else 0
    except: return 0

def _float(value) -> float:
    try:    return float(value) if value is not None else 0.0
    except: return 0.0

def _empty_stats() -> dict:
    return {k: 0.0 for k in ("corners","yellow_cards","red_cards","offsides","goals_scored","goals_conceded","shots_on_goal","fouls")}

def _sum_cards(card_dict: dict) -> int:
    """Suma tarjetas de todas las franjas { '0-15': {'total': N}, ... }"""
    total = 0
    for pd in card_dict.values():
        if isinstance(pd, dict):
            total += _int(pd.get("total", 0))
    return total


# ── Partidos del día ──────────────────────────────────────────────────────────

def get_today_matches() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    data  = _get("fixtures", {"date": today})
    matches = []
    for m in data.get("response", []):
        if m["league"]["id"] not in IMPORTANT_LEAGUES:
            continue
        matches.append({
            "id":        m["fixture"]["id"],
            "home":      m["teams"]["home"]["name"],
            "away":      m["teams"]["away"]["name"],
            "time":      _fmt_time(m["fixture"]["date"]),
            "league":    m["league"]["name"],
            "league_id": m["league"]["id"],
            "season":    m["league"]["season"],
        })
    log.info(f"Partidos de hoy: {len(matches)}")
    return matches


# ── Equipos de un fixture ─────────────────────────────────────────────────────

def get_fixture_teams(fixture_id: int) -> dict:
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
    }


# ── Stats de temporada con fallback automático ────────────────────────────────

def get_team_season_stats(team_id: int, league_id: int, season: int) -> dict:
    """
    Intenta obtener stats de `season`. Si la API devuelve 0 partidos
    (plan free sin datos de esa temporada), reintenta con FALLBACK_SEASON (2024).
    """
    stats = _fetch_stats(team_id, league_id, season)

    # Si no hay datos, probar con la temporada de fallback
    if stats is None and season != FALLBACK_SEASON:
        log.warning(f"  Sin datos para season={season}, reintentando con season={FALLBACK_SEASON}")
        stats = _fetch_stats(team_id, league_id, FALLBACK_SEASON)

    if stats is None:
        log.warning(f"  Sin datos en ninguna temporada para team={team_id}, devolviendo zeros")
        return _empty_stats()

    return stats


def _fetch_stats(team_id: int, league_id: int, season: int) -> dict | None:
    """
    Llama a /teams/statistics para obtener goles y tarjetas,
    y a /fixtures (últimos 5 FT) para corners, offsides, tiros y faltas.
    Devuelve None si la API no tiene datos de esa temporada (played=0).
    """
    log.info(f"[teams/statistics] team={team_id} league={league_id} season={season}")
    data = _get("teams/statistics", {"team": team_id, "league": league_id, "season": season})
    r    = data.get("response", {})

    if not r:
        return None

    played = _int(r.get("fixtures", {}).get("played", {}).get("total", 0))
    log.info(f"  partidos jugados: {played}")
    if played == 0:
        return None

    # Goles: ya vienen como promedio por partido (string "1.5")
    goals_scored   = _float(r.get("goals", {}).get("for",     {}).get("average", {}).get("total"))
    goals_conceded = _float(r.get("goals", {}).get("against", {}).get("average", {}).get("total"))

    # Tarjetas: totales en temporada → dividir por partidos jugados
    yellow_avg = round(_sum_cards(r.get("cards", {}).get("yellow", {})) / played, 2)
    red_avg    = round(_sum_cards(r.get("cards", {}).get("red",    {})) / played, 2)

    log.info(f"  goles/partido: {goals_scored} marcados, {goals_conceded} concedidos")
    log.info(f"  tarjetas/partido: {yellow_avg} amarillas, {red_avg} rojas")

    # Corners, offsides, tiros y faltas: de los últimos 5 partidos FT
    corners, offsides, shots, fouls = _get_match_averages(team_id, league_id, season)

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
    log.info(f"  STATS FINALES: {stats}")
    return stats


def _get_match_averages(team_id: int, league_id: int, season: int) -> tuple:
    """
    Promedia corners, offsides, tiros al arco y faltas
    de los últimos 5 partidos terminados (status=FT) del equipo.
    """
    log.info(f"  [fixtures FT] buscando últimos 5 partidos FT team={team_id} season={season}")
    fix_data = _get("fixtures", {
        "team": team_id, "league": league_id,
        "season": season, "last": 5, "status": "FT"
    })
    fixtures = fix_data.get("response", [])
    log.info(f"  → {len(fixtures)} partidos FT encontrados")

    if not fixtures:
        return (5.0, 2.0, 4.0, 12.0)  # fallback razonable

    corners_list, offsides_list, shots_list, fouls_list = [], [], [], []

    for fix in fixtures:
        fid = fix["fixture"]["id"]
        s_data = _get("fixtures/statistics", {"fixture": fid, "team": team_id})
        s_resp = s_data.get("response", [])
        if not s_resp:
            continue

        sv = {s["type"]: s["value"] for s in s_resp[0].get("statistics", [])}
        log.info(f"    fixture={fid} tipos: {list(sv.keys())}")

        c = _int(sv.get("Corner Kicks"))
        o = _int(sv.get("Offsides"))
        s = _int(sv.get("Shots on Goal"))
        f = _int(sv.get("Fouls"))
        log.info(f"    corners={c} offsides={o} shots={s} fouls={f}")

        if c + o + s + f > 0:
            corners_list.append(c)
            offsides_list.append(o)
            shots_list.append(s)
            fouls_list.append(f)

    def avg(lst, fallback):
        return round(sum(lst) / len(lst), 1) if lst else fallback

    return (
        avg(corners_list, 5.0),
        avg(offsides_list, 2.0),
        avg(shots_list, 4.0),
        avg(fouls_list, 12.0),
    )