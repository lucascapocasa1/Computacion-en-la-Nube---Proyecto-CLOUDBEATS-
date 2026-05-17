"""
prediction_service.py
Motor de VALUE BETTING puro.

Concepto:
  - "Value" = cuando nuestra probabilidad estimada > probabilidad implícita de la casa.
  - EV (Expected Value) = (prob_estimada × cuota_real) - 1
    · EV > 0 → apuesta con valor (ganarías a largo plazo)
    · EV < 0 → la casa tiene ventaja en esa apuesta

Flujo:
  1. Para cada mercado disponible, estimamos la probabilidad con los stats.
  2. Comparamos con la cuota real de la casa (si la tenemos) o usamos cuota estimada.
  3. Calculamos EV de cada mercado.
  4. Rankeamos por EV descendente.
  5. Las 3 apuestas recomendadas son simplemente las de mayor EV (una por categoría):
       - safe     → EV más alto disponible
       - risky    → segundo mejor EV
       - longshot → tercer mejor EV
  6. SIN combinadas: cada apuesta es un mercado único y simple.
"""

from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class Market:
    key:        str
    market:     str     # nombre visible
    bet:        str     # descripción de la apuesta
    our_prob:   float   # nuestra probabilidad estimada (0-1)
    house_odds: float   # cuota decimal de la casa (real o estimada)
    ev:         float   # expected value = our_prob * house_odds - 1
    description: str
    bookmaker:  str


# ── Punto de entrada ──────────────────────────────────────────────────────────

def generate_predictions(combined: dict, games_analyzed: int, real_odds: dict = None) -> dict:
    """
    Evalúa todos los mercados y devuelve las 3 mejores apuestas por EV.

    `real_odds`: dict opcional con cuotas reales de la casa, formato:
      {
        "corners_over_X":  2.10,
        "corners_under_X": 1.75,
        "goals_over_2.5":  1.90,
        "goals_under_2.5": 1.95,
        "btts_yes":        1.85,
        "btts_no":         2.00,
        "cards_over_X":    2.20,
        ...
      }
    Si no hay cuotas reales, se usa cuota estimada con margen de casa del 8%.
    """
    all_markets = _evaluate_all_markets(combined, real_odds or {})

    # Filtrar solo apuestas con EV positivo (tienen valor real)
    positive_ev = [m for m in all_markets if m.ev > 0]

    # Si no hay EV positivo (mercado muy eficiente), tomar igualmente los mejores
    candidates = positive_ev if len(positive_ev) >= 3 else all_markets

    # Ordenar por EV descendente
    ranked = sorted(candidates, key=lambda m: m.ev, reverse=True)

    # Las 3 apuestas: mejor EV = safe, luego risky, luego longshot
    safe_m     = ranked[0] if len(ranked) > 0 else None
    risky_m    = ranked[1] if len(ranked) > 1 else None
    longshot_m = ranked[2] if len(ranked) > 2 else None

    return {
        "safe":     _format(safe_m,     "safe")     if safe_m     else None,
        "risky":    _format(risky_m,    "risky")    if risky_m    else None,
        "longshot": _format(longshot_m, "longshot") if longshot_m else None,
        "all_markets": [_format(m, _ev_level(m.ev)) for m in ranked],  # debug
    }


# ── Evaluación de todos los mercados ─────────────────────────────────────────

