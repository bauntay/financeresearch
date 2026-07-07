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

# Kuratierte Rueckfalllisten, falls das Wikipedia-Scraping der
# Index-Zusammensetzung fehlschlaegt (z.B. weil sich die Tabellenstruktur
# geaendert hat). Kein Anspruch auf Vollstaendigkeit/Aktualitaet.
NASDAQ100_FALLBACK = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AVGO",
    "COST", "PEP", "ADBE", "NFLX", "CSCO", "AMD", "INTC", "QCOM", "TXN",
    "INTU", "AMGN", "HON", "SBUX", "BKNG", "GILD", "MDLZ", "ADI", "VRTX",
    "REGN", "ISRG", "LRCX",
]
EUROSTOXX50_FALLBACK = [
    "ASML.AS", "SAP.DE", "MC.PA", "OR.PA", "TTE.PA", "SAN.PA", "SIE.DE",
    "ALV.DE", "AIR.PA", "BNP.PA", "ITX.MC", "IBE.MC", "ENEL.MI", "ISP.MI",
    "DTE.DE", "BAS.DE", "MUV2.DE", "ADS.DE", "DG.PA", "SU.PA",
]

INDEX_OPTIONS = {
    "Standard-Liste (30 Aktien)": None,
    "S&P 500": "sp500",
    "Nasdaq-100": "nasdaq100",
    "Euro Stoxx 50": "eurostoxx50",
}


