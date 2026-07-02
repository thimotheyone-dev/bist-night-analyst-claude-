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
# NOT (kalibrasyon): final_score = ağırlıklı ortalama(signal_value × confidence)
# formülünden geldiği için doğal olarak dar bir aralıkta toplanır — 5 agent'ın
# görüşleri birbirini kısmen iptal eder ve confidence çarpanı (ortalama ~0.35)
# skoru ek olarak küçültür. Sentetik veri üzerinde ölçülen gerçekçi dağılım:
# std≈0.044, p90≈0.07, gözlenen maksimum≈0.15. Eski eşik (0.35) bu aralığın
# ~8 katıydı ve pratikte hiçbir zaman aşılamıyordu — bu yüzden tüm sinyaller
# BEKLE'ye düşüyor, Stop/Hedef/R:R hep None çıkıyordu. Yeni eşikler, skor
# dağılımının üst ~%1-3'ünü (gerçek "güçlü konsensüs" günlerini) AL/SAT
# olarak işaretleyecek şekilde kalibre edildi. Gerçek BIST verisiyle
# dağılım farklılaşabilir; genetik optimizer periyodik olarak bu eşikleri
# de arama uzayına dahil edip zamanla iyileştirebilir.
SIGNAL_BUY_THRESHOLD = 0.12    # final_score bu değerin üstündeyse AL
SIGNAL_SELL_THRESHOLD = -0.12  # final_score bu değerin altındaysa SAT
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
LATEST_SIGNALS_DETAIL_FILE = PROCESSED_DATA_DIR / "latest_signals_detail.json"
WEIGHT_HISTORY_FILE = PROCESSED_DATA_DIR / "weight_history.csv"

# ── Bildirimler ───────────────────────────────────────────────────────────
# E-posta gönderimi GitHub Actions üzerindeki dawidd6/action-send-mail
# adımı tarafından yapılır; uygulama kodu SMTP kimlik bilgisi taşımaz.
# GitHub repo'unuzda şu üç Secret tanımlayın:
#   EMAIL_USERNAME     → gönderici Gmail adresi (örn. adiniz@gmail.com)
#   EMAIL_APP_PASSWORD → Gmail "Uygulama Şifresi" (Google Hesabı → Güvenlik)
#   EMAIL_TO           → alıcı adresi (örn. adiniz@gmail.com)