def _evaluate_all_markets(c: dict, real_odds: dict) -> list[Market]:
    markets = []

    # ── Corners Over/Under ────────────────────────────────────────────────────
    total_corners = c["total_corners"]
    line_c, dir_c = _best_line(total_corners)
    prob_c = _poisson_over_prob(total_corners, line_c) if dir_c == "over" else 1 - _poisson_over_prob(total_corners, line_c + 1)
    odds_c = real_odds.get(f"corners_{'over' if dir_c == 'over' else 'under'}_{line_c}", _fair_odds_with_margin(prob_c))
    markets.append(Market(
        key="corners", market="Corners",
        bet=f"{'Más' if dir_c=='over' else 'Menos'} de {line_c:.1f} corners",
        our_prob=round(prob_c, 3), house_odds=odds_c,
        ev=round(prob_c * odds_c - 1, 4),
        description=f"Promedio combinado {total_corners:.1f} corners/partido. Prob. estimada: {prob_c*100:.0f}%.",
        bookmaker="Corners · Total de corners",
    ))

    # ── Goles Over/Under ──────────────────────────────────────────────────────
    total_goals = c["total_goals_scored"]
    line_g, dir_g = _best_line(total_goals)
    prob_g = _poisson_over_prob(total_goals, line_g) if dir_g == "over" else 1 - _poisson_over_prob(total_goals, line_g + 1)
    odds_g = real_odds.get(f"goals_{'over' if dir_g=='over' else 'under'}_{line_g}", _fair_odds_with_margin(prob_g))
    markets.append(Market(
        key="goals", market="Goles",
        bet=f"{'Más' if dir_g=='over' else 'Menos'} de {line_g:.1f} goles",
        our_prob=round(prob_g, 3), house_odds=odds_g,
        ev=round(prob_g * odds_g - 1, 4),
        description=f"Promedio combinado {total_goals:.1f} goles/partido. Prob. estimada: {prob_g*100:.0f}%.",
        bookmaker="Goles · Total de goles",
    ))

    # ── BTTS (ambos equipos anotan) ───────────────────────────────────────────
    home_gs = c["home_goals_scored"]
    away_gs = c["away_goals_scored"]
    # Poisson: prob de que cada equipo anote AL MENOS 1 gol
    p_home_scores = 1 - math.exp(-home_gs)
    p_away_scores = 1 - math.exp(-away_gs)
    p_btts_yes = p_home_scores * p_away_scores
    p_btts_no  = 1 - p_btts_yes

    # Elegir el lado con más valor
    for side, prob_btts, key_btts, bet_btts in [
        ("yes", p_btts_yes, "btts_yes", "Ambos equipos anotan — SÍ"),
        ("no",  p_btts_no,  "btts_no",  "Ambos equipos anotan — NO"),
    ]:
        odds_btts = real_odds.get(key_btts, _fair_odds_with_margin(prob_btts))
        markets.append(Market(
            key=f"btts_{side}", market="BTTS",
            bet=bet_btts,
            our_prob=round(prob_btts, 3), house_odds=odds_btts,
            ev=round(prob_btts * odds_btts - 1, 4),
            description=f"Local promedia {home_gs} goles, visitante {away_gs}. Prob.: {prob_btts*100:.0f}%.",
            bookmaker="Goles · Ambos equipos marcan",
        ))

    # ── Tarjetas amarillas ────────────────────────────────────────────────────
    total_cards = c["total_yellow_cards"]
    line_y, dir_y = _best_line(total_cards)
    # Las tarjetas tienen alta varianza → desviación estándar estimada ~1.8
    prob_y = _normal_prob(total_cards, 1.8, line_y, dir_y)
    odds_y = real_odds.get(f"cards_{'over' if dir_y=='over' else 'under'}_{line_y}", _fair_odds_with_margin(prob_y))
    markets.append(Market(
        key="yellow_cards", market="Tarjetas amarillas",
        bet=f"{'Más' if dir_y=='over' else 'Menos'} de {line_y:.1f} amarillas",
        our_prob=round(prob_y, 3), house_odds=odds_y,
        ev=round(prob_y * odds_y - 1, 4),
        description=f"Promedio combinado {total_cards:.1f} amarillas/partido. Prob. estimada: {prob_y*100:.0f}%.",
        bookmaker="Tarjetas · Amarillas totales",
    ))

    # ── Faltas ────────────────────────────────────────────────────────────────
    total_fouls = c["total_fouls"]
    line_f, dir_f = _best_line(total_fouls)
    prob_f = _normal_prob(total_fouls, 4.5, line_f, dir_f)  # SD ~4.5
    odds_f = real_odds.get(f"fouls_{'over' if dir_f=='over' else 'under'}_{line_f}", _fair_odds_with_margin(prob_f))
    markets.append(Market(
        key="fouls", market="Faltas",
        bet=f"{'Más' if dir_f=='over' else 'Menos'} de {line_f:.1f} faltas",
        our_prob=round(prob_f, 3), house_odds=odds_f,
        ev=round(prob_f * odds_f - 1, 4),
        description=f"Promedio combinado {total_fouls:.1f} faltas/partido. Prob. estimada: {prob_f*100:.0f}%.",
        bookmaker="Faltas · Total de faltas",
    ))

    # ── Tiros al arco ─────────────────────────────────────────────────────────
    total_shots = c["total_shots_on_goal"]
    line_s, dir_s = _best_line(total_shots)
    prob_s = _normal_prob(total_shots, 2.5, line_s, dir_s)
    odds_s = real_odds.get(f"shots_{'over' if dir_s=='over' else 'under'}_{line_s}", _fair_odds_with_margin(prob_s))
    markets.append(Market(
        key="shots", market="Tiros al arco",
        bet=f"{'Más' if dir_s=='over' else 'Menos'} de {line_s:.1f} tiros al arco",
        our_prob=round(prob_s, 3), house_odds=odds_s,
        ev=round(prob_s * odds_s - 1, 4),
        description=f"Promedio combinado {total_shots:.1f} tiros/partido. Prob. estimada: {prob_s*100:.0f}%.",
        bookmaker="Tiros · Total al arco",
    ))

    # ── Offsides ─────────────────────────────────────────────────────────────
    total_off = c["total_offsides"]
    line_o, dir_o = _best_line(total_off)
    prob_o = _poisson_over_prob(total_off, line_o) if dir_o == "over" else 1 - _poisson_over_prob(total_off, line_o + 1)
    odds_o = real_odds.get(f"offsides_{'over' if dir_o=='over' else 'under'}_{line_o}", _fair_odds_with_margin(prob_o))
    markets.append(Market(
        key="offsides", market="Offsides",
        bet=f"{'Más' if dir_o=='over' else 'Menos'} de {line_o:.1f} offsides",
        our_prob=round(prob_o, 3), house_odds=odds_o,
        ev=round(prob_o * odds_o - 1, 4),
        description=f"Promedio combinado {total_off:.1f} offsides/partido. Prob. estimada: {prob_o*100:.0f}%.",
        bookmaker="Offsides · Total de offsides",
    ))

    return markets


