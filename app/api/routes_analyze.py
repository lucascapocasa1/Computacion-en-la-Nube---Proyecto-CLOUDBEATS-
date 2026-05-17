"""
routes_analyze.py
GET /analyze?fixture_id=<id>              → análisis con value betting
GET /analyze/live-stats?fixture_id=<id>  → stats en tiempo real del partido
GET /analyze/lineups?fixture_id=<id>     → alineaciones
GET /analyze/events?fixture_id=<id>      → eventos (goles, tarjetas)
GET /analyze/standings?league_id=<id>    → tabla de posiciones
GET /analyze/demo                         → demo Boca vs River
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.football_api import (
    get_fixture_teams, get_team_season_stats, get_fixture_odds,
    get_fixture_lineups, get_fixture_events, get_standings,
    get_live_fixture_stats,
)
from app.services.data_analyzer      import build_context
from app.services.prediction_service import generate_predictions
from config import LAST_N_MATCHES, FALLBACK_SEASON

router = APIRouter(prefix="/analyze", tags=["Analyze"])


@router.get("")
def analyze(fixture_id: int = Query(...)):
    try:
        fixture = get_fixture_teams(fixture_id)
        # Pasar is_home=True/False para usar estadísticas contextuales
        home_stats = get_team_season_stats(fixture["home_id"], fixture["league_id"], fixture["season"], is_home=True)
        away_stats = get_team_season_stats(fixture["away_id"], fixture["league_id"], fixture["season"], is_home=False)
        real_odds  = get_fixture_odds(fixture_id)
        ctx        = build_context(home_stats, away_stats)
        recs       = generate_predictions(ctx["combined"], LAST_N_MATCHES, real_odds)
        return {
            "match": {
                "home": fixture["home_name"], "away": fixture["away_name"],
                "league_id": fixture["league_id"], "season": fixture["season"],
                "games_analyzed": LAST_N_MATCHES,
                "has_real_odds": bool(real_odds),
                "status": fixture.get("status"),
                "minute": fixture.get("minute"),
            },
            "home_stats": ctx["home_stats"],
            "away_stats": ctx["away_stats"],
            "recommendations": recs,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error API: {e}")


@router.get("/live-stats")
def live_stats(fixture_id: int = Query(...)):
    """Stats del partido en tiempo real: posesión, tiros, corners, etc."""
    try:
        return get_live_fixture_stats(fixture_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/lineups")
def lineups(fixture_id: int = Query(...)):
    try:
        return get_fixture_lineups(fixture_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/events")
def events(fixture_id: int = Query(...)):
    try:
        return get_fixture_events(fixture_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/standings")
def standings(league_id: int = Query(...), season: int = Query(default=FALLBACK_SEASON)):
    try:
        data = get_standings(league_id, season)
        if not data:
            raise HTTPException(status_code=404, detail="Sin datos para esa liga/temporada")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/demo")
def analyze_demo():
    home_stats = {"corners":5.8,"yellow_cards":2.1,"red_cards":0.2,"offsides":2.3,
                  "goals_scored":1.9,"goals_conceded":0.9,"shots_on_goal":5.4,"fouls":11.2}
    away_stats = {"corners":5.1,"yellow_cards":2.4,"red_cards":0.1,"offsides":1.8,
                  "goals_scored":1.7,"goals_conceded":1.1,"shots_on_goal":4.8,"fouls":12.0}
    real_odds  = {"goals_over_2.5":1.92,"goals_under_2.5":1.88,"corners_over_9.5":2.15,
                  "corners_under_9.5":1.70,"btts_yes":1.78,"btts_no":2.05,
                  "yellow_cards_over_3.5":2.30,"yellow_cards_under_3.5":1.60}
    ctx  = build_context(home_stats, away_stats)
    recs = generate_predictions(ctx["combined"], LAST_N_MATCHES, real_odds)
    return {
        "match": {"home":"Boca Juniors","away":"River Plate","league_id":128,
                  "season":2024,"games_analyzed":LAST_N_MATCHES,"has_real_odds":True,
                  "status":"NS","minute":None},
        "home_stats": ctx["home_stats"], "away_stats": ctx["away_stats"],
        "recommendations": recs, "demo": True,
    }