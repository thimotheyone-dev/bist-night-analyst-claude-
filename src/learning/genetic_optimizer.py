"""
Aşama 2 öğrenme mekanizması: walk-forward genetik algoritma ile indikatör
parametre optimizasyonu.

KRİTİK: Fitness hesaplaması SADECE train penceresinde yapılır. Test
penceresi, bulunan en iyi parametrenin gerçek (out-of-sample) performansını
ölçmek için kullanılır ve hiçbir genetik operasyon (seçim, mutasyon,
crossover) test penceresinin verisine erişemez. Bu ayrım fonksiyon
imzalarında da fiziksel olarak ayrı DataFrame'ler verilerek garanti edilir.
"""

from __future__ import annotations

import logging
import random
from copy import deepcopy

import pandas as pd

from config.settings import (
    DEFAULT_PARAMS, EVALUATION_HORIZON_DAYS, GENETIC_GENERATIONS,
    GENETIC_POPULATION_SIZE, GENETIC_TICKER_SAMPLE_SIZE,
    GENETIC_WALKFORWARD_WINDOWS, PARAMS_FILE,
)
from src.agents.confirmation_agent import ConfirmationAgent
from src.agents.supervisor import analyze_watchlist, build_agents
from src.backtest.engine import simulate_signals, walk_forward_splits
from src.backtest.metrics import summarize
from src.indicators.feature_engineer import build_features

logger = logging.getLogger(__name__)

# Optimize edilecek parametreler ve arama aralıkları (min, max, tip)
PARAM_SEARCH_SPACE = {
    "rsi_period": (10, 21, int),
    "rsi_oversold": (20, 35, int),
    "rsi_overbought": (65, 80, int),
    "macd_fast": (8, 15, int),
    "macd_slow": (20, 30, int),
    "adx_trend_threshold": (15, 30, int),
    "rel_volume_threshold": (1.2, 2.5, float),
    "bb_std": (1.5, 2.5, float),
    # ── İkinci göz doğrulama katmanı (ConfirmationAgent) ──────────────────
    "min_liquidity_try": (1_000_000, 15_000_000, float),
    "min_risk_reward": (1.0, 3.0, float),
    "extreme_rsi_veto": (75, 92, int),
}


def _random_individual() -> dict:
    individual = dict(DEFAULT_PARAMS)
    for key, (lo, hi, typ) in PARAM_SEARCH_SPACE.items():
        if typ is int:
            individual[key] = random.randint(lo, hi)
        else:
            individual[key] = round(random.uniform(lo, hi), 2)
    return individual


def _mutate(individual: dict, rate: float = 0.25) -> dict:
    child = deepcopy(individual)
    for key, (lo, hi, typ) in PARAM_SEARCH_SPACE.items():
        if random.random() < rate:
            if typ is int:
                child[key] = random.randint(lo, hi)
            else:
                child[key] = round(random.uniform(lo, hi), 2)
    return child


def _crossover(parent_a: dict, parent_b: dict) -> dict:
    child = {}
    for key in PARAM_SEARCH_SPACE:
        child[key] = parent_a[key] if random.random() < 0.5 else parent_b[key]
    return {**DEFAULT_PARAMS, **child}


def _sample_tickers_for_ga(
    raw_data: dict[str, pd.DataFrame], benchmark_ticker: str, sample_size: int,
) -> dict[str, pd.DataFrame]:
    """GA'nın her (birey × jenerasyon × pencere) kombinasyonu için yeniden
    işlediği hisse sayısını sınırlar (performans). Benchmark her zaman
    dahil edilir; geri kalanından rastgele bir alt küme seçilir. GA
    SHARED (tüm watchlist için ortak) parametreleri optimize ettiğinden,
    temsili bir alt küme yeterli bir fitness tahmini verir — bulunan
    parametreler yine de gece taramasında TAM watchlist'e uygulanır, bu
    örnekleme sadece GA'nın kendi iç değerlendirme maliyetini azaltır.
    Her çalıştırmada farklı bir alt küme seçilerek, uzun vadede (haftalık
    tekrarlarla) tüm watchlist'in davranışı örneklenmiş olur."""
    non_benchmark = [t for t in raw_data if t != benchmark_ticker]
    if len(non_benchmark) <= sample_size:
        return raw_data
    sampled = random.sample(non_benchmark, sample_size)
    result = {t: raw_data[t] for t in sampled}
    if benchmark_ticker in raw_data:
        result[benchmark_ticker] = raw_data[benchmark_ticker]
    return result


