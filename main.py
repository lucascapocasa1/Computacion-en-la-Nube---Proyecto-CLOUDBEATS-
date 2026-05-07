"""
main.py
Punto de entrada de la aplicación CloudBets.

Endpoints disponibles:
  GET /                          → health check
  GET /matches/today             → partidos del día
  GET /analyze?fixture_id=<id>  → análisis de un partido real
  GET /analyze/demo              → demo con Boca vs River (sin consumir API)

Para correr en desarrollo:
  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes_matches, routes_analyze

app = FastAPI(
    title="CloudBets API",
    description="Análisis estadístico de apuestas deportivas — Computación en la Nube",
    version="2.0.0",
)

# CORS abierto para desarrollo local; en producción restringir allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de routers
app.include_router(routes_matches.router)
app.include_router(routes_analyze.router)


@app.get("/", tags=["Health"])
def root():
    """Health check — confirma que la API está activa."""
    return {"status": "ok", "message": "CloudBets API corriendo 🚀"}
