import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
from transformers import pipeline
import numpy as np
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import config


class GoogleNewsFetcher:
    """
    Fetches news from Google News RSS and classifies each article
    into one of three tiers based on its source.

    Tier 1 — Premium financial outlets  (Bloomberg, Reuters, WSJ, CNBC, FT, …)
    Tier 2 — Reputable financial media   (Yahoo Finance, Seeking Alpha, Forbes, …)
    Tier 3 — Everything else             (community blogs, aggregators, etc.)
    """

    TIER_1_SOURCES = [
        "bloomberg", "reuters", "wsj", "wall street journal",
        "cnbc", "financial times", "barron's", "barrons", "marketwatch",
    ]

    TIER_2_SOURCES = [
        "yahoo finance", "yahoo", "seeking alpha", "motley fool", "fool.com",
        "forbes", "business insider", "investopedia", "the street", "thestreet",
        "benzinga", "zacks", "investor's business daily", "ibd",
    ]

    def fetch_news(self, symbol=None, custom_query=None):
        """
        Fetches news from Google News RSS.
        If symbol is provided, searches for "{symbol} stock".
        If custom_query is provided, uses that exactly.
        """
        if custom_query:
            query = custom_query
        elif symbol:
            query = f"{symbol} stock"
        else:
            return []

        url = (f"https://news.google.com/rss/search?q={quote(query)}"
               f"&hl=en-US&gl=US&ceid=US:en")

        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"  [GoogleNews] Failed to fetch news for '{query}' "
                      f"(Status: {response.status_code})")
                return []

            root = ET.fromstring(response.content)
            news_items = []
            max_age_h = getattr(config, "SENTIMENT_ARTICLE_MAX_AGE_H", 48)

            for item in root.findall("./channel/item"):
                title   = item.find("title").text
                link    = item.find("link").text
                pub_str = item.find("pubDate").text

                source_el = item.find("source")
                source    = source_el.text if source_el is not None else "Unknown"

                # Strip source suffix from headline ("Headline - Source")
                headline = title.rsplit(" - ", 1)[0] if " - " in title else title

                # Age filter
                try:
                    pub_date = parsedate_to_datetime(pub_str)
                    if datetime.now(pub_date.tzinfo) - pub_date > timedelta(hours=max_age_h):
                        continue
                except Exception:
                    pass  # Keep article if date parsing fails

                # Classify tier
                tier, weight = self.classify_source(source)

                news_items.append({
                    "headline": headline,
                    "source":   source,
                    "url":      link,
                    "pub_date": pub_str,
                    "tier":     tier,
                    "weight":   weight,
                })

            return news_items

        except Exception as e:
            print(f"  [GoogleNews] Error parsing RSS for '{query}': {e}")
            return []

    def classify_source(self, source: str) -> tuple[int, float]:
        """
        Returns (tier, weight) for a given source string.

        Weights come from config so PortfolioTuner can tune them.
        """
        w1 = getattr(config, "SENTIMENT_TIER1_WEIGHT", 1.0)
        w2 = getattr(config, "SENTIMENT_TIER2_WEIGHT", 0.6)
        w3 = getattr(config, "SENTIMENT_TIER3_WEIGHT", 0.3)

        src_lower = source.lower()
        if any(t in src_lower for t in self.TIER_1_SOURCES):
            return 1, w1
        if any(t in src_lower for t in self.TIER_2_SOURCES):
            return 2, w2
        return 3, w3


