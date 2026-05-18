"""
routes_matches.py
Endpoint: GET /matches/today
Devuelve los partidos del día filtrados por ligas importantes.
"""

# Importa las herramientas necesarias de FastAPI:
# - APIRouter: para definir rutas/endpoints
# - HTTPException: para manejar errores HTTP
from fastapi import APIRouter, HTTPException

# Importa la función que obtiene los partidos del día desde el servicio/API
from app.services.football_api import get_today_matches

# Crea un router con:
# - prefijo "/matches" → todas las rutas empiezan con esto
# - tag "Matches" → se usa para documentar en Swagger
router = APIRouter(prefix="/matches", tags=["Matches"])


# Define un endpoint GET en "/today"
# Ruta final: GET /matches/today
@router.get("/today")
def matches_today():
    """Retorna la lista de partidos de hoy en las ligas configuradas."""
    
    try:
        # Llama a la función que obtiene los partidos del día
        # y devuelve directamente el resultado
        return get_today_matches()

    except Exception as e:
        # Si ocurre cualquier error (ej: fallo en la API externa),
        # lanza un error HTTP 502 (Bad Gateway)
        # con el detalle del error original
        raise HTTPException(status_code=502, detail=str(e))