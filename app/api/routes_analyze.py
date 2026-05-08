"""
routes_analyze.py
GET /analyze?fixture_id=<id>   → análisis real con value betting
GET /analyze/demo              → demo Boca vs River
GET /analyze/debug?fixture_id=<id> → respuesta cruda de la API
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.football_api       import get_fixture_teams, get_team_season_stats, get_fixture_odds, _get
from app.services.data_analyzer      import build_context
from app.services.prediction_service import generate_predictions
from config import LAST_N_MATCHES

router = APIRouter(prefix="/analyze", tags=["Analyze"])


@router.get("")
def analyze(fixture_id: int = Query(...)):
    try:
        # 1. Meta del partido
        fixture = get_fixture_teams(fixture_id)

        # 2. Stats de temporada de cada equipo
        home_stats = get_team_season_stats(fixture["home_id"], fixture["league_id"], fixture["season"])
        away_stats = get_team_season_stats(fixture["away_id"], fixture["league_id"], fixture["season"])

        # 3. Cuotas reales de Betano (1 llamada extra, devuelve {} si no hay)
        real_odds = get_fixture_odds(fixture_id)

        # 4. Combinar stats y generar predicciones con value betting
        ctx  = build_context(home_stats, away_stats)
        recs = generate_predictions(ctx["combined"], LAST_N_MATCHES, real_odds)

        return {
            "match": {
                "home": fixture["home_name"], "away": fixture["away_name"],
                "league_id": fixture["league_id"], "season": fixture["season"],
                "games_analyzed": LAST_N_MATCHES,
                "has_real_odds": bool(real_odds),
            },
            "home_stats":      ctx["home_stats"],
            "away_stats":      ctx["away_stats"],
            "recommendations": recs,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error API: {e}")


@router.get("/demo")
def analyze_demo():
    home_stats = {"corners":5.8,"yellow_cards":2.1,"red_cards":0.2,"offsides":2.3,"goals_scored":1.9,"goals_conceded":0.9,"shots_on_goal":5.4,"fouls":11.2}
    away_stats = {"corners":5.1,"yellow_cards":2.4,"red_cards":0.1,"offsides":1.8,"goals_scored":1.7,"goals_conceded":1.1,"shots_on_goal":4.8,"fouls":12.0}
    # Simulamos cuotas reales de Betano para la demo
    real_odds_demo = {
        "goals_over_2.5": 1.92, "goals_under_2.5": 1.88,
        "corners_over_9.5": 2.15, "corners_under_9.5": 1.70,
        "btts_yes": 1.78, "btts_no": 2.05,
        "yellow_cards_over_3.5": 2.30, "yellow_cards_under_3.5": 1.60,
    }
    ctx  = build_context(home_stats, away_stats)
    recs = generate_predictions(ctx["combined"], LAST_N_MATCHES, real_odds_demo)
    return {
        "match": {"home":"Boca Juniors","away":"River Plate","league_id":128,"season":2024,"games_analyzed":LAST_N_MATCHES,"has_real_odds":True},
        "home_stats": ctx["home_stats"], "away_stats": ctx["away_stats"],
        "recommendations": recs, "demo": True,
    }


@router.get("/debug")
def debug(fixture_id: int = Query(...)):
    try:
        fixture_raw = _get("fixtures", {"id": fixture_id})
        if not fixture_raw.get("response"):
            raise HTTPException(status_code=404, detail="Fixture no encontrado")
        m         = fixture_raw["response"][0]
        home_id   = m["teams"]["home"]["id"]
        away_id   = m["teams"]["away"]["id"]
        league_id = m["league"]["id"]
        season    = m["league"]["season"]
        home_ts   = _get("teams/statistics", {"team": home_id, "league": league_id, "season": season})
        away_ts   = _get("teams/statistics", {"team": away_id, "league": league_id, "season": season})
        odds_raw  = _get("odds", {"fixture": fixture_id, "bookmaker": 8})
        return {
            "fixture_meta": {"home": m["teams"]["home"]["name"], "away": m["teams"]["away"]["name"], "league_id": league_id, "season": season},
            "home_teams_statistics_raw": home_ts.get("response", {}),
            "away_teams_statistics_raw": away_ts.get("response", {}),
            "odds_raw": odds_raw.get("response", []),
        }
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=502, detail=str(e))