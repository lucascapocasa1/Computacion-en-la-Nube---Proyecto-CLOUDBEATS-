"""
routes_matches.py
Endpoint: GET /matches/today
Devuelve los partidos del día filtrados por ligas importantes.
"""

from fastapi import APIRouter, HTTPException
from app.services.football_api import get_today_matches

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("/today")
def matches_today():
    """Retorna la lista de partidos de hoy en las ligas configuradas."""
    try:
        return get_today_matches()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