@st.cache_data(ttl=86400, show_spinner=False)
def get_index_tickers(index_key: str) -> tuple:
    """Liest die Index-Zusammensetzung von Wikipedia, mit Rueckfall auf eine
    kuratierte, statische Liste falls das Scraping fehlschlaegt."""
    try:
        if index_key == "sp500":
            tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
            tickers = tables[0]["Symbol"].tolist()
            tickers = [t.replace(".", "-") for t in tickers]
        elif index_key == "nasdaq100":
            tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
            df = next(t for t in tables if "Ticker" in t.columns)
            tickers = df["Ticker"].tolist()
        elif index_key == "eurostoxx50":
            tables = pd.read_html("https://en.wikipedia.org/wiki/EURO_STOXX_50")
            df = next(t for t in tables if any(c in t.columns for c in ("Ticker", "Ticker symbol")))
            col = "Ticker" if "Ticker" in df.columns else "Ticker symbol"
            tickers = df[col].tolist()
        else:
            return tuple(DEFAULT_UNIVERSE)
        tickers = [str(t).strip().upper() for t in tickers if str(t).strip()]
        return tuple(dict.fromkeys(tickers))
    except Exception:
        fallback = {"sp500": DEFAULT_UNIVERSE, "nasdaq100": NASDAQ100_FALLBACK, "eurostoxx50": EUROSTOXX50_FALLBACK}
        return tuple(fallback.get(index_key, DEFAULT_UNIVERSE))


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
            volume = df["Volume"]
            sma20 = close.rolling(20).mean().iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1]
            sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan
            rsi = compute_rsi(close).iloc[-1]
            high_52w = df["High"].rolling(min(len(df), 252)).max().iloc[-1]
            low_52w = df["Low"].rolling(min(len(df), 252)).min().iloc[-1]
            last_close = close.iloc[-1]

            # Relative Staerke nach Levy: aktueller Kurs / gleitender
            # Durchschnitt der letzten 27 Wochen (~130 Handelstage).
            # Der Rang (Perzentil ueber das ganze Universum) wird weiter
            # unten nach der Schleife berechnet.
            sma_levy = close.rolling(130).mean().iloc[-1] if len(close) >= 130 else np.nan
            levy_rs = last_close / sma_levy if pd.notna(sma_levy) else np.nan

            perf_1d = close.iloc[-1] / close.iloc[-2] - 1 if len(close) >= 2 else np.nan
            perf_1w = close.iloc[-1] / close.iloc[-6] - 1 if len(close) >= 6 else np.nan
            perf_1m = close.iloc[-1] / close.iloc[-22] - 1 if len(close) >= 22 else np.nan

            avg_vol20 = volume.rolling(20).mean().iloc[-1]
            vol_ratio = volume.iloc[-1] / avg_vol20 if pd.notna(avg_vol20) and avg_vol20 > 0 else np.nan

            rows.append({
                "Ticker": ticker,
                "Kurs": round(last_close, 2),
                "SMA20": round(sma20, 2) if pd.notna(sma20) else np.nan,
                "SMA50": round(sma50, 2) if pd.notna(sma50) else np.nan,
                "SMA200": round(sma200, 2) if pd.notna(sma200) else np.nan,
                "RSI14": round(rsi, 1) if pd.notna(rsi) else np.nan,
                "Levy RS": round(levy_rs, 3) if pd.notna(levy_rs) else np.nan,
                "52W Hoch": round(high_52w, 2),
                "52W Tief": round(low_52w, 2),
                "% vom 52W-Hoch": round((last_close / high_52w - 1) * 100, 1),
                "1T %": round(perf_1d * 100, 1) if pd.notna(perf_1d) else np.nan,
                "1W %": round(perf_1w * 100, 1) if pd.notna(perf_1w) else np.nan,
                "1M %": round(perf_1m * 100, 1) if pd.notna(perf_1m) else np.nan,
                "Vol-Ratio": round(vol_ratio, 2) if pd.notna(vol_ratio) else np.nan,
            })
        except Exception:
            continue

    result = pd.DataFrame(rows)
    if not result.empty:
        # RS-Rang: Perzentil-Rang der Levy-RS ueber das gesamte geladene
        # Universum (1-99, aehnlich der IBD RS Rating), NaN bleibt NaN.
        result["RS-Rang"] = (result["Levy RS"].rank(pct=True) * 100).round(0)
    return result


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def style_sma_columns(df: pd.DataFrame):
    """Hebt SMA20/SMA50/SMA200 hellgruen hervor, wenn der Kurs darueber
    liegt, und hellrot, wenn er darunter liegt."""
    def _row_style(row):
        styles = pd.Series("", index=row.index)
        for col in ("SMA20", "SMA50", "SMA200"):
            if col not in row.index or pd.isna(row[col]) or pd.isna(row["Kurs"]):
                continue
            if row["Kurs"] > row[col]:
                styles[col] = "background-color: #d4f7d4; color: #000000"
            elif row["Kurs"] < row[col]:
                styles[col] = "background-color: #f9d4d4; color: #000000"
        return styles

    return df.style.apply(_row_style, axis=1)


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

    index_choice = st.selectbox("Aktien-Universe", list(INDEX_OPTIONS.keys()))
    custom_input = st.text_input(
        "Eigene Ticker (kommagetrennt, optional - überschreibt die Auswahl oben)",
        "",
    )

    if custom_input.strip():
        universe = tuple(t.strip().upper() for t in custom_input.split(",") if t.strip())
    elif INDEX_OPTIONS[index_choice] is None:
        universe = tuple(DEFAULT_UNIVERSE)
    else:
        with st.spinner(f"Lade Ticker-Liste für {index_choice}..."):
            universe = get_index_tickers(INDEX_OPTIONS[index_choice])
        st.caption(f"{len(universe)} Ticker geladen.")

    st.markdown("**Trend**")
    t1, t2, t3, t4 = st.columns(4)
    filter_above_sma20 = t1.checkbox("Kurs über SMA20")
    filter_above_sma50 = t2.checkbox("Kurs über SMA50", value=True)
    filter_above_sma200 = t3.checkbox("Kurs über SMA200")
    cross_choice = t4.selectbox("SMA50/SMA200-Kreuzung", ["Keine Filterung", "Golden Cross (SMA50 > SMA200)", "Death Cross (SMA50 < SMA200)"])

    st.markdown("**Momentum**")
    m1, m2, m3, m4 = st.columns(4)
    filter_oversold = m1.checkbox("RSI < 30 (überverkauft)")
    min_rs_rank = m2.slider("Mindest RS-Rang (Levy)", 0, 99, 0, help="Perzentil-Rang der Relativen Stärke nach Levy über das gewählte Universum. 0 = Filter deaktiviert.")
    filter_positive_1m = m3.checkbox("Positive 1-Monats-Performance")
    filter_volume_breakout = m4.checkbox("Volumen-Ausbruch (>1.5x Ø)")

    filter_near_high = st.checkbox("Innerhalb 10% vom 52W-Hoch")

    if st.button("Screener ausführen", type="primary"):
        with st.spinner(f"Lade Daten für {len(universe)} Ticker..."):
            snapshot = load_universe_snapshot(universe)

        if snapshot.empty:
            st.error("Keine Daten gefunden. Bitte Ticker-Symbole prüfen.")
        else:
            result = snapshot.copy()
            if filter_above_sma20:
                result = result[result["Kurs"] > result["SMA20"]]
            if filter_above_sma50:
                result = result[result["Kurs"] > result["SMA50"]]
            if filter_above_sma200:
                result = result[result["Kurs"] > result["SMA200"]]
            if cross_choice == "Golden Cross (SMA50 > SMA200)":
                result = result[result["SMA50"] > result["SMA200"]]
            elif cross_choice == "Death Cross (SMA50 < SMA200)":
                result = result[result["SMA50"] < result["SMA200"]]
            if filter_oversold:
                result = result[result["RSI14"] < 30]
            if min_rs_rank > 0:
                result = result[result["RS-Rang"] >= min_rs_rank]
            if filter_positive_1m:
                result = result[result["1M %"] > 0]
            if filter_volume_breakout:
                result = result[result["Vol-Ratio"] > 1.5]
            if filter_near_high:
                result = result[result["% vom 52W-Hoch"] >= -10]

            st.write(f"**{len(result)} von {len(snapshot)} Aktien erfüllen die Kriterien:**")
            st.caption("🟢 Kurs über dem gleitenden Durchschnitt · 🔴 Kurs darunter (SMA20/SMA50/SMA200).")
            result_sorted = result.sort_values("RS-Rang", ascending=False)
            st.dataframe(style_sma_columns(result_sorted), use_container_width=True, hide_index=True)

st.caption("Daten von Yahoo Finance über yfinance. Nur zu Informationszwecken, keine Anlageberatung.")
