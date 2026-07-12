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
    # ── İkinci göz doğrulama katmanı (ConfirmationAgent) parametreleri ────
    "min_liquidity_try": 5_000_000.0,  # 20 günlük ort. min. TL cinsinden hacim
    "min_risk_reward": 1.5,            # min. kabul edilebilir R:R oranı
    "extreme_rsi_veto": 85,            # bu RSI seviyesi üstü AL'ı veto eder
    # ── Stop/Hedef hesaplama (trend gücüne göre değişken R:R) ─────────────
    # NOT: Eskiden stop=1.5xATR, hedef=3.0xATR sabitti -> R:R HER ZAMAN tam
    # olarak 2.0 çıkıyordu, hisseden hisseye hiç değişmiyordu. Bu da
    # ConfirmationAgent'ın "min_risk_reward" kontrolünü ayırt edici gücü
    # olmayan bir açma/kapama düğmesine indirgiyordu. Artık hedef, zaten
    # hesaplanan ADX (trend gücü) ile ölçekleniyor -- güçlü trendde hedef
    # daha uzağa konuyor, zayıf/yatay trendde daha yakın tutuluyor. Böylece
    # R:R gerçekten hisseden hisseye, günden güne değişiyor.
    "atr_stop_multiplier": 1.5,
    "atr_target_multiplier_base": 2.0,
    "atr_target_trend_bonus": 2.0,
    # ── Agent'lar arası görüş ayrılığı cezası ─────────────────────────────
    # NOT: has_conflict (agent'lar arası yön uyuşmazlığı) eskiden sadece
    # ekranda "⚠️" göstermek için hesaplanıyordu, final_score'u hiç
    # etkilemiyordu. Artık çelişki varsa skor bu çarpanla küçültülüyor.
    "conflict_penalty": 0.8,
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

# ── Backtest / işlem maliyeti ──────────────────────────────────────────
# Ortalama gidiş-dönüş işlem maliyeti (komisyon + BSMV + spread yaklaşık).
# Aracı kurumunuza göre değişir; GA ve backtest bu maliyeti düşerek NET
# getiriye göre optimize eder -- brüt (maliyetsiz) getiriye göre kalibre
# etmek gerçek karlılığı sistematik olarak abartabilir. Kendi aracı
# kurumunuzun oranına göre bu değeri güncelleyebilirsiniz.
DEFAULT_TRANSACTION_COST = 0.003  # %0.3 gidiş-dönüş (yaklaşık)

# ── Feedback / öğrenme ────────────────────────────────────────────────────
# Bir sinyalin "sonucu" kaç gün sonra değerlendirilir (1 haftalık swing
# trading ufkuna uygun).
EVALUATION_HORIZON_DAYS = 5

# Ağırlık güncelleme hızı (exponential moving update katsayısı)
WEIGHT_LEARNING_RATE = 0.05

# Genetik algoritma periyodu (kaç günde bir parametre optimizasyonu çalışır)
GENETIC_OPTIMIZATION_INTERVAL_DAYS = 7
# NOT (performans kalibrasyonu, 4. revizyon): Örneklem sayısı (ticker_sample)
# jenerasyon döngüsü BAŞLAMADAN ÖNCE bir kez seçilip o haftanın TÜM
# bireyleri/jenerasyonları için SABİT kalıyor (bkz. optimize_parameters).
# Bu yüzden küçük bir örneklem sadece gürültülü bir ölçüm değil, o haftaya
# özgü SABİT bir yanlılık demek -- popülasyon/jenerasyonu kısıp örneklemi
# küçük tutmak, GA'nın o yanlılığı daha hassas ezberlemesine (overfitting)
# yol açabilir. Bu yüzden örneklem BÜYÜK tutulup (50), popülasyon/
# jenerasyon TAM değerine (20/14) geri döndürüldü -- 90 dakikalık zaman
# aşımı keyfi bir güvenlik sınırıydı, gerçek bir kaynak kısıtı değildi;
# bu iş haftada bir kez çalıştığı için limit 150 dakikaya çıkarıldı
# (bkz. .github/workflows/nightly_analysis.yml). Tahmini gerçek süre
# ~97 dakika (~1.54x güvenlik payı, aylık CI bütçesinin sadece ~%21'i).
GENETIC_POPULATION_SIZE = 20
GENETIC_GENERATIONS = 14
GENETIC_WALKFORWARD_WINDOWS = 3
# GA, parametreleri TÜM watchlist yerine rastgele seçilmiş bu kadar
# hisse üzerinde değerlendirir (performans amaçlı) — bulunan parametreler
# yine de gece taramasında TÜM hisselere uygulanır, sadece GA'nın kendi
# iç değerlendirme maliyeti azalır. Her haftalık çalıştırmada farklı bir
# alt küme seçilir, böylece uzun vadede tüm watchlist örneklenmiş olur.
# 100 hisselik BIST100 evreninin yarısını her hafta örnekler.
GENETIC_TICKER_SAMPLE_SIZE = 50

# ── Dosya yolları ─────────────────────────────────────────────────────────
WEIGHTS_FILE = MODELS_DIR / "agent_weights.json"
PARAMS_FILE = MODELS_DIR / "agent_params.json"
PARAMS_HISTORY_FILE = PROCESSED_DATA_DIR / "params_history.csv"
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
