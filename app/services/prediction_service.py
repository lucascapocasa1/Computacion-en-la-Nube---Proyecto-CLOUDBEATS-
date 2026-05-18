"""
prediction_service.py — Motor de VALUE BETTING

EV (Expected Value) = prob_estimada × cuota_real - 1
  · Solo es calculable con cuotas REALES de la casa.
  · Con cuotas estimadas el EV siempre daría ≈ -8% (margen de la casa),
    lo cual no es informativo. En ese caso mostramos en su lugar:
      - "Confianza estadística": qué tan fuera de la media está la línea
      - "Cuota justa": la cuota que debería ofrecer la casa sin margen

Flujo:
  1. Estimamos probabilidad de cada mercado con modelos estadísticos.
  2. Si hay cuota real → calculamos EV real.
     Si no            → calculamos cuota justa y mostramos confianza.
  3. Rankeamos por EV (con cuotas reales) o por confianza (sin ellas).
  4. Devolvemos los 3 mejores mercados: safe / risky / longshot.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class Market:
    key:        str
    market:     str
    bet:        str
    our_prob:   float   # probabilidad estimada (0–1)
    fair_odds:  float   # cuota justa sin margen = 1 / our_prob
    house_odds: float   # cuota real de Bet365 (o 0.0 si no disponible)
    has_real_odds: bool
    ev:         float   # EV real si hay cuota; confianza normalizada si no
    description: str
    bookmaker:  str


# ── Punto de entrada ──────────────────────────────────────────────────────────

def generate_predictions(combined: dict, games_analyzed: int,
                         real_odds: dict | None = None) -> dict:
    real_odds = real_odds or {}
    all_markets = _evaluate_all_markets(combined, real_odds)

    # Rankear: si hay cuotas reales, por EV; si no, por probabilidad (confianza)
    has_any_real = any(m.has_real_odds for m in all_markets)
    ranked = sorted(all_markets,
                    key=lambda m: m.ev if has_any_real else m.our_prob,
                    reverse=True)

    # Priorizar mercados con EV positivo cuando existen
    if has_any_real:
        positive = [m for m in ranked if m.ev > 0 and m.has_real_odds]
        candidates = positive if len(positive) >= 3 else ranked
    else:
        candidates = ranked

    safe_m     = candidates[0] if len(candidates) > 0 else None
    risky_m    = candidates[1] if len(candidates) > 1 else None
    longshot_m = candidates[2] if len(candidates) > 2 else None

    return {
        "safe":        _format(safe_m)     if safe_m     else None,
        "risky":       _format(risky_m)    if risky_m    else None,
        "longshot":    _format(longshot_m) if longshot_m else None,
        "has_real_odds": has_any_real,
        "all_markets": [_format(m) for m in ranked],
    }


# ── Evaluación de mercados ────────────────────────────────────────────────────

def _evaluate_all_markets(c: dict, real_odds: dict) -> list[Market]:
    markets = []

    # Corners
    tc = c["total_corners"]
    line_c, dir_c = _best_line(tc)
    prob_c = _poisson_prob(tc, line_c, dir_c)
    markets.append(_make_market(
        key="corners", market="Corners", direction=dir_c, line=line_c,
        value=tc, unit="corners", prob=prob_c,
        odds_key=f"corners_{dir_c}_{line_c}", real_odds=real_odds,
        bookmaker="Corners · Total de corners",
    ))

    # Goles totales
    tg = c["total_goals_scored"]
    line_g, dir_g = _best_line(tg)
    prob_g = _poisson_prob(tg, line_g, dir_g)
    markets.append(_make_market(
        key="goals", market="Goles", direction=dir_g, line=line_g,
        value=tg, unit="goles", prob=prob_g,
        odds_key=f"goals_{dir_g}_{line_g}", real_odds=real_odds,
        bookmaker="Goles · Total de goles",
    ))

    # BTTS
    hgs, ags = c["home_goals_scored"], c["away_goals_scored"]
    p_btts_yes = (1 - math.exp(-max(hgs, 0.01))) * (1 - math.exp(-max(ags, 0.01)))
    p_btts_no  = 1 - p_btts_yes
    for side, prob_b, ok, bet_b in [
        ("yes", p_btts_yes, "btts_yes", "Ambos equipos anotan — SÍ"),
        ("no",  p_btts_no,  "btts_no",  "Ambos equipos anotan — NO"),
    ]:
        ro_b = real_odds.get(ok, 0.0)
        markets.append(Market(
            key=f"btts_{side}", market="BTTS", bet=bet_b,
            our_prob=round(prob_b, 3),
            fair_odds=round(1 / max(prob_b, 0.01), 2),
            house_odds=ro_b, has_real_odds=bool(ro_b),
            ev=round(prob_b * ro_b - 1, 4) if ro_b else round(prob_b, 4),
            description=f"Local promedia {hgs:.1f} goles, visitante {ags:.1f}. Prob.: {prob_b*100:.0f}%.",
            bookmaker="Goles · Ambos equipos marcan",
        ))

    # Tarjetas amarillas (distribución Normal, SD≈1.8)
    ty = c["total_yellow_cards"]
    line_y, dir_y = _best_line(ty)
    prob_y = _normal_prob(ty, 1.8, line_y, dir_y)
    markets.append(_make_market(
        key="yellow_cards", market="Tarjetas amarillas", direction=dir_y, line=line_y,
        value=ty, unit="amarillas", prob=prob_y,
        odds_key=f"yellow_cards_{dir_y}_{line_y}", real_odds=real_odds,
        bookmaker="Tarjetas · Amarillas totales",
    ))

    # Faltas (distribución Normal, SD≈4.5)
    tf = c["total_fouls"]
    line_f, dir_f = _best_line(tf)
    prob_f = _normal_prob(tf, 4.5, line_f, dir_f)
    markets.append(_make_market(
        key="fouls", market="Faltas", direction=dir_f, line=line_f,
        value=tf, unit="faltas", prob=prob_f,
        odds_key=f"fouls_{dir_f}_{line_f}", real_odds=real_odds,
        bookmaker="Faltas · Total de faltas",
    ))

    # Tiros al arco (distribución Normal, SD≈2.5)
    ts = c["total_shots_on_goal"]
    line_s, dir_s = _best_line(ts)
    prob_s = _normal_prob(ts, 2.5, line_s, dir_s)
    markets.append(_make_market(
        key="shots", market="Tiros al arco", direction=dir_s, line=line_s,
        value=ts, unit="tiros al arco", prob=prob_s,
        odds_key=f"shots_{dir_s}_{line_s}", real_odds=real_odds,
        bookmaker="Tiros · Total al arco",
    ))

    # Offsides (Poisson)
    to = c["total_offsides"]
    line_o, dir_o = _best_line(to)
    prob_o = _poisson_prob(to, line_o, dir_o)
    markets.append(_make_market(
        key="offsides", market="Offsides", direction=dir_o, line=line_o,
        value=to, unit="offsides", prob=prob_o,
        odds_key=f"offsides_{dir_o}_{line_o}", real_odds=real_odds,
        bookmaker="Offsides · Total de offsides",
    ))

    return markets


def _make_market(*, key, market, direction, line, value, unit,
                 prob, odds_key, real_odds, bookmaker) -> Market:
    """Construye un Market Over/Under unificando cuota real vs estimada."""
    ro = real_odds.get(odds_key, 0.0)
    verb = "Más" if direction == "over" else "Menos"
    bet  = f"{verb} de {line:.1f} {unit}"
    desc = (f"Promedio combinado {value:.1f} {unit}/partido. "
            f"Prob. estimada: {prob*100:.0f}%.")
    return Market(
        key=key, market=market, bet=bet,
        our_prob=round(prob, 3),
        fair_odds=round(1 / max(prob, 0.01), 2),
        house_odds=ro, has_real_odds=bool(ro),
        # EV real si hay cuota; probabilidad como proxy de ranking si no
        ev=round(prob * ro - 1, 4) if ro else round(prob, 4),
        description=desc, bookmaker=bookmaker,
    )


# ── Formateo de salida ────────────────────────────────────────────────────────

def _format(m: Market) -> dict:
    has_real = m.has_real_odds
    if has_real:
        ev_str   = f"{m.ev * 100:+.1f}%"
        has_value = m.ev > 0
    else:
        # Sin cuota real: EV es la probabilidad usada como ranking, no un porcentaje real
        ev_str    = "N/D"
        has_value = m.our_prob >= 0.60   # "valor" cuando prob propia > 60%

    return {
        "market":          m.market,
        "bet":             m.bet,
        "our_probability": f"{m.our_prob * 100:.0f}%",
        "fair_odds":       f"{m.fair_odds:.2f}",
        "house_odds":      f"{m.house_odds:.2f}" if m.has_real_odds else "—",
        "expected_value":  ev_str,
        "ev_raw":          m.ev if m.has_real_odds else None,
        "has_value":       has_value,
        "has_real_odds":   has_real,
        "description":     m.description,
        "betano_market":   m.bookmaker,
        # compatibilidad con frontend
        "confidence":      round(m.our_prob, 2),
        "estimated_odds":  f"{m.fair_odds:.2f}",
    }


# ── Modelos probabilísticos ───────────────────────────────────────────────────

def _poisson_prob(lam: float, line: float, direction: str) -> float:
    """P(X > line) o P(X ≤ line) con distribución de Poisson(lam)."""
    lam = max(lam, 0.01)
    k   = int(math.floor(line))
    p_under = sum(
        math.exp(-lam) * lam**i / math.factorial(i)
        for i in range(k + 1)
    )
    p = (1 - p_under) if direction == "over" else p_under
    return max(0.01, min(0.99, p))


def _normal_prob(mean: float, std: float, line: float, direction: str) -> float:
    """P(X > line) o P(X ≤ line) con distribución Normal(mean, std)."""
    std  = max(std, 0.01)
    z    = (line - mean) / std
    p_le = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    p    = (1 - p_le) if direction == "over" else p_le
    return max(0.01, min(0.99, p))


def _best_line(value: float) -> tuple[float, str]:
    """
    Elige la línea .5 que maximiza el margen respecto al promedio.
    Ej: valor=8.1 → Over 7.5 (margen=0.6) mejor que Under 8.5 (margen=0.4)
    """
    floor_val    = math.floor(value)
    line_over    = (floor_val - 1) + 0.5   # Over esta línea
    line_under   = floor_val + 0.5          # Under la siguiente
    margin_over  = value - line_over
    margin_under = line_under - value
    return (line_over, "over") if margin_over >= margin_under else (line_under, "under")