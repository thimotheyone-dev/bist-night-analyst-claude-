"""
Supervisor / orchestrator.

Not: Orijinal tasarımda LangGraph önerilmişti, ancak deterministik ve
döngüsüz (agent'lar birbirine bağımlı değil, hepsi paralel çalışıp tek bir
birleştirme adımından geçiyor) bir akış için LangGraph gereksiz bir
bağımlılık + Streamlit Cloud'da ek kurulum riski getiriyor. Bu yüzden basit,
saf Python orchestration tercih edildi — önceki projelerdeki "minimum
bağımlılık" felsefesiyle tutarlı. İleride agent'lar arası gerçek
diyalog/iterasyon gerekirse LangGraph bu modülün yerine kolayca geçebilir.
"""

from __future__ import annotations

import pandas as pd

from config import settings
from src.agents.base_agent import AgentSignal, BaseAgent
from src.agents.confirmation_agent import ConfirmationAgent
from src.agents.macd_agent import MACDAgent
from src.agents.pattern_agent import PatternAgent
from src.agents.rsi_agent import RSIAgent
from src.agents.trend_agent import TrendAgent
from src.agents.volume_agent import VolumeAgent

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "trend_agent": TrendAgent,
    "rsi_agent": RSIAgent,
    "macd_agent": MACDAgent,
    "volume_agent": VolumeAgent,
    "pattern_agent": PatternAgent,
}


def build_agents(params: dict | None = None) -> dict[str, BaseAgent]:
    return {name: cls(params=params) for name, cls in AGENT_REGISTRY.items()}


def compute_regime_multiplier(benchmark_features: pd.DataFrame | None, as_of_date) -> tuple[float, str]:
    """BIST100 rejim filtresi: piyasa genel trendi düşüşteyse, AL sinyallerini
    bastırır (çarpan < 1.0); yükselişteyse normal/güçlendirilmiş bırakır."""
    if benchmark_features is None or benchmark_features.empty:
        return 1.0, "Benchmark verisi yok, rejim filtresi uygulanmadı."

    as_of_date = pd.Timestamp(as_of_date)
    safe = benchmark_features.loc[:as_of_date]
    if safe.empty:
        return 1.0, "Benchmark verisi yetersiz."

    last = safe.iloc[-1]
    trend_up = bool(last.get("trend_up", True))
    adx_val = last.get("adx", float("nan"))
    strong = pd.notna(adx_val) and adx_val >= 20

    if trend_up and strong:
        return 1.15, "XU100 güçlü yükseliş trendinde — sinyaller güçlendirildi."
    if trend_up:
        return 1.0, "XU100 yükseliş trendinde."
    if not trend_up and strong:
        return 0.6, "XU100 güçlü düşüş trendinde — AL sinyalleri bastırıldı."
    return 0.85, "XU100 yatay/zayıf trendde."


def _signal_from_score(score: float) -> str:
    if score >= settings.SIGNAL_BUY_THRESHOLD:
        return "AL"
    if score <= settings.SIGNAL_SELL_THRESHOLD:
        return "SAT"
    return "BEKLE"


def _compute_stop_target(last_row: pd.Series, signal: str) -> dict:
    close = last_row.get("Close", float("nan"))
    atr_val = last_row.get("atr", float("nan"))
    if pd.isna(close) or pd.isna(atr_val) or signal == "BEKLE":
        return {"stop": None, "target": None, "risk_reward": None}

    if signal == "AL":
        stop = close - 1.5 * atr_val
        target = close + 3.0 * atr_val
    else:  # SAT -> kısa pozisyon perspektifiyle referans seviye (otomatik işlem yapılmaz)
        stop = close + 1.5 * atr_val
        target = close - 3.0 * atr_val

    risk = abs(close - stop)
    reward = abs(target - close)
    rr = round(reward / risk, 2) if risk > 0 else None

    return {"stop": round(stop, 2), "target": round(target, 2), "risk_reward": rr}