def _build_features_for_individual(
    raw_data: dict[str, pd.DataFrame], benchmark_ticker: str, params: dict,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame | None]:
    """Belirli bir birey (parametre seti) için TÜM hisselerin feature'larını
    BİR KEZ hesaplar. build_features() sonucu sadece (df, params) çiftine
    bağlıdır, pencere sınırlarına bağlı DEĞİLDİR — bu yüzden aynı bireyin
    farklı pencerelerde (train/test, N adet walk-forward penceresi) tekrar
    tekrar build_features() çağırması tamamen gereksizdi. Bu, GA'da tespit
    edilen ikinci büyük performans darboğazıydı (n_windows kat gereksiz
    tekrar). Bu fonksiyon sonucu, aynı birey için tüm pencerelerde yeniden
    kullanılır."""
    benchmark_df = raw_data.get(benchmark_ticker)
    benchmark_features = build_features(benchmark_df, None, params) if benchmark_df is not None else None
    features_by_ticker = {
        ticker: build_features(df, benchmark_df["Close"] if benchmark_df is not None else None, params)
        for ticker, df in raw_data.items() if ticker != benchmark_ticker
    }
    return features_by_ticker, benchmark_features


def _fitness_on_precomputed_features(
    features_by_ticker: dict[str, pd.DataFrame], benchmark_features: pd.DataFrame | None,
    params: dict, window_start: pd.Timestamp, window_end: pd.Timestamp,
) -> float:
    """_fitness_on_window ile aynı mantık, ancak feature'lar ÖNCEDEN
    hesaplanmış olarak alınır (bkz. _build_features_for_individual).
    Bu fonksiyona window dışına ait hiçbir veri sızdırılmaz: feature'lar
    tüm geçmişle hesaplanmış olsa da sinyal/skor sadece pencere içindeki
    tarihler için değerlendirilir.
    """
    weights = {name: 1.0 / 5 for name in build_agents().keys()}
    all_scores = []
    confirmation_agent = ConfirmationAgent(params)

    for ticker, features in features_by_ticker.items():
        window_dates = features.loc[window_start:window_end].index
        if len(window_dates) == 0:
            continue

        signals_in_window = {}
        agents = build_agents(params)
        for date in window_dates:
            try:
                from src.agents.supervisor import analyze_ticker
                result = analyze_ticker(ticker, features, date, weights, agents, benchmark_features)
                final_signal = result["final_signal"]
                # AL sinyali, ikinci göz doğrulamasından geçmezse fitness
                # hesabında BEKLE (işlem yapılmamış) olarak sayılır — bu
                # sayede GA, confirmation eşiklerinin (likidite/R:R/RSI
                # vetosu) gerçek getiriyi nasıl etkilediğini "görebilir".
                if final_signal == "AL":
                    conf_result = confirmation_agent.review(ticker, features, date, result)
                    if not conf_result.confirmed:
                        final_signal = "BEKLE"
                signals_in_window[date] = final_signal
            except Exception:  # noqa: BLE001
                continue

        if not signals_in_window:
            continue

        signal_series = pd.Series(signals_in_window)
        sim = simulate_signals(signal_series, features["Close"].reindex(signal_series.index),
                                 horizon=EVALUATION_HORIZON_DAYS)
        metrics = summarize(sim)
        if pd.notna(metrics["avg_return"]):
            all_scores.append(metrics["avg_return"])

    if not all_scores:
        return -1.0
    return sum(all_scores) / len(all_scores)


