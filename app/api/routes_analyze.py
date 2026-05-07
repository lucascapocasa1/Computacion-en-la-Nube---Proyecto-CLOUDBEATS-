"""
routes_analyze.py
Endpoints de análisis:
  GET /analyze?fixture_id=<id>  → análisis real
  GET /analyze/demo             → demo sin consumir API
  GET /analyze/debug?fixture_id=<id> → muestra la respuesta cruda de la API
                                       (útil para diagnosticar si faltan datos)
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.football_api       import get_fixture_teams, get_team_season_stats, _get
from app.services.data_analyzer      import build_context
from app.services.prediction_service import generate_predictions
from config import LAST_N_MATCHES

router = APIRouter(prefix="/analyze", tags=["Analyze"])


# ── Análisis real ─────────────────────────────────────────────────────────────

@router.get("")
def analyze(fixture_id: int = Query(..., description="ID del fixture")):
    """Devuelve estadísticas de temporada + 3 apuestas recomendadas."""
    try:
        fixture    = get_fixture_teams(fixture_id)
        home_stats = get_team_season_stats(fixture["home_id"], fixture["league_id"], fixture["season"])
        away_stats = get_team_season_stats(fixture["away_id"], fixture["league_id"], fixture["season"])
        ctx        = build_context(home_stats, away_stats)
        recs       = generate_predictions(ctx["combined"], LAST_N_MATCHES)

        return {
            "match": {
                "home": fixture["home_name"], "away": fixture["away_name"],
                "league_id": fixture["league_id"], "season": fixture["season"],
                "games_analyzed": LAST_N_MATCHES,
            },
            "home_stats":      ctx["home_stats"],
            "away_stats":      ctx["away_stats"],
            "recommendations": recs,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error API: {e}")


# ── Demo ──────────────────────────────────────────────────────────────────────

@router.get("/demo")
def analyze_demo():
    """Demo con Boca vs River. No consume llamadas de API."""
    home_stats = {"corners":5.8,"yellow_cards":2.1,"red_cards":0.2,"offsides":2.3,"goals_scored":1.9,"goals_conceded":0.9,"shots_on_goal":5.4,"fouls":11.2}
    away_stats = {"corners":5.1,"yellow_cards":2.4,"red_cards":0.1,"offsides":1.8,"goals_scored":1.7,"goals_conceded":1.1,"shots_on_goal":4.8,"fouls":12.0}
    ctx  = build_context(home_stats, away_stats)
    recs = generate_predictions(ctx["combined"], LAST_N_MATCHES)
    return {
        "match": {"home":"Boca Juniors","away":"River Plate","league_id":128,"season":2025,"games_analyzed":LAST_N_MATCHES},
        "home_stats": ctx["home_stats"], "away_stats": ctx["away_stats"],
        "recommendations": recs, "demo": True,
    }


# ── Debug: respuesta cruda de la API ─────────────────────────────────────────

@router.get("/debug")
def debug(fixture_id: int = Query(..., description="ID del fixture a inspeccionar")):
    """
    Devuelve la respuesta RAW de la API para diagnosticar problemas.
    Visitá /analyze/debug?fixture_id=<id> en el browser para ver qué
    devuelve realmente api-sports.io para ese partido.
    """
    try:
        # 1. Info del fixture
        fixture_raw = _get("fixtures", {"id": fixture_id})
        if not fixture_raw.get("response"):
            raise HTTPException(status_code=404, detail="Fixture no encontrado")

        m          = fixture_raw["response"][0]
        home_id    = m["teams"]["home"]["id"]
        away_id    = m["teams"]["away"]["id"]
        league_id  = m["league"]["id"]
        season     = m["league"]["season"]

        # 2. teams/statistics crudo para ambos equipos
        home_ts = _get("teams/statistics", {"team": home_id, "league": league_id, "season": season})
        away_ts = _get("teams/statistics", {"team": away_id, "league": league_id, "season": season})

        # 3. Último partido terminado (FT) de cada equipo + sus stats
        home_fixtures = _get("fixtures", {"team": home_id, "league": league_id, "season": season, "last": 1, "status": "FT"})
        away_fixtures = _get("fixtures", {"team": away_id, "league": league_id, "season": season, "last": 1, "status": "FT"})

        home_last_stats, away_last_stats = {}, {}
        if home_fixtures.get("response"):
            fid = home_fixtures["response"][0]["fixture"]["id"]
            home_last_stats = _get("fixtures/statistics", {"fixture": fid, "team": home_id})
        if away_fixtures.get("response"):
            fid = away_fixtures["response"][0]["fixture"]["id"]
            away_last_stats = _get("fixtures/statistics", {"fixture": fid, "team": away_id})

        return {
            "fixture_meta": {
                "home": m["teams"]["home"]["name"], "away": m["teams"]["away"]["name"],
                "league_id": league_id, "season": season,
            },
            "home_teams_statistics_raw": home_ts.get("response", {}),
            "away_teams_statistics_raw": away_ts.get("response", {}),
            "home_last_match_stats_raw": home_last_stats.get("response", []),
            "away_last_match_stats_raw": away_last_stats.get("response", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))