import os
from dotenv import load_dotenv

load_dotenv()

# Alpaca API Credentials
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

# Validate Credentials
if not API_KEY or not SECRET_KEY:
    raise ValueError("Missing API Keys! Please check your .env file.")

# Model Hyperparameters
SEQ_LENGTH = 30      # Look back 30 minutes
HIDDEN_DIM = 64      # LSTM hidden units
NUM_LAYERS = 2       # LSTM layers
OUTPUT_DIM = 1       # 1 = Probability of Price UP
DROPOUT = 0.2
EPOCHS = 50
BATCH_SIZE = 32
LEARNING_RATE = 0.005

# Trading Settings
TRADE_ALLOCATION = 0.1   # Allocate 10% of portfolio per trade
STOP_LOSS_PCT = 0.05     # 5% Stop Loss (wider for multi-day holds)
TAKE_PROFIT_PCT = 0.10   # 10% Take Profit (2:1 risk/reward)
ENABLE_RISK_MANAGER = True # Master toggle for SL/TP checks

# Dynamic Risk Settings (ATR-Based)
USE_ATR_BASED_RISK = True
ATR_MULTIPLIER_SL = 1.5    # Stop Loss = 1.5x Daily ATR
ATR_MULTIPLIER_TP = 3.0    # Take Profit = 3.0x Daily ATR

# Trading Thresholds (Confidence-based)
# Conservative thresholds - only trade when there's genuine conviction
CONFIDENCE_THRESHOLD_BUY = 0.55   # Buy signal threshold
CONFIDENCE_THRESHOLD_SELL = 0.45  # Sell signal threshold

# Minimum conviction requirement (distance from neutral 0.50)
# Prevents trading on weak signals that are barely different from random
MIN_CONFIDENCE_GAP = 0.10  # Require at least 0.10 away from neutral (0.50)

# Volatility Protection Settings
VIX_THRESHOLD_HIGH = 25.0       # Points above which we scale up required confidence
DYNAMIC_GAP_MULTIPLIER = 1.5    # Scale the gap by this when VIX is high
SIDEWAYS_REGIME_PENALTY = 0.05  # Subtract this from confidence in ranging markets

# Trailing Stop Settings
ENABLE_TRAILING_STOP = True
TRAILING_STOP_PCT = 0.03    # 3% Trailing Stop

# Real-Market Readiness Settings
SLIPPAGE_BUFFER_PCT = 0.0005     # 0.05% buffer for limit orders
TRANSACTION_COST_PCT = 0.0001    # 0.01% estimated fees per trade
ORDER_TIMEOUT_MINUTES = 25       # Cancel stale orders before next 30min cycle

# Institutional Safeguards
MAX_SPREAD_PCT = 0.005           # 0.5% max Bid/Ask spread (avoids illiquid stocks)
# Alpha Booster Settings
ENABLE_PARTIAL_TP = True
PARTIAL_TP_PCT_LOW_VIX = 0.30   # Calm market: let 70% run
PARTIAL_TP_PCT_NORMAL = 0.50   # Normal market: sell half
PARTIAL_TP_PCT_HIGH_VIX = 0.75   # Fearful market: bank 75%
VIX_TP_LOW = 15.0
VIX_TP_HIGH = 25.0
CONVICTION_BOOST_LEVEL_1 = 0.70 # Scale to 1.5x at 70% confidence
CONVICTION_BOOST_LEVEL_2 = 0.80 # Scale to 2.0x at 80% confidence
RUNNER_TRAILING_STOP_PCT = 0.07 # Wider 7% stop for "runners" after partial TP
MARGIN_BUFFER_PCT = 0.05         # Keep 5% cash reserve for margin safety
MAX_PORTFOLIO_DRAWDOWN = 0.05    # 5% Portfolio-level Stop Loss (Lockdown)
PORTFOLIO_PROFIT_TARGET = 0.15   # 15% Portfolio-level Take Profit
ALLOCATION_STRATEGY = "HRP"      # Options: "MVO", "RISK_PARITY", "HRP"
HRP_LINKAGE_METHOD = "single"    # Linkage method for HRP: 'single', 'complete', 'average', 'ward'

