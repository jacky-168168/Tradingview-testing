from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "cache"
HISTORY_DIR = CACHE_DIR / "history"
DATA_DIR = ROOT / "docs" / "data"
UNIVERSE_CACHE = CACHE_DIR / "universe.json"
LATEST_JSON = DATA_DIR / "latest.json"

LOOKBACK_CALENDAR_DAYS = 220
MAX_CAPITAL_B = 500.0
MIN_PRICE = 10.0
MIN_TURNOVER_M = 100.0
TOP_N = 20
RISK_ON = 60
RISK_STRONG = 75
RISK_OFF = 45
SAR_CANDIDATES = 50
YAHOO_WORKERS = 8
REQUEST_TIMEOUT = 20

TWSE_COMPANY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_COMPANY_URLS = [
    "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
    "https://www.tpex.org.tw/openapi/v1/t187ap03_O",
    "https://openapi.twse.com.tw/v1/opendata/t187ap03_O",
]
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
BENCHMARK = "^TWII"