def optimize_parameters(
    raw_data: dict[str, pd.DataFrame], benchmark_ticker: str,
    population_size: int = None, generations: int = None,
    n_windows: int = None, ticker_sample_size: int = None,
) -> dict:
    """Walk-forward GA ile en iyi parametre setini bulur ve out-of-sample
    (test penceresi) performansını raporlar."""
    population_size = population_size or GENETIC_POPULATION_SIZE
    generations = generations or GENETIC_GENERATIONS
    n_windows = n_windows or GENETIC_WALKFORWARD_WINDOWS
    ticker_sample_size = ticker_sample_size or GENETIC_TICKER_SAMPLE_SIZE

    original_ticker_count = len([t for t in raw_data if t != benchmark_ticker])
    raw_data = _sample_tickers_for_ga(raw_data, benchmark_ticker, ticker_sample_size)
    sampled_count = len([t for t in raw_data if t != benchmark_ticker])
    if sampled_count < original_ticker_count:
        logger.info(
            "Performans amaçlı: %d hisseden %d tanesi GA değerlendirmesi için "
            "örneklendi (bulunan parametreler yine de TÜM watchlist'e uygulanır).",
            original_ticker_count, sampled_count,
        )

    sample_ticker = next(iter(raw_data))
    all_dates = pd.DatetimeIndex(raw_data[sample_ticker].index)
    windows = walk_forward_splits(all_dates, n_windows=n_windows)

    if not windows:
        logger.warning("Walk-forward pencereleri oluşturulamadı, varsayılan parametreler kullanılacak.")
        return dict(DEFAULT_PARAMS)

    population = [_random_individual() for _ in range(population_size)]
    best_individual, best_fitness = None, float("-inf")

    for generation in range(generations):
        scored = []
        for individual in population:
            # Bu birey için feature'lar BİR KEZ hesaplanır, tüm pencerelerde
            # yeniden kullanılır (bkz. _build_features_for_individual).
            features_by_ticker, benchmark_features = _build_features_for_individual(
                raw_data, benchmark_ticker, individual
            )
            # Fitness, SADECE train pencerelerinin ortalaması üzerinden
            # hesaplanır — test pencereleri bu aşamada hiç görülmez.
            train_scores = [
                _fitness_on_precomputed_features(
                    features_by_ticker, benchmark_features, individual, w.train_start, w.train_end
                )
                for w in windows
            ]
            fitness = sum(train_scores) / len(train_scores) if train_scores else -1.0
            scored.append((fitness, individual))

        scored.sort(key=lambda x: x[0], reverse=True)
        if scored[0][0] > best_fitness:
            best_fitness, best_individual = scored[0]

        logger.info("Jenerasyon %d/%d — en iyi train fitness: %.4f", generation + 1, generations, scored[0][0])

        # Elitizm: en iyi %25 hayatta kalır, geri kalan crossover+mutasyon ile üretilir
        survivors = [ind for _, ind in scored[: max(2, population_size // 4)]]
        new_population = list(survivors)
        while len(new_population) < population_size:
            parent_a, parent_b = random.sample(survivors, 2)
            child = _crossover(parent_a, parent_b)
            child = _mutate(child)
            new_population.append(child)
        population = new_population

    # Out-of-sample doğrulama: en iyi bireyin TEST pencerelerindeki
    # performansı — bu, GA sürecine hiçbir şekilde geri beslenmez, sadece
    # raporlama amaçlıdır.
    best_features_by_ticker, best_benchmark_features = _build_features_for_individual(
        raw_data, benchmark_ticker, best_individual
    )
    test_scores = [
        _fitness_on_precomputed_features(
            best_features_by_ticker, best_benchmark_features, best_individual, w.test_start, w.test_end
        )
        for w in windows
    ]
    oos_performance = sum(test_scores) / len(test_scores) if test_scores else float("nan")

    logger.info("En iyi parametreler: %s | train_fitness=%.4f | out-of-sample=%.4f",
                best_individual, best_fitness, oos_performance)

    result = {
        "params": best_individual,
        "train_fitness": best_fitness,
        "out_of_sample_performance": oos_performance,
        "optimized_at": str(pd.Timestamp.today().date()),
    }

    import json
    with open(PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
