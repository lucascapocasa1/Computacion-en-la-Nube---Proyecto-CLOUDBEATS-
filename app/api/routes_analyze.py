"""
routes_analyze.py

Este archivo define múltiples endpoints relacionados al análisis de partidos de fútbol.
Permite obtener estadísticas, eventos, alineaciones y generar recomendaciones de apuestas.

Endpoints disponibles:
GET /analyze?fixture_id=<id>              → análisis completo con value betting
GET /analyze/live-stats?fixture_id=<id>  → estadísticas en tiempo real del partido
GET /analyze/lineups?fixture_id=<id>     → alineaciones del partido
GET /analyze/events?fixture_id=<id>      → eventos (goles, tarjetas, etc.)
GET /analyze/standings?league_id=<id>    → tabla de posiciones de la liga
GET /analyze/demo                        → demo con datos simulados (Boca vs River)
"""

# Importación de herramientas de FastAPI
from fastapi import APIRouter, HTTPException, Query

# Importación de funciones que interactúan con la API de fútbol (probablemente externa)
from app.services.football_api import (
    get_fixture_teams,        # Obtiene información básica del partido (equipos, liga, temporada, etc.)
    get_team_season_stats,    # Obtiene estadísticas del equipo en la temporada
    get_fixture_odds,         # Obtiene cuotas reales de apuestas del partido
    get_fixture_lineups,      # Obtiene alineaciones del partido
    get_fixture_events,       # Obtiene eventos del partido (goles, tarjetas, etc.)
    get_standings,            # Obtiene tabla de posiciones de una liga
    get_live_fixture_stats,   # Obtiene estadísticas en tiempo real del partido
)

# Importación de función que construye un contexto de datos combinados
from app.services.data_analyzer import build_context

# Importación de función que genera recomendaciones de apuestas
from app.services.prediction_service import generate_predictions

# Importación de constantes de configuración
from config import LAST_N_MATCHES, FALLBACK_SEASON

# Creación del router de FastAPI
# prefix="/analyze" → todas las rutas comenzarán con /analyze
# tags=["Analyze"] → etiqueta usada en la documentación automática (Swagger)
router = APIRouter(prefix="/analyze", tags=["Analyze"])


# Endpoint principal: análisis completo del partido
@router.get("")
def analyze(fixture_id: int = Query(...)):
    """
    Analiza un partido a partir de su fixture_id.

    Parámetros:
    - fixture_id: ID del partido (obligatorio)

    Retorna:
    - Información del partido
    - Estadísticas de ambos equipos
    - Recomendaciones de apuestas
    """
    try:
        # Obtiene información del partido (equipos, liga, temporada, etc.)
        fixture = get_fixture_teams(fixture_id)

        # Obtiene estadísticas del equipo local (is_home=True)
        home_stats = get_team_season_stats(
            fixture["home_id"],
            fixture["league_id"],
            fixture["season"],
            is_home=True
        )

        # Obtiene estadísticas del equipo visitante (is_home=False)
        away_stats = get_team_season_stats(
            fixture["away_id"],
            fixture["league_id"],
            fixture["season"],
            is_home=False
        )

        # Obtiene cuotas reales del partido (puede ser None si no hay datos)
        real_odds = get_fixture_odds(fixture_id)

        # Construye un contexto combinando estadísticas de ambos equipos
        # ctx contiene: home_stats, away_stats y combined
        ctx = build_context(home_stats, away_stats)

        # Genera recomendaciones de apuestas basadas en:
        # - estadísticas combinadas
        # - cantidad de partidos a analizar
        # - cuotas reales
        recs = generate_predictions(
            ctx["combined"],
            LAST_N_MATCHES,
            real_odds
        )

        # Retorna la respuesta final en formato JSON
        return {
            "match": {
                "home": fixture["home_name"],      # Nombre del equipo local
                "away": fixture["away_name"],      # Nombre del equipo visitante
                "league_id": fixture["league_id"], # ID de la liga
                "season": fixture["season"],       # Temporada
                "games_analyzed": LAST_N_MATCHES,  # Cantidad de partidos analizados
                "has_real_odds": bool(real_odds),  # Indica si hay cuotas reales disponibles
                "status": fixture.get("status"),   # Estado del partido (ej: NS, LIVE, FT)
                "minute": fixture.get("minute"),   # Minuto actual (si está en vivo)
            },
            "home_stats": ctx["home_stats"],       # Estadísticas del equipo local
            "away_stats": ctx["away_stats"],       # Estadísticas del equipo visitante
            "recommendations": recs,               # Recomendaciones generadas
        }

    # Manejo de error si no se encuentra el recurso (por ejemplo fixture inexistente)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Manejo de cualquier otro error (por ejemplo fallo en API externa)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error API: {e}")


