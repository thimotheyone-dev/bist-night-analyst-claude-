# BIST Night Analyst

Borsa İstanbul (BIST) hisseleri için **kısa vadeli swing trading** odaklı,
çoklu-agent teknik analiz raporlama sistemi.

> ⚠️ Bu proje **otomatik al-sat yapmaz**. Sadece AL / SAT / BEKLE raporu
> üretir; tüm işlem kararları kullanıcıya aittir. Yatırım tavsiyesi
> değildir.

## Ne Yapar?

Piyasa kapandıktan sonra (GitHub Actions ile, gece) çalışır:

1. Watchlist'teki 50 hisse için OHLCV verisini çeker (yfinance)
2. 5 uzman agent (Trend, RSI, MACD, Hacim, Formasyon) her hisseyi bağımsız
   değerlendirir
3. Bir supervisor bu görüşleri ağırlıklı olarak birleştirir, BIST100 rejim
   filtresi uygular, nihai AL/SAT/BEKLE kararını + ATR bazlı stop/hedef
   seviyelerini üretir
4. Geçmiş tahminlerin gerçekleşen getirisi değerlendirilir; agent'ların
   ağırlıkları buna göre güncellenir (kendi kendini geliştiren sistem)
5. Haftalık olarak genetik algoritma ile indikatör parametreleri walk-forward
   doğrulamayla optimize edilir
6. Sonuçlar repoya commit edilir; Streamlit arayüzü bu sonuçları gösterir

## Mimari

```
GitHub Actions (cron, piyasa kapanışı sonrası)
    → veri çek → indikatör hesapla → agent'lar çalışır → supervisor karar verir
    → sonuçlar data/processed/'a yazılır, repo'ya commit edilir
    → feedback loop: geçmiş tahminler değerlendirilir, ağırlıklar güncellenir
    → (haftalık) genetik optimizasyon: parametreler walk-forward ile iyileştirilir

Streamlit Cloud
    → sadece git'teki son sonuçları okur ve görselleştirir (hesaplama yapmaz)
```

## Look-Ahead Bias Koruması

Bu projenin en kritik tasarım ilkesi: **bir agent, kararını verdiği günden
sonraki hiçbir veriyi göremez.**

- `src/agents/base_agent.py::get_data_as_of()` — her agent çağrısından önce
  veriyi zorunlu olarak `as_of_date`'e kadar keser; agent kodu fiziksel
  olarak gelecek satırlara erişemez.
- `src/backtest/engine.py` — sinyal üretimi (`f(veri[0:t])`) ile sonuç
  ölçümü (`getiri[t+N]/fiyat[t] - 1`) her zaman ayrı, birbirine sızmayan
  hesaplamalardır.
- `src/learning/genetic_optimizer.py` — walk-forward validasyon: parametre
  optimizasyonu (fitness) sadece "train" penceresinde yapılır, "test"
  penceresi GA sürecine hiç gösterilmez, sadece out-of-sample raporlama
  için kullanılır.
- `src/learning/feedback_loop.py` — bir tahmin, `result_available_date`
  geçmeden değerlendirmeye katılmaz (henüz sonucu belli olmayan veri
  kullanılmaz).
- `scripts/audit_lookahead.py` — tüm tahmin logunu programatik olarak
  denetler, ihlal varsa CI'da hata verir.
- `tests/test_no_lookahead.py` — agent'a gelecekteki günler eklendiğinde
  geçmiş tarihli sinyalin DEĞİŞMEDİĞİNİ doğrulayan regresyon testi içerir.

## Kurulum

```bash
git clone <repo-url>
cd bist-night-analyst
pip install -r requirements.txt
cp .env.example .env   # opsiyonel: Telegram bildirimleri için
```

### Yerel test

```bash
python scripts/run_daily_analysis.py   # tek seferlik gece taraması
python scripts/audit_lookahead.py      # look-ahead denetimi
pytest tests/ -v                       # tüm testler
streamlit run streamlit_app.py         # arayüzü başlat
```

### GitHub Actions Kurulumu

1. Repoyu GitHub'a push edin.
2. (Opsiyonel) Settings → Secrets → Actions altına `TELEGRAM_BOT_TOKEN` ve
   `TELEGRAM_CHAT_ID` ekleyin.
3. `.github/workflows/nightly_analysis.yml` hafta içi her gün piyasa
   kapanışından sonra (18:30 TRT) otomatik çalışır, sonuçları commit eder.
4. Cumartesi günleri ayrı bir job genetik optimizasyonu çalıştırır.
5. Manuel tetiklemek için: Actions sekmesi → "BIST Night Analyst" →
   "Run workflow".

### Streamlit Cloud Deploy

