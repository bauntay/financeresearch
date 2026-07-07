"""
Finance Research Dashboard
Zwei Bereiche: Kursdaten & Charts sowie ein einfacher Stock-Screener.
Datenquelle: Yahoo Finance (via yfinance) - kostenlos, kein API-Key noetig.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

st.set_page_config(page_title="Finance Research Dashboard", layout="wide")

# Kleine Auswahl an bekannten US-Aktien fuer den Screener.
# Bewusst klein gehalten, damit der Live-Abruf auf dem kostenlosen
# Streamlit-Hosting schnell genug bleibt.
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM",
    "V", "UNH", "HD", "PG", "MA", "DIS", "ADBE", "NFLX", "KO", "PEP", "CSCO",
    "INTC", "AMD", "CRM", "PFE", "XOM", "CVX", "WMT", "MCD", "NKE", "BA",
]


@st.cache_data(ttl=900, show_spinner=False)
def load_price_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna(how="all")


@st.cache_data(ttl=900, show_spinner=False)
def load_universe_snapshot(tickers: tuple) -> pd.DataFrame:
    raw = yf.download(
        tickers=list(tickers),
        period="1y",
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False,
        auto_adjust=False,
    )

    rows = []
    for ticker in tickers:
        try:
            df = raw[ticker].dropna(how="all") if len(tickers) > 1 else raw.dropna(how="all")
            if df.empty or len(df) < 60:
                continue
            close = df["Close"]
            sma50 = close.rolling(50).mean().iloc[-1]
            sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan
            rsi = compute_rsi(close).iloc[-1]
            high_52w = df["High"].rolling(min(len(df), 252)).max().iloc[-1]
            low_52w = df["Low"].rolling(min(len(df), 252)).min().iloc[-1]
            last_close = close.iloc[-1]
            rows.append({
                "Ticker": ticker,
                "Kurs": round(last_close, 2),
                "SMA50": round(sma50, 2) if pd.notna(sma50) else np.nan,
                "SMA200": round(sma200, 2) if pd.notna(sma200) else np.nan,
                "RSI14": round(rsi, 1) if pd.notna(rsi) else np.nan,
                "52W Hoch": round(high_52w, 2),
                "52W Tief": round(low_52w, 2),
                "% vom 52W-Hoch": round((last_close / high_52w - 1) * 100, 1),
            })
        except Exception:
            continue

    return pd.DataFrame(rows)


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


st.title("📈 Finance Research Dashboard")

tab_charts, tab_screener = st.tabs(["Kursdaten & Charts", "Stock-Screener"])

with tab_charts:
    col1, col2, col3 = st.columns([2, 1, 1])
    ticker = col1.text_input("Ticker", "AAPL").strip().upper()
    period = col2.selectbox("Zeitraum", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)
    interval = col3.selectbox("Intervall", ["1d", "1wk", "1mo"], index=0)

    if ticker:
        with st.spinner(f"Lade Daten für {ticker}..."):
            df = load_price_history(ticker, period, interval)

        if df.empty:
            st.error(f"Keine Daten für '{ticker}' gefunden. Bitte Ticker-Symbol prüfen.")
        else:
            df["SMA20"] = df["Close"].rolling(20).mean()
            df["SMA50"] = df["Close"].rolling(50).mean()
            df["RSI14"] = compute_rsi(df["Close"])

            latest = df.iloc[-1]
            prev_close = df["Close"].iloc[-2] if len(df) > 1 else latest["Close"]
            change_pct = (latest["Close"] / prev_close - 1) * 100

            m1, m2, m3 = st.columns(3)
            m1.metric("Letzter Kurs", f"{latest['Close']:.2f}", f"{change_pct:.2f}%")
            m2.metric("SMA20", f"{latest['SMA20']:.2f}" if pd.notna(latest["SMA20"]) else "–")
            m3.metric("RSI14", f"{latest['RSI14']:.1f}" if pd.notna(latest["RSI14"]) else "–")

            fig = make_subplots(
                rows=3, cols=1, shared_xaxes=True, row_heights=[0.55, 0.2, 0.25],
                vertical_spacing=0.03,
                subplot_titles=(f"Kurs – {ticker}", "Volumen", "RSI (14)"),
            )
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                name="Kurs",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], name="SMA20", line=dict(width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], name="SMA50", line=dict(width=1)), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volumen", marker_color="gray"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI14"], name="RSI14", line=dict(color="orange")), row=3, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

            fig.update_layout(height=800, xaxis_rangeslider_visible=False, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Rohdaten anzeigen"):
                st.dataframe(df.tail(200), use_container_width=True)

with tab_screener:
    st.write("Filtert eine Aktienliste nach einfachen technischen Kriterien (Daten von Yahoo Finance).")

    custom_input = st.text_input(
        "Eigene Ticker (kommagetrennt, optional - überschreibt die Standardliste)",
        "",
    )
    universe = tuple(
        t.strip().upper() for t in custom_input.split(",") if t.strip()
    ) or tuple(DEFAULT_UNIVERSE)

    c1, c2, c3, c4 = st.columns(4)
    filter_above_sma50 = c1.checkbox("Kurs über SMA50", value=True)
    filter_above_sma200 = c2.checkbox("Kurs über SMA200")
    filter_oversold = c3.checkbox("RSI < 30 (überverkauft)")
    filter_near_high = c4.checkbox("Innerhalb 10% vom 52W-Hoch")

    if st.button("Screener ausführen", type="primary"):
        with st.spinner(f"Lade Daten für {len(universe)} Ticker..."):
            snapshot = load_universe_snapshot(universe)

        if snapshot.empty:
            st.error("Keine Daten gefunden. Bitte Ticker-Symbole prüfen.")
        else:
            result = snapshot.copy()
            if filter_above_sma50:
                result = result[result["Kurs"] > result["SMA50"]]
            if filter_above_sma200:
                result = result[result["Kurs"] > result["SMA200"]]
            if filter_oversold:
                result = result[result["RSI14"] < 30]
            if filter_near_high:
                result = result[result["% vom 52W-Hoch"] >= -10]

            st.write(f"**{len(result)} von {len(snapshot)} Aktien erfüllen die Kriterien:**")
            st.dataframe(result.sort_values("% vom 52W-Hoch", ascending=False), use_container_width=True, hide_index=True)

st.caption("Daten von Yahoo Finance über yfinance. Nur zu Informationszwecken, keine Anlageberatung.")