# Market Open Protection (9:30 AM - 10:00 AM EST)
# Time is 24h format. US/Eastern timezone is assumed for these definitions.
MARKET_OPEN_START_HOUR = 9
MARKET_OPEN_START_MIN = 30
MARKET_OPEN_DURATION_MINS = 30

# Strategy A: Downside Noise Protection (ENTRY-based)
# Multiplier for ATR-based Stop Loss during opening noise.
# IMPORTANT: Value < 1.0 TIGHTENS the stop (cuts faster on volatile opens).
# Set to 1.0 to avoid prematurely cutting winners on standard morning volatility.
OPEN_STOP_LOSS_MULTIPLIER = 1.0  # Normal ATR during open window

# Strategy B: Upside Profit Locking (PEAK-based)
# Threshold and Trailing Stop for capturing gap reversals.
# Increased from 0.005 (0.5%) to 0.015 (1.5%) so protection activates on genuine surges.
OPEN_GAP_THRESHOLD = 0.015      # 1.5% gap triggers protection
OPEN_GAP_TRAILING_STOP = 0.01   # Tight 1% trailing stop on gap ups

# ── Sentiment Analysis (multi-tier weighted) ─────────────────────────────────
# PortfolioTuner will override these at runtime with learned values.
# These are the starting defaults only.
SENTIMENT_TIER1_WEIGHT       = 1.0   # Full trust: Bloomberg, Reuters, WSJ, CNBC, FT
SENTIMENT_TIER2_WEIGHT       = 0.6   # Partial trust: Yahoo Finance, Seeking Alpha, etc.
SENTIMENT_TIER3_WEIGHT       = 0.3   # Low trust: generic / community sources
SENTIMENT_MIN_ARTICLES       = 2     # Ignore score if fewer articles than this
SENTIMENT_MAX_HEADLINES      = 30    # Cap for market-wide query to save compute
SENTIMENT_ARTICLE_MAX_AGE_H  = 48    # Skip articles older than this many hours
SENTIMENT_VETO_THRESHOLD     = -0.2  # Score below which sentiment vetoes a buy
SENTIMENT_BOOST_THRESHOLD    = 0.2   # Score above which sentiment boosts confidence
SENTIMENT_BOOST_AMOUNT       = 0.1   # Confidence boost on positive sentiment
SENTIMENT_HARD_VETO_THRESHOLD = -0.6  # Score below which sentiment forces an absolute hold (no trading)
SENTIMENT_PENALTY_SCALE       = 0.5   # Negative sentiment penalty = abs(score) * this factor

# ── Smart Money Tracker ───────────────────────────────────────────────────────
SM_CACHE_DURATION_HOURS      = 4     # Hours to cache insider data per ticker
SM_HTTP_MAX_RETRIES          = 3     # HTTP retry attempts before giving up
SM_HTTP_RETRY_DELAY_S        = 2     # Seconds between retries
SM_FILINGS_TO_SCAN           = 20    # Number of recent filings to examine
SM_STRONG_BUY_THRESHOLD      = 0.5   # Score above which = strong insider buy
SM_STRONG_SELL_THRESHOLD     = -0.5  # Score below which = heavy insider selling
SM_BUY_CONFIDENCE_BOOST      = 0.15  # Confidence boost on strong insider buy
SM_SELL_CONFIDENCE_PENALTY   = 0.10  # Confidence reduction on heavy insider sell
SM_ALPHA_CONFIRM_THRESHOLD   = 0.3   # Insider score required to confirm borderline entries

# ── PortfolioTuner Meta-Learner ───────────────────────────────────────────────
TUNER_MIN_TRADES_TO_OPTIMIZE = 5     # Don't tune until at least this many trades closed
TUNER_OPTIMIZATION_INTERVAL  = 3     # Run one tuning step after every N closed trades
TUNER_EXPLORATION_WEIGHT     = 0.2   # UCB kappa: 0=pure exploit, higher=more explore
TUNER_PARAMS_PATH            = "models/portfolio_tuner_params.json"
TUNER_HISTORY_PATH           = "models/portfolio_tuner_history.json"
