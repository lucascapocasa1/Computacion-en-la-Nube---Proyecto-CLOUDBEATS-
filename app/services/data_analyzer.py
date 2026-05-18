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

    # Obtiene todas las claves (stats) del equipo local
    # Se asume que home y away tienen las mismas claves
    keys = home.keys()

    # Diccionario donde se guardarán las estadísticas combinadas
    combined = {}

    # Recorre cada estadística (ej: goles, tiros, posesión, etc.)
    for k in keys:

        # Guarda el valor del equipo local con prefijo "home_"
        combined[f"home_{k}"] = home[k]

        # Guarda el valor del equipo visitante con prefijo "away_"
        combined[f"away_{k}"] = away[k]

        # Calcula el total (suma de ambos equipos)
        # round(..., 1) redondea a 1 decimal
        combined[f"total_{k}"] = round(home[k] + away[k], 1)

    # Devuelve el diccionario con todas las métricas combinadas
    return combined


def build_context(home_stats: dict, away_stats: dict) -> dict:
    """
    Punto de entrada para el análisis.
    Devuelve:
      - home_stats / away_stats → promedios por equipo (para el front)
      - combined                → métricas totales (para el motor de apuestas)
    """

    # Retorna un diccionario estructurado con:
    return {
        # Estadísticas originales del equipo local (para mostrar en frontend)
        "home_stats": home_stats,

        # Estadísticas originales del equipo visitante
        "away_stats": away_stats,

        # Estadísticas combinadas (usadas para lógica de predicción)
        "combined": combine_stats(home_stats, away_stats),
    }