"""
data_analyzer.py
Combina las estadísticas de ambos equipos y calcula métricas
agregadas que luego usa el motor de predicciones.
"""


def combine_stats(home: dict, away: dict) -> dict:
    """
    Recibe los promedios individuales de local y visita
    y devuelve un dict con:
      - home_<stat>  → promedio del equipo local
      - away_<stat>  → promedio del equipo visita
      - total_<stat> → suma de ambos (útil para mercados Over/Under)
    """
    keys = home.keys()
    combined = {}
    for k in keys:
        combined[f"home_{k}"] = home[k]
        combined[f"away_{k}"] = away[k]
        combined[f"total_{k}"] = round(home[k] + away[k], 1)
    return combined


def build_context(home_stats: dict, away_stats: dict) -> dict:
    """
    Punto de entrada para el análisis.
    Devuelve:
      - home_stats / away_stats → promedios por equipo (para el front)
      - combined                → métricas totales (para el motor de apuestas)
    """
    return {
        "home_stats": home_stats,
        "away_stats": away_stats,
        "combined":   combine_stats(home_stats, away_stats),
    }
