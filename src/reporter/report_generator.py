"""
Gece taraması sonuçlarından okunabilir rapor (DataFrame + özet metinler)
üretir. Streamlit arayüzü bu modülün çıktısını kullanır.
"""

from __future__ import annotations

import pandas as pd


def results_to_dataframe(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "Hisse": r["ticker"].replace(".IS", ""),
            "Sinyal": r.get("final_signal"),
            "Skor": r.get("final_score"),
            "Kapanış": r.get("close"),
            "Stop": r.get("stop"),
            "Hedef": r.get("target"),
            "R:R": r.get("risk_reward"),
            "Çelişki": "⚠️" if r.get("has_conflict") else "",
            "Rejim Notu": r.get("regime_note"),
            "Tarih": r.get("as_of_date"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        signal_order = {"AL": 0, "BEKLE": 1, "SAT": 2}
        df["_sort"] = df["Sinyal"].map(signal_order).fillna(1)
        df = df.sort_values(["_sort", "Skor"], ascending=[True, False]).drop(columns="_sort")
    return df.reset_index(drop=True)


def agent_breakdown_dataframe(result: dict) -> pd.DataFrame:
    """Tek bir hisse için agent bazlı detay tablosu (şeffaflık amaçlı)."""
    rows = []
    for sig in result.get("agent_signals", []):
        rows.append({
            "Agent": sig["agent"],
            "Sinyal": sig["signal"],
            "Değer": sig["signal_value"],
            "Güven": sig["confidence"],
            "Ağırlık": sig["weight"],
            "Açıklama": sig["reasoning"],
        })
    return pd.DataFrame(rows)


def summary_text(results: list[dict]) -> str:
    df = results_to_dataframe(results)
    if df.empty:
        return "Bu gece için sonuç üretilemedi."
    n_buy = (df["Sinyal"] == "AL").sum()
    n_sell = (df["Sinyal"] == "SAT").sum()
    n_wait = (df["Sinyal"] == "BEKLE").sum()
    n_conflict = (df["Çelişki"] == "⚠️").sum()
    date = df["Tarih"].iloc[0] if not df.empty else ""
    return (
        f"{date} taraması: {n_buy} AL, {n_sell} SAT, {n_wait} BEKLE sinyali "
        f"({n_conflict} hissede agent'lar arası görüş ayrılığı var)."
    )
