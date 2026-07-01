"""
Takip edilecek BIST hisseleri.

yfinance üzerinden veri çekebilmek için tüm BIST sembollerine ".IS" suffix'i
eklenir. BIST100 endeksi rejim filtresi için ayrıca tutulur.
"""

from __future__ import annotations

# Ham BIST ticker kodları (suffix'siz)
WATCHLIST: list[str] = [
    "SASA", "OTKAR", "IEYHO", "ALTNY", "TCELL", "KCHOL", "MGROS", "SISE",
    "TOASO", "SKBNK", "AAGYO", "KRDMD", "BIMAS", "BINHO", "SAHOL", "KATMR",
    "MARMR", "ENKAI", "EREGL", "PGSUS", "ARCLK", "TTKOM", "ULKER", "TABGD",
    "ASELS", "KBORU", "YKBNK", "FROTO", "ENERY", "ISCTR", "IZFAS", "PAPIL",
    "TUPRS", "MANAS", "VESTL", "CIMSA", "TEHOL", "KRDMA", "PEKGY", "TCKRC",
    "GARAN", "VAKBN", "BIOEN", "SOKM", "KUYAS", "TAVHL", "AEFES", "THYAO",
    "CCOLA", "GRSEL",
]

# Piyasa rejim filtresi için referans endeks
BENCHMARK_SYMBOL: str = "XU100"


def to_yfinance_ticker(symbol: str) -> str:
    """BIST sembolünü yfinance formatına çevirir (örn. 'SASA' -> 'SASA.IS')."""
    symbol = symbol.strip().upper()
    if symbol == BENCHMARK_SYMBOL:
        return "XU100.IS"
    if symbol.endswith(".IS"):
        return symbol
    return f"{symbol}.IS"


def get_yfinance_watchlist() -> list[str]:
    """Tüm watchlist'i yfinance ticker formatında döndürür."""
    return [to_yfinance_ticker(s) for s in WATCHLIST]


def get_benchmark_ticker() -> str:
    return to_yfinance_ticker(BENCHMARK_SYMBOL)