1. [share.streamlit.io](https://share.streamlit.io) üzerinden repoyu bağlayın.
2. Ana dosya: `streamlit_app.py`
3. Python sürümü: 3.11 önerilir.
4. Ekstra sistem paketi gerekmez (TA-Lib kullanılmadığı için).

## Watchlist

`config/symbols.py` içinde 50 BIST hissesi tanımlıdır (SASA, THYAO, GARAN,
ASELS, TUPRS, vb.). Düzenlemek için bu dosyayı güncelleyin.

## Agent'lar

| Agent | Odak | Ana Sinyal Kaynağı |
|---|---|---|
| `trend_agent` | Genel trend yapısı | MA50/MA200, ADX |
| `rsi_agent` | Momentum / aşırı alım-satım | RSI(14) |
| `macd_agent` | Momentum dönüşü | MACD kesişimi, histogram |
| `volume_agent` | Kurumsal ilgi teyidi | Relative volume |
| `pattern_agent` | Kırılım kalitesi | BB squeeze, resistance breakout, mum kalitesi |

Her agent `-1.0` (güçlü sat) ile `+1.0` (güçlü al) arası bir `signal_value`,
bir `confidence` (0-1) ve insan-okunabilir bir `reasoning` üretir. Supervisor
bunları ağırlıklı ortalama + BIST100 rejim çarpanı ile birleştirir.

## İkinci Göz Doğrulama Katmanı (ConfirmationAgent)

5 agent + supervisor bir hisseye **AL** kararı verdikten SONRA devreye
giren, bağımsız bir doğrulama kapısı. Yeni bir oy eklemez — var olan kararı
üç ek kriterle bir kez daha süzer, hiçbir yeni indikatör hesaplamaz:

| Kriter | Ne kontrol eder | Varsayılan eşik |
|---|---|---|
| Likidite | 20 günlük ort. TL cinsinden işlem hacmi | ≥ 5.000.000 TL |
| Risk/Ödül | Supervisor'ın zaten hesapladığı ATR bazlı R:R | ≥ 1.5 |
| Aşırı RSI vetosu | Çok güçlü trend + çok yüksek RSI ("tükenme rallisi" riski) | RSI < 85 |

Bu üç eşik de haftalık genetik optimizasyonun arama uzayına dahildir
(`src/learning/genetic_optimizer.py::PARAM_SEARCH_SPACE`) — GA, backtest
sırasında AL sinyali doğrulanmazsa o günü BEKLE (işlem yapılmamış) olarak
sayar, böylece bu eşikler de zamanla gerçek performansa göre ayarlanır.

Streamlit'te bir hissenin detayına girildiğinde, AL sinyali varsa bu
katmanın "✅ Onaylandı" / "❌ Reddedildi" sonucu ve gerekçesi gösterilir.

## Neden RL/LangGraph/TA-Lib/VectorBT Kullanılmadı?

Orijinal mimaride önerilen bu araçlar bilinçli olarak sadeleştirildi:

- **TA-Lib** → Streamlit Cloud'da C derlemesi gerektirir, kırılgan. Tüm
  indikatörler sıfırdan, sadece pandas/numpy ile yazıldı.
- **Stable-Baselines3/PPO** → Streamlit Cloud'un ücretsiz katmanında RL
  eğitimi pratik değil. `src/learning/` altında iskelet olarak bırakıldı
  (`environment.py`, `ppo_trainer.py`), aktif kullanılmıyor. Öğrenme,
  skor-bazlı ağırlık güncelleme + genetik algoritma ile yapılıyor.
- **LangGraph** → Agent'lar arası gerçek bir diyalog/döngü olmadığı (hepsi
  paralel çalışıp tek seferde birleştiriliyor) için gereksiz bağımlılık.
  `src/agents/supervisor.py` saf Python ile aynı işi yapıyor.
- **VectorBT** → Lisans/kurulum karmaşıklığı; `src/backtest/` altında
  kendi vektörize backtest motoru yazıldı.

## Dizin Yapısı

```
bist-night-analyst/
├── config/              # Watchlist ve tüm konfigürasyon
├── data/
│   ├── raw/              # Ham OHLCV (parquet)
│   ├── processed/        # Sinyal sonuçları, tahmin logu, ağırlık geçmişi
│   └── models/           # agent_weights.json, agent_params.json
├── src/
│   ├── data_collector/   # yfinance veri çekme + temizleme
│   ├── indicators/       # Sıfırdan indikatör hesaplama
│   ├── agents/            # 5 uzman agent + supervisor + look-ahead koruması
│   ├── learning/          # Feedback loop + genetik optimizer (+ RL iskelet)
│   ├── backtest/          # Look-ahead güvenli backtest + metrikler
│   └── reporter/          # Rapor üretimi + Telegram bildirimi
├── scripts/               # run_daily_analysis.py, train_model.py, audit_lookahead.py
├── tests/                 # Look-ahead, indikatör ve veri testleri
├── .github/workflows/     # Gece + haftalık GitHub Actions
└── streamlit_app.py       # Dashboard (sadece okuma, hesaplama yapmaz)
```