# ── Formateo de salida ────────────────────────────────────────────────────────

def _format(m: Market, level: str) -> dict:
    ev_pct = f"{m.ev * 100:+.1f}%"
    has_real_odds = True  # siempre tenemos cuota, real o estimada
    return {
        "market":         m.market,
        "bet":            m.bet,
        "our_probability": f"{m.our_prob * 100:.0f}%",
        "house_odds":     f"{m.house_odds:.2f}",
        "expected_value": ev_pct,
        "ev_raw":         m.ev,
        "has_value":      m.ev > 0,
        "description":    m.description,
        "betano_market":  m.bookmaker,
        # campos legacy para compatibilidad con el frontend actual
        "confidence":     round(m.our_prob, 2),
        "estimated_odds": f"{m.house_odds:.2f}",
    }


def _ev_level(ev: float) -> str:
    if ev >= 0.08:  return "safe"
    if ev >= 0.03:  return "risky"
    return "longshot"


# ── Modelos probabilísticos ───────────────────────────────────────────────────

def _poisson_over_prob(lam: float, line: float) -> float:
    """
    P(X > line) para distribución de Poisson con media `lam`.
    Se usa para eventos de conteo (corners, goles, offsides).
    """
    k = int(math.floor(line))
    # P(X <= k) = suma de P(X=i) para i=0..k
    p_under = sum(
        (math.exp(-lam) * lam**i) / math.factorial(i)
        for i in range(k + 1)
    )
    return max(0.01, min(0.99, 1 - p_under))


def _normal_prob(mean: float, std: float, line: float, direction: str) -> float:
    """
    P(X > line) o P(X < line+1) bajo distribución Normal(mean, std).
    Se usa para tarjetas y faltas que tienen distribución más simétrica.
    """
    z = (line - mean) / std
    # Aproximación de la CDF normal estándar
    p_under = _normal_cdf(z)
    if direction == "over":
        return max(0.01, min(0.99, 1 - p_under))
    else:
        return max(0.01, min(0.99, p_under))


def _normal_cdf(z: float) -> float:
    """CDF de la distribución normal estándar (aproximación de Abramowitz & Stegun)."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _best_line(value: float) -> tuple[float, str]:
    """
    Elige la línea .5 que maximiza el margen con dirección coherente.
    Ej: valor=8.1 → Over 7.5 (margen 0.6)
    """
    floor_val   = math.floor(value)
    line_over   = (floor_val - 1) + 0.5
    line_under  = floor_val + 0.5
    margin_over = value - line_over
    margin_under= line_under - value
    return (line_over, "over") if margin_over >= margin_under else (line_under, "under")


def _fair_odds_with_margin(prob: float, margin: float = 0.08) -> float:
    """
    Cuota justa = 1/prob. Con margen de casa del 8% (margen típico de casas europeas).
    Retorna la cuota que ofrecería la casa (siempre menor que la justa).
    """
    if prob <= 0:
        return 99.0
    fair = 1 / prob
    # La casa descuenta el margen de la cuota
    return round(fair * (1 - margin), 2)