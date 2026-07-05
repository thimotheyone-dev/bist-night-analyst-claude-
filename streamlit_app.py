"""
BIST Night Analyst — Streamlit Dashboard

Bu arayüz HİÇBİR ağır hesaplama yapmaz; sadece GitHub Actions'ın gece
ürettiği ve repo'ya commit ettiği sonuçları (data/processed/*.csv) okur ve
görselleştirir. "Manuel Tara" bölümü sadece test/geliştirme amaçlıdır ve
GitHub Actions akışının yerine geçmez.

Bu uygulama OTOMATİK AL-SAT YAPMAZ. Sadece analiz/rapor üretir; tüm işlem
kararları kullanıcıya aittir.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import settings
from config.symbols import WATCHLIST
from src.learning.feedback_loop import load_predictions_log, load_weights
from src.reporter.report_generator import agent_breakdown_dataframe, load_full_results

st.set_page_config(page_title="BIST Night Analyst", page_icon="📊", layout="wide")

st.title("📊 BIST Night Analyst")
st.caption(
    "Kısa vadeli swing trading için çoklu-agent teknik analiz raporu. "
    "Otomatik işlem yapılmaz — yalnızca AL / SAT / BEKLE önerisi sunar."
)

st.warning(
    "⚠️ Bu uygulama yatırım tavsiyesi değildir. Tüm sinyaller geçmiş veri ve "
    "teknik göstergelere dayalı otomatik analizdir; nihai karar kullanıcıya aittir.",
    icon="⚠️",
)


# ── Veri yükleme ────────────────────────────────────────────────────────
@st.cache_data(ttl=900)
def load_latest_signals() -> pd.DataFrame:
    if settings.LATEST_SIGNALS_FILE.exists():
        return pd.read_csv(settings.LATEST_SIGNALS_FILE)
    return pd.DataFrame()


@st.cache_data(ttl=900)
def load_weight_history() -> pd.DataFrame:
    if settings.WEIGHT_HISTORY_FILE.exists():
        return pd.read_csv(settings.WEIGHT_HISTORY_FILE, parse_dates=["date"])
    return pd.DataFrame()


@st.cache_data(ttl=900)
def load_predictions() -> pd.DataFrame:
    return load_predictions_log()


@st.cache_data(ttl=900)
def load_signal_details() -> dict:
    return load_full_results(settings.LATEST_SIGNALS_DETAIL_FILE)


signals_df = load_latest_signals()
weight_history_df = load_weight_history()
predictions_df = load_predictions()
current_weights = load_weights()
detail_by_ticker = load_signal_details()


# ── Üst özet ────────────────────────────────────────────────────────────
if signals_df.empty:
    st.info(
        "Henüz bir gece taraması çalıştırılmamış. GitHub Actions iş akışı "
        "(`.github/workflows/nightly_analysis.yml`) ilk çalıştığında sonuçlar "
        "burada görünecek. Manuel test için aşağıdaki bölümü kullanabilirsiniz."
    )
else:
    col1, col2, col3, col4 = st.columns(4)
    n_buy = (signals_df["Sinyal"] == "AL").sum()
    n_sell = (signals_df["Sinyal"] == "SAT").sum()
    n_wait = (signals_df["Sinyal"] == "BEKLE").sum()
    last_date = signals_df["Tarih"].iloc[0] if "Tarih" in signals_df.columns else "-"
    col1.metric("🟢 AL Sinyali", int(n_buy))
    col2.metric("🔴 SAT Sinyali", int(n_sell))
    col3.metric("🟡 BEKLE", int(n_wait))
    col4.metric("Son Tarama", last_date)

    st.subheader("Güncel Tarama Sonuçları")
    signal_filter = st.multiselect("Sinyale göre filtrele", ["AL", "SAT", "BEKLE"], default=["AL", "SAT"])
    filtered = signals_df[signals_df["Sinyal"].isin(signal_filter)] if signal_filter else signals_df
    st.dataframe(filtered, use_container_width=True, hide_index=True)

    st.subheader("Hisse Bazında Agent Detayı")
    selected_ticker = st.selectbox("Hisse seçin", sorted(signals_df["Hisse"].unique()))
    st.caption(
        f"{selected_ticker} için her agent'ın bireysel görüşü ve gerekçesi "
        "aşağıda listelenir. Bu şeffaflık, neden o sinyalin üretildiğini "
        "anlamanızı sağlar."
    )

    detail = detail_by_ticker.get(selected_ticker)
    if detail is None:
        st.warning(
            f"{selected_ticker} için detaylı agent verisi bulunamadı. Bu genellikle "
            "gece taramasının bu güncellemeden ÖNCE çalıştırılmış olmasından "
            "kaynaklanır — bir sonraki tarama sonrası burası otomatik dolacaktır.",
            icon="⚠️",
        )
    else:
        summary_cols = st.columns(4)
        summary_cols[0].metric("Nihai Sinyal", detail.get("final_signal", "-"))
        summary_cols[1].metric("Skor", f"{detail.get('final_score', 0):.3f}")
        summary_cols[2].metric("Rejim Çarpanı", f"{detail.get('regime_multiplier', 1):.2f}")
        summary_cols[3].metric("Görüş Ayrılığı", "Evet ⚠️" if detail.get("has_conflict") else "Hayır")
        if detail.get("regime_note"):
            st.caption(detail["regime_note"])

        st.dataframe(agent_breakdown_dataframe(detail), use_container_width=True, hide_index=True)

        if detail.get("final_signal") == "AL":
            st.divider()
            st.subheader("🔎 İkinci Göz Doğrulaması")
            st.caption(
                "Birincil sistem AL kararı verdikten sonra, bağımsız üç kriterle "
                "(likidite, risk/ödül, aşırı RSI vetosu) bir kez daha süzülür."
            )
            confirmed = detail.get("confirmed")
            notes = detail.get("confirmation_notes", "")
            checks = detail.get("confirmation_checks", {})

            if confirmed is True:
                st.success(f"✅ Doğrulandı — {notes}")
            elif confirmed is False:
                st.error(f"❌ Doğrulanmadı — {notes}")
            else:
                st.info("Doğrulama verisi mevcut değil.")

            if checks:
                check_labels = {"likidite": "Likidite", "risk_odul": "Risk/Ödül", "asiri_rsi": "RSI Vetosu"}
                check_cols = st.columns(len(checks))
                for col, (key, passed) in zip(check_cols, checks.items()):
                    col.metric(check_labels.get(key, key), "✅" if passed else "❌")


# ── Agent ağırlık geçmişi ───────────────────────────────────────────────
st.subheader("🧠 Agent Ağırlıklarının Zaman İçindeki Gelişimi")
st.caption(
    "Her agent'ın geçmiş tahmin başarısına göre güncellenen güven ağırlığı. "
    "Yükselen bir çizgi, o agent'ın son dönemde daha isabetli olduğu anlamına gelir."
)

if weight_history_df.empty:
    st.info("Henüz ağırlık geçmişi yok — ilk feedback döngüsünden sonra burada birikecek.")
else:
    fig = go.Figure()
    for col in weight_history_df.columns:
        if col == "date":
            continue
        fig.add_trace(go.Scatter(x=weight_history_df["date"], y=weight_history_df[col],
                                  mode="lines+markers", name=col))
    fig.update_layout(template="plotly_dark", height=400, yaxis_title="Ağırlık", xaxis_title="Tarih")
    st.plotly_chart(fig, use_container_width=True)

    st.write("**Güncel Ağırlıklar:**")
    weight_cols = st.columns(len(current_weights))
    for col, (agent, w) in zip(weight_cols, current_weights.items()):
        col.metric(agent.replace("_agent", "").upper(), f"{w:.2%}")


# ── Geçmiş tahmin doğruluğu ─────────────────────────────────────────────
st.subheader("📈 Geçmiş Tahmin Performansı")

if predictions_df.empty:
    st.info("Henüz değerlendirilmiş tahmin yok.")
else:
    evaluated = predictions_df[predictions_df["evaluated"].astype(bool, errors="ignore") == True]  # noqa: E712
    if evaluated.empty:
        st.info(
            f"Tahminler henüz değerlendirme aşamasında "
            f"({settings.EVALUATION_HORIZON_DAYS if hasattr(settings, 'EVALUATION_HORIZON_DAYS') else 5} "
            "gün sonra sonuçlanır)."
        )
    else:
        agent_accuracy = (
            evaluated.groupby("agent")["was_correct"]
            .apply(lambda s: s.astype(bool).mean())
            .sort_values(ascending=False)
        )
        fig2 = go.Figure(go.Bar(
            x=agent_accuracy.index, y=agent_accuracy.values,
            marker_color="#22c55e", text=[f"{v:.1%}" for v in agent_accuracy.values],
            textposition="outside",
        ))
        fig2.update_layout(
            template="plotly_dark", height=350, yaxis_title="Doğruluk Oranı",
            yaxis_tickformat=".0%", xaxis_title="Agent",
        )
        st.plotly_chart(fig2, use_container_width=True)

        with st.expander("Ham tahmin geçmişini görüntüle"):
            st.dataframe(evaluated.sort_values("as_of_date", ascending=False), use_container_width=True)


# ── Manuel test taraması (opsiyonel, geliştirme amaçlı) ────────────────
with st.expander("🔧 Manuel Tarama Çalıştır (test amaçlı, gece otomasyonunun yerine geçmez)"):
    st.caption(
        "Bu buton, GitHub Actions akışını beklemeden tek seferlik bir tarama "
        "çalıştırır. Sonuçlar dosyaya kaydedilmez, sadece burada gösterilir."
    )
    selected_subset = st.multiselect("Test edilecek hisseler", WATCHLIST, default=WATCHLIST[:5])

    if st.button("Şimdi Tara", type="primary"):
        with st.spinner("Veri çekiliyor ve analiz ediliyor..."):
            from config.symbols import get_benchmark_ticker, to_yfinance_ticker
            from src.agents.supervisor import analyze_watchlist
            from src.data_collector.collector import download_batch
            from src.data_collector.preprocessor import clean_watchlist_data
            from src.indicators.feature_engineer import build_features, build_features_for_watchlist

            tickers = [to_yfinance_ticker(s) for s in selected_subset]
            benchmark_ticker = get_benchmark_ticker()
            raw = clean_watchlist_data(download_batch(tickers + [benchmark_ticker]))

            if not raw:
                st.error("Veri çekilemedi. Streamlit Cloud'da ağ/erişim sorunu olabilir.")
            else:
                features = build_features_for_watchlist(raw, benchmark_ticker)
                benchmark_features = (
                    build_features(raw[benchmark_ticker]) if benchmark_ticker in raw else None
                )
                as_of = min(df.index.max() for df in features.values())
                results = analyze_watchlist(features, as_of, current_weights, {}, benchmark_features)

                from src.reporter.report_generator import results_to_dataframe
                st.dataframe(results_to_dataframe(results), use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Mimari notu: tüm sinyaller, üretildikleri tarihe kadar olan veriyle "
    "hesaplanır (look-ahead bias korumalı). Detaylar için README.md."
)
