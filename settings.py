"""
Tüm proje genelinde kullanılan sabitler ve konfigürasyon değerleri.

Ortam değişkenleri ile override edilebilir (.env dosyası, bkz. .env.example).
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Dizinler ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
LOGS_DIR = PROJECT_ROOT / "logs"

for _d in (RAW_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Veri çekme ────────────────────────────────────────────────────────────
# Günlük mum verisi için ne kadar geriye gidileceği (indikatör ısınma payı
# dahil — MA200 gibi uzun pencereler için en az 250+ gün gerekir).
HISTORY_PERIOD = "2y"
HISTORY_INTERVAL = "1d"

# ── İndikatör parametreleri (varsayılanlar; genetik optimizer bunları
#    data/models/agent_params.json üzerinden override edebilir) ───────────
DEFAULT_PARAMS = {
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ma_short": 50,
    "ma_long": 200,
    "adx_period": 14,
    "adx_trend_threshold": 20,
    "atr_period": 14,
    "bb_period": 20,
    "bb_std": 2.0,
    "rel_volume_period": 20,
    "rel_volume_threshold": 1.5,
}

# ── Sinyal eşikleri ───────────────────────────────────────────────────────
SIGNAL_BUY_THRESHOLD = 0.35    # final_score bu değerin üstündeyse AL
SIGNAL_SELL_THRESHOLD = -0.35  # final_score bu değerin altındaysa SAT
# Aradaki bölge BEKLE olarak değerlendirilir.

# ── Agent başlangıç ağırlıkları (feedback loop bunları zamanla günceller) ──
DEFAULT_AGENT_WEIGHTS = {
    "trend_agent": 0.25,
    "rsi_agent": 0.20,
    "macd_agent": 0.20,
    "volume_agent": 0.15,
    "pattern_agent": 0.20,
}

# ── Feedback / öğrenme ────────────────────────────────────────────────────
# Bir sinyalin "sonucu" kaç gün sonra değerlendirilir (1 haftalık swing
# trading ufkuna uygun).
EVALUATION_HORIZON_DAYS = 5

# Ağırlık güncelleme hızı (exponential moving update katsayısı)
WEIGHT_LEARNING_RATE = 0.05

# Genetik algoritma periyodu (kaç günde bir parametre optimizasyonu çalışır)
GENETIC_OPTIMIZATION_INTERVAL_DAYS = 7
GENETIC_POPULATION_SIZE = 24
GENETIC_GENERATIONS = 15
GENETIC_WALKFORWARD_WINDOWS = 4  # walk-forward train/test pencere sayısı

# ── Dosya yolları ─────────────────────────────────────────────────────────
WEIGHTS_FILE = MODELS_DIR / "agent_weights.json"
PARAMS_FILE = MODELS_DIR / "agent_params.json"
PREDICTIONS_LOG_FILE = PROCESSED_DATA_DIR / "predictions_log.csv"
LATEST_SIGNALS_FILE = PROCESSED_DATA_DIR / "latest_signals.csv"
WEIGHT_HISTORY_FILE = PROCESSED_DATA_DIR / "weight_history.csv"

# ── Bildirimler (opsiyonel) ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
NOTIFICATIONS_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