# Endpoint: estadísticas en tiempo real del partido
@router.get("/live-stats")
def live_stats(fixture_id: int = Query(...)):
    """
    Devuelve estadísticas en vivo del partido:
    posesión, tiros, corners, etc.
    """
    try:
        return get_live_fixture_stats(fixture_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# Endpoint: alineaciones del partido
@router.get("/lineups")
def lineups(fixture_id: int = Query(...)):
    """
    Devuelve las alineaciones del partido.
    """
    try:
        return get_fixture_lineups(fixture_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# Endpoint: eventos del partido
@router.get("/events")
def events(fixture_id: int = Query(...)):
    """
    Devuelve eventos del partido:
    goles, tarjetas, cambios, etc.
    """
    try:
        return get_fixture_events(fixture_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# Endpoint: tabla de posiciones
@router.get("/standings")
def standings(
    league_id: int = Query(...),                         # ID de la liga (obligatorio)
    season: int = Query(default=FALLBACK_SEASON)         # Temporada (por defecto)
):
    """
    Devuelve la tabla de posiciones de una liga y temporada.
    """
    try:
        # Obtiene datos de standings
        data = get_standings(league_id, season)

        # Si no hay datos, devuelve error 404
        if not data:
            raise HTTPException(status_code=404, detail="Sin datos para esa liga/temporada")

        return data

    # Si ya es una HTTPException, la vuelve a lanzar
    except HTTPException:
        raise

    # Otros errores
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# Endpoint de demo (sin API externa)
@router.get("/demo")
def analyze_demo():
    """
    Simulación de análisis de partido con datos hardcodeados.
    Útil para pruebas o demos (Boca vs River).
    """

    # Estadísticas simuladas del equipo local
    home_stats = {
        "corners": 5.8,
        "yellow_cards": 2.1,
        "red_cards": 0.2,
        "offsides": 2.3,
        "goals_scored": 1.9,
        "goals_conceded": 0.9,
        "shots_on_goal": 5.4,
        "fouls": 11.2
    }

    # Estadísticas simuladas del equipo visitante
    away_stats = {
        "corners": 5.1,
        "yellow_cards": 2.4,
        "red_cards": 0.1,
        "offsides": 1.8,
        "goals_scored": 1.7,
        "goals_conceded": 1.1,
        "shots_on_goal": 4.8,
        "fouls": 12.0
    }

    # Cuotas simuladas
    real_odds = {
        "goals_over_2.5": 1.92,
        "goals_under_2.5": 1.88,
        "corners_over_9.5": 2.15,
        "corners_under_9.5": 1.70,
        "btts_yes": 1.78,
        "btts_no": 2.05,
        "yellow_cards_over_3.5": 2.30,
        "yellow_cards_under_3.5": 1.60
    }

    # Construye contexto con stats simuladas
    ctx = build_context(home_stats, away_stats)

    # Genera recomendaciones basadas en datos simulados
    recs = generate_predictions(ctx["combined"], LAST_N_MATCHES, real_odds)

    # Retorna respuesta simulada
    return {
        "match": {
            "home": "Boca Juniors",
            "away": "River Plate",
            "league_id": 128,
            "season": 2024,
            "games_analyzed": LAST_N_MATCHES,
            "has_real_odds": True,
            "status": "NS",   # Not Started
            "minute": None,
        },
        "home_stats": ctx["home_stats"],
        "away_stats": ctx["away_stats"],
        "recommendations": recs,
        "demo": True,  # Indica que es un endpoint de prueba
    }