class SentimentAnalyzer:
    def __init__(self, client=None):
        self.client  = client
        self.fetcher = GoogleNewsFetcher()

        print("  [Sentiment] Loading FinBERT model (this may take a moment)...")
        self.nlp = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        print("  [Sentiment] FinBERT loaded successfully.")

    # ------------------------------------------------------------------ #
    #  Core helpers                                                        #
    # ------------------------------------------------------------------ #

    def _score_articles(self, articles: list[dict]) -> tuple[float, dict | None]:
        """
        Runs FinBERT on every article's headline and returns a
        tier-weighted average sentiment score plus the top article metadata.

        Returns: (weighted_score, top_article_dict | None)
        """
        if not articles:
            return 0.0, None

        headlines = [a["headline"] for a in articles]
        try:
            results = self.nlp(headlines)
        except Exception as e:
            print(f"  [Sentiment] FinBERT inference error: {e}")
            return 0.0, None

        weighted_sum  = 0.0
        weight_total  = 0.0
        max_impact    = -1.0
        top_article   = None

        tier_counts = {1: 0, 2: 0, 3: 0}

        for i, res in enumerate(results):
            article  = articles[i]
            label    = res["label"]
            conf     = res["score"]
            weight   = article["weight"]
            tier     = article["tier"]

            if label == "positive":
                raw_score = conf
            elif label == "negative":
                raw_score = -conf
            else:
                raw_score = 0.0

            weighted_sum  += raw_score * weight
            weight_total  += weight
            tier_counts[tier] += 1

            # Track top article (highest absolute confidence × tier weight)
            impact = conf * weight
            if impact > max_impact:
                max_impact  = impact
                top_article = {
                    "source":   article["source"],
                    "headline": article["headline"],
                    "url":      article["url"],
                    "score":    raw_score,
                    "tier":     tier,
                }

        score = (weighted_sum / weight_total) if weight_total > 0 else 0.0
        return score, top_article, tier_counts

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def analyze_sentiment(self, symbol: str) -> tuple[float, dict | None]:
        """
        Fetches news from Google News, applies tier-weighted FinBERT scoring,
        and returns (sentiment_score, top_news_metadata).

        • Tier 1 articles are scored at full weight.
        • Tier 2 articles contribute at SENTIMENT_TIER2_WEIGHT (default 0.6).
        • Tier 3 articles contribute at SENTIMENT_TIER3_WEIGHT (default 0.3).
        • Returns (0.0, None) only if there are NO articles at all.
        """
        try:
            raw_news = self.fetcher.fetch_news(symbol=symbol)
            if not raw_news:
                print(f"  [News] {symbol}: No news found via Google RSS.")
                return 0.0, None

            min_articles = getattr(config, "SENTIMENT_MIN_ARTICLES", 2)
            if len(raw_news) < min_articles:
                print(f"  [News] {symbol}: Only {len(raw_news)} article(s) found "
                      f"(min={min_articles}). Score unreliable — returning neutral.")
                return 0.0, None

            # Log tier breakdown
            t1 = sum(1 for a in raw_news if a["tier"] == 1)
            t2 = sum(1 for a in raw_news if a["tier"] == 2)
            t3 = sum(1 for a in raw_news if a["tier"] == 3)
            print(f"  [News] {symbol}: {len(raw_news)} articles "
                  f"[T1:{t1} T2:{t2} T3:{t3}]")

            # Log up to 3 headlines
            for i, a in enumerate(raw_news[:3]):
                tier_label = f"T{a['tier']}"
                print(f"    • [{tier_label}][{a['source']}] "
                      f"{a['headline'][:60]}…")

            score, top_article, _ = self._score_articles(raw_news)
            print(f"    → Weighted Sentiment Score: {score:.3f}")
            return score, top_article

        except Exception as e:
            print(f"  [Sentiment] Error analyzing {symbol}: {e}")
            import traceback; traceback.print_exc()
            return 0.0, None

    def analyze_market_sentiment(self) -> float:
        """
        Analyses broader market sentiment using general queries.
        Uses tier-weighted scoring (same as per-symbol).
        """
        try:
            print("\n  [Sentiment] Analyzing Broad Market Sentiment…")
            queries = ["Stock Market News", "Economy News", "S&P 500"]
            all_articles: list[dict] = []

            for q in queries:
                articles = self.fetcher.fetch_news(custom_query=q)
                all_articles.extend(articles)

            # Deduplicate by headline
            seen: set[str] = set()
            unique_articles: list[dict] = []
            for a in all_articles:
                if a["headline"] not in seen:
                    seen.add(a["headline"])
                    unique_articles.append(a)

            if not unique_articles:
                print("  [Sentiment] No market news found. Assuming Neutral (0.0).")
                return 0.0

            max_headlines = getattr(config, "SENTIMENT_MAX_HEADLINES", 30)
            capped = unique_articles[:max_headlines]

            t1 = sum(1 for a in capped if a["tier"] == 1)
            t2 = sum(1 for a in capped if a["tier"] == 2)
            t3 = sum(1 for a in capped if a["tier"] == 3)

            score, _, _ = self._score_articles(capped)

            mood = "NEUTRAL"
            if score > 0.15:
                mood = "BULLISH"
            elif score < -0.15:
                mood = "BEARISH"

            print(f"  [Sentiment] Market Score: {score:.3f} ({mood}) | "
                  f"{len(capped)} headlines [T1:{t1} T2:{t2} T3:{t3}]")
            return score

        except Exception as e:
            print(f"  [Sentiment] Market analysis failed: {e}")
            return 0.0
