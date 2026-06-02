import requests
from bs4 import BeautifulSoup
import time
import config


class SmartMoneyAnalyzer:
    """
    Tracks 'Smart Money' flows by scraping insider trading data from OpenInsider.
    Focuses on the Buy/Sell ratio across recent filings.

    All thresholds are read from config so PortfolioTuner can tune them
    without touching this file.

    Returns
    -------
    get_signal(ticker) → float in [-1, +1]
        Backward-compatible single-float interface.

    get_detailed_signal(ticker) → dict
        Richer signal with raw counts for logging/tuning.
    """

    def __init__(self):
        self.base_url = "http://openinsider.com/screener"
        self.cache: dict = {}  # ticker → {'score': float, 'buys': int, 'sells': int, 'last_fetch': ts}

    # ------------------------------------------------------------------ #
    #  Cache helpers                                                       #
    # ------------------------------------------------------------------ #

    def _cache_duration_secs(self) -> float:
        hours = getattr(config, "SM_CACHE_DURATION_HOURS", 4)
        return hours * 3600

    def _get_from_cache(self, ticker: str) -> dict | None:
        if ticker not in self.cache:
            return None
        entry = self.cache[ticker]
        if time.time() - entry["last_fetch"] < self._cache_duration_secs():
            return entry
        return None  # Expired

    # ------------------------------------------------------------------ #
    #  Data fetch                                                          #
    # ------------------------------------------------------------------ #

    def _fetch_activity(self, ticker: str) -> dict:
        """
        Fetches insider trading data from OpenInsider for `ticker`.
        Returns a dict with keys: score, buys, sells, filings_scanned.
        """
        max_retries   = getattr(config, "SM_HTTP_MAX_RETRIES", 3)
        retry_delay   = getattr(config, "SM_HTTP_RETRY_DELAY_S", 2)
        filings_limit = getattr(config, "SM_FILINGS_TO_SCAN", 20)

        empty_result = {"score": 0.0, "buys": 0, "sells": 0, "filings_scanned": 0}

        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}?s={ticker}"
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/91.0.4472.124 Safari/537.36"
                    )
                }
                response = requests.get(url, headers=headers, timeout=20)
                if response.status_code != 200:
                    return empty_result

                soup  = BeautifulSoup(response.content, "html.parser")
                table = soup.find("table", {"class": "tinytable"})
                if not table:
                    return empty_result

                rows = table.find_all("tr")[1:]  # Skip header
                buys = 0
                sells = 0
                scanned = 0

                for row in rows[:filings_limit]:
                    cols = row.find_all("td")
                    if len(cols) < 7:
                        continue
                    trade_type = cols[6].text.strip()
                    if "P - Purchase" in trade_type:
                        buys += 1
                    elif "S - Sale" in trade_type:
                        sells += 1
                    scanned += 1

                total = buys + sells
                score = (buys - sells) / total if total > 0 else 0.0

                result = {
                    "score":           score,
                    "buys":            buys,
                    "sells":           sells,
                    "filings_scanned": scanned,
                    "last_fetch":      time.time(),
                }
                self.cache[ticker] = result
                return result

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  [SmartMoney] Attempt {attempt + 1} failed for {ticker}: {e}. Retrying…")
                    time.sleep(retry_delay)
                else:
                    print(f"  [SmartMoney] Error for {ticker} after {max_retries} attempt(s): {e}")
                    return empty_result

        return empty_result  # Unreachable but satisfies type checker

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get_detailed_signal(self, ticker: str) -> dict:
        """
        Returns a rich dict:
            {
                'score':           float,  # −1=heavy sell, +1=heavy buy
                'buys':            int,
                'sells':           int,
                'filings_scanned': int,
            }
        """
        print(f"  [SmartMoney] Analyzing insiders for {ticker}…")

        cached = self._get_from_cache(ticker)
        if cached:
            return cached

        return self._fetch_activity(ticker)

    def get_signal(self, ticker: str) -> float:
        """
        Backward-compatible interface.
        Returns a float in [−1, +1].
        """
        detail = self.get_detailed_signal(ticker)
        score  = detail["score"]
        buys   = detail["buys"]
        sells  = detail["sells"]
        print(f"  [SmartMoney] {ticker}: score={score:+.2f} "
              f"(B:{buys} S:{sells} / {detail['filings_scanned']} filings)")
        return score


if __name__ == "__main__":
    sma = SmartMoneyAnalyzer()
    for t in ["TSLA", "NVDA", "AAPL"]:
        detail = sma.get_detailed_signal(t)
        print(f"{t} → score={detail['score']:+.2f}  "
              f"buys={detail['buys']}  sells={detail['sells']}")