def analyze_ticker(
    ticker: str,
    features: pd.DataFrame,
    as_of_date,
    weights: dict[str, float],
    agents: dict[str, BaseAgent],
    benchmark_features: pd.DataFrame | None = None,
) -> dict:
    """Tek bir hisse için tüm agent'ları çalıştırır, ağırlıklı skor üretir."""
    agent_outputs: list[AgentSignal] = []
    for name, agent in agents.items():
        result = agent.analyze(ticker, features, as_of_date)
        result.weight = weights.get(name, 1.0 / len(agents))
        agent_outputs.append(result)

    weighted_sum = sum(a.signal_value * a.confidence * a.weight for a in agent_outputs)
    total_weight = sum(a.weight for a in agent_outputs) or 1.0
    raw_score = weighted_sum / total_weight

    regime_mult, regime_note = compute_regime_multiplier(benchmark_features, as_of_date)
    final_score = max(-1.0, min(1.0, raw_score * regime_mult))

    final_signal = _signal_from_score(final_score)

    as_of_ts = pd.Timestamp(as_of_date)
    safe_features = features.loc[:as_of_ts]
    last_row = safe_features.iloc[-1] if not safe_features.empty else pd.Series(dtype=float)
    stop_target = _compute_stop_target(last_row, final_signal)

    # Çelişki tespiti: agent'lar arasında yön uyuşmazlığı var mı?
    directions = [1 if a.signal_value > 0.1 else (-1 if a.signal_value < -0.1 else 0) for a in agent_outputs]
    has_conflict = len(set(d for d in directions if d != 0)) > 1

    return {
        "ticker": ticker,
        "as_of_date": str(as_of_ts.date()),
        "final_signal": final_signal,
        "final_score": round(final_score, 4),
        "has_conflict": has_conflict,
        "regime_multiplier": regime_mult,
        "regime_note": regime_note,
        "close": round(float(last_row.get("Close", float("nan"))), 2) if not last_row.empty else None,
        **stop_target,
        "agent_signals": [a.to_dict() for a in agent_outputs],
    }


def analyze_watchlist(
    features_by_ticker: dict[str, pd.DataFrame],
    as_of_date,
    weights: dict[str, float],
    params: dict | None = None,
    benchmark_features: pd.DataFrame | None = None,
) -> list[dict]:
    agents = build_agents(params)
    results = []
    for ticker, features in features_by_ticker.items():
        try:
            result = analyze_ticker(ticker, features, as_of_date, weights, agents, benchmark_features)
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            results.append({
                "ticker": ticker, "as_of_date": str(pd.Timestamp(as_of_date).date()),
                "final_signal": "BEKLE", "final_score": 0.0, "error": str(exc),
            })
    return results


def apply_confirmation_gate(
    results: list[dict],
    features_by_ticker: dict[str, pd.DataFrame],
    as_of_date,
    params: dict | None = None,
) -> list[dict]:
    """Sadece final_signal == 'AL' olan sonuçlara ikinci göz doğrulamasını
    uygular; her sonuca 'confirmed' (bool|None), 'confirmation_notes' ve
    'confirmation_checks' alanlarını ekler. AL dışındaki sinyaller
    dokunulmadan geçer (confirmed=None -> "doğrulama bu sinyale uygulanmaz").
    """
    agent = ConfirmationAgent(params)
    for r in results:
        if r.get("final_signal") != "AL":
            r["confirmed"] = None
            r["confirmation_notes"] = ""
            r["confirmation_checks"] = {}
            continue

        features = features_by_ticker.get(r["ticker"])
        if features is None:
            r["confirmed"] = None
            r["confirmation_notes"] = "Doğrulama için veri bulunamadı."
            r["confirmation_checks"] = {}
            continue

        result = agent.review(r["ticker"], features, as_of_date, r)
        r["confirmed"] = result.confirmed
        r["confirmation_notes"] = result.reasoning
        r["confirmation_checks"] = result.checks
    return results
