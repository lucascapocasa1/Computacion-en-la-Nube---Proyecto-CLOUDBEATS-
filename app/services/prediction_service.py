"""
prediction_service.py
Motor de recomendaciones de apuesta.
Genera 3 apuestas (segura, intermedia, casi imposible) a partir
de los promedios combinados de los dos equipos.

Cada apuesta devuelve:
  market          → categoría (Corners, Goles, Tarjetas, etc.)
  bet             → descripción de la apuesta
  confidence      → valor 0-1 que indica la confianza del modelo
  estimated_odds  → cuota estimada en formato decimal (ej: "1.75")
  expected_value  → valor esperado expresado como "+X%" o "-X%"
  description     → explicación en texto
  betano_market   → nombre del mercado en Betano Argentina
"""


def generate_predictions(combined: dict, games_analyzed: int) -> dict:
    """
    Toma el dict `combined` producido por data_analyzer.build_context()
    y devuelve un dict con tres claves: safe, risky, longshot.
    """
    safe      = _safe_bet(combined, games_analyzed)
    risky     = _risky_bet(combined, games_analyzed)
    longshot  = _longshot_bet(combined, games_analyzed)
    return {"safe": safe, "risky": risky, "longshot": longshot}


# ── Apuesta segura (alta confianza, cuota baja) ───────────────────────────────

def _safe_bet(c: dict, n: int) -> dict:
    """
    Mercado de Corners: Over/Under según el promedio total combinado.
    Los corners son el mercado más predecible por su regularidad.
    """
    total = c["total_corners"]
    line  = _round_half(total)          # línea redondeada al .5 más cercano

    if total >= line:
        bet = f"Más de {line - 0.5:.1f} corners"
        # Confianza alta si el promedio supera bien la línea
        confidence = min(0.92, 0.72 + (total - line) * 0.05)
        description = (
            f"Entre ambos equipos promedian {total} corners por partido "
            f"en los últimos {n} encuentros. "
            f"La línea de {line - 0.5:.1f} es cómodamente alcanzable."
        )
    else:
        bet = f"Menos de {line + 0.5:.1f} corners"
        confidence = min(0.88, 0.68 + (line - total) * 0.05)
        description = (
            f"Promedio combinado de {total} corners. "
            f"Los datos sugieren un partido con pocos saques de esquina."
        )

    odds = _confidence_to_odds(confidence)
    return {
        "market":         "Corners",
        "bet":            bet,
        "confidence":     round(confidence, 2),
        "estimated_odds": odds,
        "expected_value": _ev(confidence, float(odds)),
        "description":    description,
        "betano_market":  "Corners → Total de corners",
    }


# ── Apuesta intermedia (confianza media, cuota media) ─────────────────────────

def _risky_bet(c: dict, n: int) -> dict:
    """
    Mercado de Goles: Over/Under 2.5 o resultado de ambos anotan (BTTS).
    """
    total_goals = c["total_goals_scored"]
    btts_score  = (c["home_goals_scored"] >= 1.2 and c["away_goals_scored"] >= 1.0)

    if btts_score:
        bet = "Ambos equipos anotan — SÍ"
        confidence = min(0.72, 0.55 + c["away_goals_scored"] * 0.08)
        description = (
            f"El local promedia {c['home_goals_scored']} goles y "
            f"el visitante {c['away_goals_scored']}. "
            "Ambos han anotado con regularidad últimamente."
        )
        betano = "Goles → Ambos equipos marcan"
    elif total_goals > 2.2:
        bet = "Más de 2.5 goles"
        confidence = min(0.68, 0.50 + (total_goals - 2.2) * 0.06)
        description = (
            f"Promedio combinado de {total_goals} goles. "
            "El partido tiene pinta de ser abierto."
        )
        betano = "Goles → Total de goles"
    else:
        bet = "Menos de 2.5 goles"
        confidence = min(0.65, 0.50 + (2.2 - total_goals) * 0.06)
        description = (
            f"Promedio combinado de {total_goals} goles. "
            "Se espera un partido cerrado y de pocos goles."
        )
        betano = "Goles → Total de goles"

    odds = _confidence_to_odds(confidence)
    return {
        "market":         "Goles",
        "bet":            bet,
        "confidence":     round(confidence, 2),
        "estimated_odds": odds,
        "expected_value": _ev(confidence, float(odds)),
        "description":    description,
        "betano_market":  betano,
    }


# ── Apuesta difícil (confianza baja, cuota alta) ──────────────────────────────

def _longshot_bet(c: dict, n: int) -> dict:
    """
    Mercado de Tarjetas: se apuesta a un número exacto o a un Over
    agresivo basado en el total de amarillas promedio.
    """
    total_cards = c["total_yellow_cards"]

    if total_cards >= 5:
        line = 4.5
        bet  = f"Más de {line} tarjetas amarillas"
        confidence = min(0.45, 0.28 + (total_cards - 5) * 0.04)
        description = (
            f"Promedio combinado de {total_cards} amarillas. "
            "Es una apuesta agresiva: los árbitros y el calor del partido "
            "hacen que este número fluctúe mucho."
        )
    else:
        line = 3.5
        bet  = f"Más de {line} tarjetas amarillas"
        confidence = min(0.38, 0.22 + total_cards * 0.03)
        description = (
            f"Promedio de {total_cards} amarillas, pero el margen es ajustado. "
            "Alto riesgo: cualquier árbitro permisivo arruina la apuesta."
        )

    odds = _confidence_to_odds(confidence)
    return {
        "market":         "Tarjetas",
        "bet":            bet,
        "confidence":     round(confidence, 2),
        "estimated_odds": odds,
        "expected_value": _ev(confidence, float(odds)),
        "description":    description,
        "betano_market":  "Tarjetas → Total de tarjetas amarillas",
    }


# ── Utilidades matemáticas ────────────────────────────────────────────────────

def _round_half(value: float) -> float:
    """Redondea al entero más cercano y suma 0.5 (línea de apuesta)."""
    return round(value) + 0.5


def _confidence_to_odds(confidence: float) -> str:
    """
    Convierte confianza [0,1] a cuota decimal estimada.
    Añade un 8 % de margen de casa (vigorish típico de Betano).
    """
    if confidence <= 0:
        return "99.00"
    raw = 1 / confidence
    with_margin = raw * 1.08
    return f"{with_margin:.2f}"


def _ev(confidence: float, odds: float) -> str:
    """
    Calcula el valor esperado: EV = (conf × (odds-1)) - (1-conf)
    Expresado como porcentaje sobre la apuesta.
    """
    ev = confidence * (odds - 1) - (1 - confidence)
    return f"{ev * 100:+.1f}%"
