
import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page Config
st.set_page_config(
    page_title="Mini AI Hedge Fund | Live Monitor",
    page_icon="🤖",
    layout="wide",
)

# Dark Theme Styling
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #3e4150;
    }
    .css-1r6slb0 { /* sidebar */
        background-color: #161b22;
    }
    </style>
    """, unsafe_allow_html=True)

# Data Loading Functions
def load_history():
    path = "logs/portfolio_history.json"
    if os.path.exists(path):
        with open(path, 'r') as f:
            return pd.DataFrame(json.load(f))
    return pd.DataFrame()

def load_latest_state():
    path = "logs/latest_state.json"
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return None

# --- Main Dashboard ---
st.title("🤖 Mini AI Hedge Fund - Live Monitor")

latest = load_latest_state()
history = load_history()

if latest:
    # Sidebar Info
    st.sidebar.header("Market Environment")
    vix = latest.get('vix', 20.0)
    regime = latest.get('regime', 'NORMAL')
    
    vix_color = "red" if vix > 25 else "green" if vix < 15 else "blue"
    st.sidebar.markdown(f"**VIX (Fear Index):** <span style='color:{vix_color}'>{vix:.2f}</span>", unsafe_allow_html=True)
    st.sidebar.markdown(f"**Regime:** `{regime}`")
    
    # Risk Metrics
    risk = latest.get('risk_metrics', {})
    beta = risk.get('beta', 0.0)
    net_exp = risk.get('net_exposure', 0.0)
    
    beta_color = "red" if beta > 1.2 else "green" if beta > 0.8 else "blue"
    st.sidebar.markdown(f"**Portfolio Beta:** <span style='color:{beta_color}'>{beta:.2f}</span>", unsafe_allow_html=True)
    st.sidebar.markdown(f"**Net Exposure:** `${net_exp:,.2f}`")
    
    st.sidebar.divider()
    
    st.sidebar.header("Bot Status")
    st.sidebar.success("RUNNING" if (datetime.now() - datetime.strptime(latest['timestamp'], "%Y-%m-%d %H:%M:%S")).seconds < 3600 else "STANDBY")
    st.sidebar.info(f"Last Log: {latest['timestamp']}")
    
    # Top Metrics
    col1, col2, col3, col4 = st.columns(4)
    equity = latest['equity']
    cash = latest['cash']
    
    # Calculate Daily PnL Pct (Assuming $100k starting if history empty)
    start_val = history['equity'].iloc[0] if not history.empty else 100000
    pnl_val = equity - start_val
    pnl_pct = (pnl_val / start_val) * 100

    col1.metric("Portfolio Value", f"${equity:,.2f}", f"{pnl_pct:+.2f}%")
    col2.metric("Cash Balance", f"${cash:,.2f}")
    col3.metric("Open Positions", len(latest['positions']))
    col4.metric("Active Signals", len(latest['signals']))

    # --- PERFORMANCE METRICS SECTION ---
    st.divider()
    st.subheader("📊 Performance Metrics")
    
    perf = latest.get('performance_metrics', {})
    
    # Create metrics grid
    m1, m2, m3, m4, m5 = st.columns(5)
    
    # Sharpe Ratio
    sharpe = perf.get('sharpe_ratio', 0.0)
    sharpe_color = "🟢" if sharpe > 1.5 else "🟡" if sharpe > 1.0 else "🔴"
    m1.metric(
        "Sharpe Ratio",
        f"{sharpe:.2f}",
        help="Risk-adjusted return. >1.5 is excellent, >1.0 is good"
    )
    m1.markdown(f"<p style='text-align:center; font-size:24px;'>{sharpe_color}</p>", unsafe_allow_html=True)
    
    # Max Drawdown
    max_dd = perf.get('max_drawdown', 0.0)
    dd_color = "🟢" if max_dd > -10 else "🟡" if max_dd > -20 else "🔴"
    m2.metric(
        "Max Drawdown",
        f"{max_dd:.1f}%",
        help="Largest peak-to-trough decline. <-10% is great, <-20% is acceptable"
    )
    m2.markdown(f"<p style='text-align:center; font-size:24px;'>{dd_color}</p>", unsafe_allow_html=True)
    
    # Win Rate
    win_rate = perf.get('win_rate', 0.0)
    wr_color = "🟢" if win_rate > 60 else "🟡" if win_rate > 50 else "🔴"
    m3.metric(
        "Win Rate", 
        f"{win_rate:.1f}%",
        f"{perf.get('wins', 0)}W / {perf.get('losses', 0)}L",
        help="Percentage of profitable trades. >60% is excellent"
    )
    m3.markdown(f"<p style='text-align:center; font-size:24px;'>{wr_color}</p>", unsafe_allow_html=True)
    
    # Alpha vs S&P 500
    alpha = perf.get('alpha', 0.0)
    alpha_color = "🟢" if alpha > 5 else "🟡" if alpha > 0 else "🔴"
    m4.metric(
        "Alpha (vs SPY)",
        f"{alpha:+.1f}%",
        help="Excess return vs S&P 500 benchmark. Positive = outperforming"
    )
    m4.markdown(f"<p style='text-align:center; font-size:24px;'>{alpha_color}</p>", unsafe_allow_html=True)
    
    # Volatility
    vol = perf.get('volatility', 0.0)
    vol_color = "🟢" if vol < 15 else "🟡" if vol < 25 else "🔴"
    m5.metric(
        "Volatility",
        f"{vol:.1f}%",
        help="Annualized standard deviation. Lower is smoother"
    )
    m5.markdown(f"<p style='text-align:center; font-size:24px;'>{vol_color}</p>", unsafe_allow_html=True)
    
    # Additional metrics row
    st.markdown("---")
    a1, a2, a3, a4 = st.columns(4)
    
    a1.metric(
        "Total Return",
        f"${perf.get('total_return', 0):,.2f}",
        f"{perf.get('total_return_pct', 0):.2f}%"
    )
    
    a2.metric(
        "Total Trades",
        f"{perf.get('total_trades', 0)}",
        f"PF: {perf.get('profit_factor', 0):.2f}"
    )
    
    a3.metric(
        "Avg Win",
        f"${perf.get('avg_win', 0):,.2f}"
    )
    
    a4.metric(
        "Avg Loss", 
        f"${perf.get('avg_loss', 0):,.2f}"
    )


    # --- NEW: Top Market Catalyst Preview ---
    # Find the signal with the highest confidence that HAS a news catalyst
    top_catalyst = None
    top_catalyst_sym = None
    
    if latest['signals']:
        # Sort by confidence descending
        sorted_signals = sorted(
            latest['signals'].items(), 
            key=lambda x: x[1].get('confidence', 0), 
            reverse=True
        )
        
        for sym, data in sorted_signals:
            cat = data.get('catalyst')
            if cat and isinstance(cat, dict) and cat.get('headline'):
                top_catalyst = cat
                top_catalyst_sym = sym
                break
    
    if top_catalyst:
        st.markdown("### 📰 Top Market Catalyst")
        with st.container():
            # Styling for the news card
            st.markdown(f"""
            <div style="background-color: #262730; padding: 20px; border-radius: 10px; border-left: 5px solid #00d4ff; margin-bottom: 20px;">
                <h4 style="margin:0; color: #aaa; font-size: 0.9em;">AFFECTING: <span style="color: #fff; font-weight: bold; font-size: 1.1em;">{top_catalyst_sym}</span> <span style="color: #555;">|</span> SOURCE: {top_catalyst.get('source', 'Unknown')}</h4>
                <h2 style="margin-top: 10px; margin-bottom: 10px; font-size: 1.5em;">{top_catalyst.get('headline', 'No Headline')}</h2>
                <p style="color: #ccc;"><i>"This news article was identified as a primary driver for the {top_catalyst_sym} trade signal."</i></p>
                <a href="{top_catalyst.get('url', '#')}" target="_blank" style="text-decoration: none;">
                    <button style="background-color: #00d4ff; color: #000; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                        Read Full Article 🔗
                    </button>
                </a>
            </div>
            """, unsafe_allow_html=True)


    # Equity Curve
    if not history.empty:
        st.subheader("📈 Performance (Equity Curve)")
        if len(history) < 3:
            st.info(f"📊 Collecting data... ({len(history)} data point{'s' if len(history) > 1 else ''} so far). The curve will become more meaningful as the bot runs more cycles.")
        fig = px.line(history, x='timestamp', y='equity', 
                      template="plotly_dark", 
                      color_discrete_sequence=['#00d4ff'])
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    # Tables Row
    st.divider()
    c1, c2 = st.columns([1.2, 1])

    with c1:
        st.subheader("📂 Open Positions")
        if latest['positions']:
            pos_df = pd.DataFrame(latest['positions'])
            # Style PnL Column
            def color_pnl(val):
                color = '#ff4b4b' if val < 0 else '#00cc96'
                return f'color: {color}'
            
            # Helper to calculate Price Levels
            def calc_levels(row):
                entry = row.get('avg_entry', 0)
                sl_pct = row.get('sl_pct', 0.05)
                tp_pct = row.get('tp_pct', 0.10)
                
                # Assume Long for now (Dashboard mainly supports Long logic visualisation)
                sl_price = entry * (1 - sl_pct)
                tp_price = entry * (1 + tp_pct)
                
                return pd.Series([sl_price, tp_price])

            result_cols = pos_df.apply(calc_levels, axis=1)
            pos_df[['Stop ($)', 'Target ($)']] = result_cols
            
            # Format
            pos_df['Stop ($)'] = pos_df['Stop ($)'].map('${:,.2f}'.format)
            pos_df['Target ($)'] = pos_df['Target ($)'].map('${:,.2f}'.format)
            
            # Select columns
            display_cols = ['symbol', 'qty', 'market_value', 'pnl', 'Stop ($)', 'Target ($)']
            final_df = pos_df[display_cols].rename(columns={
                'symbol': 'Ticker', 'qty': 'Qty', 
                'market_value': 'Value', 'pnl': 'PnL ($)'
            })
            
            st.dataframe(final_df.style.applymap(color_pnl, subset=['PnL ($)']), use_container_width=True)
        else:
            st.write("No open positions.")

    with c2:
        st.subheader("🎯 Active AI Signals")
        if latest['signals']:
            try:
                # Convert dict to DataFrame
                df_signals = pd.DataFrame.from_dict(latest['signals'], orient='index')
                df_signals.index.name = 'Symbol'
                df_signals.reset_index(inplace=True)
                
                # Check if 'reason' column exists (for backward compatibility)
                if 'reason' not in df_signals.columns:
                    df_signals['reason'] = "N/A"
                
                # Formatting
                df_signals['confidence'] = df_signals['confidence'].mul(100).map('{:.1f}%'.format)
                df_signals['volatility'] = df_signals['volatility'].mul(100).map('{:.2f}%'.format)
                df_signals['action'] = df_signals['action'].str.upper()

                # Format Catalyst
                def format_catalyst(cat):
                    if isinstance(cat, dict):
                        return f"[{cat.get('source', 'Unknown')}] {cat.get('headline', '')}"
                    return "No Significant News"

                if 'catalyst' not in df_signals.columns:
                    df_signals['catalyst'] = None
                    
                df_signals['catalyst'] = df_signals['catalyst'].apply(format_catalyst)
                
                # Rename to match desired output
                df_signals = df_signals.rename(columns={
                    'confidence': 'Conf',
                    'volatility': 'Vol',
                    'action': 'Action'
                })

                # Stylized Dataframe
                st.dataframe(
                    df_signals[['Symbol', 'Action', 'Conf', 'Vol', 'reason', 'catalyst']],
                    column_config={
                        "Symbol": st.column_config.TextColumn("Ticker", width="small"),
                        "Action": st.column_config.TextColumn("Action", width="small"),
                        "Conf": st.column_config.TextColumn("Conf", width="small"),
                        "Vol": st.column_config.TextColumn("Vol", width="small"),
                        "reason": st.column_config.TextColumn(
                            "AI Reason & Logic",
                            width="medium",
                            help="Shows the breakdown of the ensemble model (Regime, MC, RF, Sentiment)"
                        ),
                        "catalyst": st.column_config.TextColumn(
                            "News Catalyst",
                            width="large",
                            help="The specific news story driving sentiment."
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
            except Exception as e:
                st.error(f"Error displaying signals: {e}")
        else:
            st.info("Waiting for next scan cycle...")

    # Log/Insights
    with st.expander("📝 Latest Lifecycle Insights"):
        st.write("**Potential Buys (Filtered):**", latest.get('potential_buys', []))
        st.write("**MVO Allocations:**", latest.get('allocations', {}))

    st.divider()
    
    # --- MARKET PULSE SECTION ---
    st.subheader("🌐 Market Pulse & Scanner")
    
    # 1. Market Sentiment Display
    ms = latest.get('market_sentiment', {})
    ms_score = ms.get('score', 0.0)
    ms_mood = ms.get('mood', 'NEUTRAL')
    
    # Determine Color
    if ms_mood == 'BULLISH': mid_color = '#00cc96' # Green
    elif ms_mood == 'BEARISH': mid_color = '#ef553b' # Red
    else: mid_color = '#ffa15a' # Orange
    
    mp_col1, mp_col2 = st.columns([1, 2])
    
    with mp_col1:
        st.markdown(f"""
        <div style="text-align: center; border: 1px solid #333; padding: 10px; border-radius: 10px; background-color: #1e2130;">
            <h4 style="margin-bottom: 5px;">Broad Market Sentiment</h4>
            <h2 style="color: {mid_color}; margin: 0;">{ms_mood}</h2>
            <p style="font-size: 1.2em; color: #ccc;">Score: <b>{ms_score:.2f}</b></p>
            <p style="font-size: 0.8em; color: #777;">(Checks Tier 1 News for "S&P 500", "Economy")</p>
        </div>
        """, unsafe_allow_html=True)
        
    # 2. Screener Picks Display
    with mp_col2:
        st.markdown("#### 🔍 Daily Screener Top Picks")
        picks = latest.get('screener_picks', [])
        
        if picks:
            # We don't have individual sentiment scores for picks in the log yet, 
            # effectively they are "Approved" if they are in this list.
            # We'll display them as tiles.
            
            tiles_html = ""
            for sym in picks:
                tiles_html += f"""
                <div style="display: inline-block; background-color: #262730; border: 1px solid #444; border-radius: 5px; padding: 10px; margin: 5px;">
                    <span style="font-weight: bold; font-size: 1.1em; color: #64b5f6;">{sym}</span>
                    <br>
                    <span style="font-size: 0.8em; color: #00cc96;">✅ News Validated</span>
                </div>
                """
            
            st.markdown(tiles_html, unsafe_allow_html=True)
            st.caption("These assets passed both Technical Filters AND Sentiment Validation.")
        else:
            st.info("No assets passed the screener active filters today.")

else:
    st.warning("No log data found yet. Start the bot with `main.py` and wait for the first trading cycle to complete.")
    st.info("The dashboard will refresh automatically once data is available in `logs/portfolio_history.json`.")

# Auto-refresh every 60 seconds
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=60 * 1000, key="data_refresh")
