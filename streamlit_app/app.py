"""
Finance Research Dashboard
Zwei Bereiche: Kursdaten & Charts sowie Watchlists & Screener (gespeicherte
Watchlists oder ganze Indizes nach technischen Kriterien filtern).
Datenquelle: Yahoo Finance (via yfinance) - kostenlos, kein API-Key noetig.
"""

import base64
import json
from io import StringIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

st.set_page_config(page_title="Finance Research Dashboard", layout="wide")

# Corporate-Design: dieselben zwei Blautoene und Schriftarten (Oswald/Overpass)
# wie in den anderen Dashboards.
BRAND_DARK_BLUE = "#004267"
BRAND_LIGHT_BLUE = "#84bdce"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Overpass:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Overpass', sans-serif;
    }}

    h1, h2, h3, h4, h5, h6,
    [data-testid="stMetricValue"],
    [data-testid="stMetricLabel"] {{
        font-family: 'Oswald', sans-serif !important;
        color: {BRAND_DARK_BLUE};
    }}

    [data-testid="stMetric"] {{
        background-color: {BRAND_LIGHT_BLUE}22;
        border-radius: 8px;
        padding: 10px 14px;
    }}

    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
        background-color: {BRAND_DARK_BLUE};
        color: #FFFFFF;
        border: 1px solid {BRAND_DARK_BLUE};
    }}
    .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
        background-color: {BRAND_LIGHT_BLUE};
        color: {BRAND_DARK_BLUE};
        border: 1px solid {BRAND_LIGHT_BLUE};
    }}

    /* Kompaktere vertikale Abstaende zwischen den Elementen */
    div[data-testid="stVerticalBlock"] {{
        gap: 0.65rem;
    }}
    .block-container {{
        padding-top: 2.5rem;
    }}
    h1 {{
        margin-bottom: 0.3rem;
    }}

    /* Seiten-Navigation (st.radio mit key="nav") als Tab-Pills stylen.
       Bewusst ueber die st-key-Klasse gescoped, damit normale Radios
       (z.B. die Quellen-Auswahl) unveraendert bleiben. */
    .st-key-nav div[role="radiogroup"] {{
        gap: 0.5rem;
        flex-direction: row;
    }}
    .st-key-nav label[data-testid="stRadioOption"] {{
        border: 1px solid {BRAND_LIGHT_BLUE};
        border-radius: 999px;
        padding: 0.3rem 1.1rem;
        margin-right: 0;
        background-color: #FFFFFF;
        cursor: pointer;
    }}
    /* Radio-Kreis ausblenden, nur der Text bleibt sichtbar */
    .st-key-nav label[data-testid="stRadioOption"] > div > div > div:first-child {{
        display: none;
    }}
    .st-key-nav label[data-testid="stRadioOption"] p {{
        font-family: 'Oswald', sans-serif !important;
        color: {BRAND_DARK_BLUE};
    }}
    .st-key-nav label[data-testid="stRadioOption"][data-selected="true"] {{
        background-color: {BRAND_DARK_BLUE};
        border-color: {BRAND_DARK_BLUE};
    }}
    .st-key-nav label[data-testid="stRadioOption"][data-selected="true"] p {{
        color: #FFFFFF !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Watchlisten werden als JSON-Datei im GitHub-Repo gespeichert (ueber die
# GitHub Contents API), damit sie geraeteuebergreifend erhalten bleiben.
# Dafuer muss in den Streamlit-Cloud-Secrets ein GITHUB_TOKEN mit
# Schreibrechten auf dieses Repo hinterlegt sein (siehe README).
GITHUB_REPO = "bauntay/financeresearch"
WATCHLIST_PATH = "streamlit_app/watchlists.json"


def _get_secret(key: str, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _github_headers():
    token = _get_secret("GITHUB_TOKEN")
    if not token:
        return None
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}


def _github_branch() -> str:
    return _get_secret("GITHUB_BRANCH", "main")


def load_watchlists() -> dict:
    headers = _github_headers()
    if not headers:
        return {}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{WATCHLIST_PATH}"
    try:
        resp = requests.get(url, headers=headers, params={"ref": _github_branch()}, timeout=10)
    except requests.exceptions.RequestException:
        return {}
    if resp.status_code == 200:
        try:
            raw = base64.b64decode(resp.json()["content"]).decode("utf-8")
            return json.loads(raw)
        except (KeyError, ValueError):
            return {}
    return {}


def save_watchlists(data: dict) -> tuple:
    headers = _github_headers()
    if not headers:
        return False, "Kein GITHUB_TOKEN in den Streamlit-Secrets hinterlegt (siehe README für die Einrichtung)."

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{WATCHLIST_PATH}"
    branch = _github_branch()
    try:
        get_resp = requests.get(url, headers=headers, params={"ref": branch}, timeout=10)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

        payload = {
            "message": "Update watchlists.json via Streamlit app",
            "content": base64.b64encode(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")).decode("utf-8"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        put_resp = requests.put(url, headers=headers, json=payload, timeout=10)
    except requests.exceptions.RequestException as exc:
        return False, f"Netzwerkfehler beim Speichern: {exc}"

    if put_resp.status_code in (200, 201):
        return True, "Watchlist gespeichert."
    return False, f"Fehler beim Speichern (HTTP {put_resp.status_code}): {put_resp.text[:200]}"

# Statische Ersatzliste fuer den S&P 500, falls Wikipedia nicht
# erreichbar ist. Kein Anspruch auf Vollstaendigkeit/Aktualitaet.
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
    "S&P 500": "sp500",
    "Nasdaq-100": "nasdaq100",
    "Euro Stoxx 50": "eurostoxx50",
}

# Waehrung anhand des Yahoo-Finance-Ticker-Suffixes schaetzen (kein
# Anspruch auf Vollstaendigkeit) - vermeidet einen zusaetzlichen API-Call
# pro Ticker beim Screening groesserer Listen.
SUFFIX_CURRENCY = {
    "DE": "EUR", "PA": "EUR", "AS": "EUR", "MI": "EUR", "MC": "EUR",
    "BR": "EUR", "LS": "EUR", "IR": "EUR", "VI": "EUR",
    "L": "GBP", "TO": "CAD", "V": "CAD", "SW": "CHF",
    "HK": "HKD", "T": "JPY", "AX": "AUD", "SA": "BRL",
}


def guess_currency(ticker: str) -> str:
    if "." in ticker:
        suffix = ticker.rsplit(".", 1)[-1].upper()
        return SUFFIX_CURRENCY.get(suffix, "USD")
    return "USD"


@st.cache_data(ttl=86400, show_spinner=False)
def get_currency(ticker: str) -> str:
    """Fragt die tatsaechliche Handelswaehrung bei Yahoo Finance ab (ein
    Ticker = ein Zusatz-Request, daher nur fuer den Einzelticker-Chart
    genutzt), mit Rueckfall auf die Suffix-Schaetzung."""
    try:
        fast_info = yf.Ticker(ticker).fast_info
        currency = fast_info.get("currency") if hasattr(fast_info, "get") else None
        if currency:
            return currency
    except Exception:
        pass
    return guess_currency(ticker)


def _read_wikipedia_tables(url: str) -> list:
    # Expliziter Abruf per requests: pd.read_html laedt URLs sonst ueber
    # urllib mit Standard-User-Agent, den Wikipedia teils blockiert.
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (FinanceDashboard)"}, timeout=20)
    resp.raise_for_status()
    return pd.read_html(StringIO(resp.text))


def _pick_column(df: pd.DataFrame, candidates: tuple) -> str:
    return next((c for c in candidates if c in df.columns), None)


@st.cache_data(ttl=86400, show_spinner=False)
def get_index_constituents(index_key: str) -> tuple:
    """Liest die Index-Zusammensetzung (Ticker + Firmenname) von Wikipedia.
    Gibt (DataFrame[Ticker, Name], quelle) zurueck; quelle ist "wikipedia"
    oder "fallback" wenn stattdessen die statische Ersatzliste greift."""
    urls = {
        "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "nasdaq100": "https://en.wikipedia.org/wiki/Nasdaq-100",
        "eurostoxx50": "https://en.wikipedia.org/wiki/EURO_STOXX_50",
    }
    try:
        tables = _read_wikipedia_tables(urls[index_key])
        df = next(
            t for t in tables
            if _pick_column(t, ("Symbol", "Ticker", "Ticker symbol")) and len(t) >= 20
        )
        ticker_col = _pick_column(df, ("Symbol", "Ticker", "Ticker symbol"))
        name_col = _pick_column(df, ("Security", "Company", "Company name", "Name"))

        out = pd.DataFrame({
            "Ticker": df[ticker_col].astype(str).str.strip().str.upper(),
            "Name": df[name_col].astype(str).str.strip() if name_col else "",
        })
        if index_key == "sp500":
            # Yahoo nutzt '-' statt '.' bei Aktienklassen (BRK.B -> BRK-B)
            out["Ticker"] = out["Ticker"].str.replace(".", "-", regex=False)
        out = out[out["Ticker"] != ""].drop_duplicates("Ticker").reset_index(drop=True)
        if out.empty:
            raise ValueError("Leere Ticker-Liste")
        return out, "wikipedia"
    except Exception:
        fallback = {
            "sp500": DEFAULT_UNIVERSE,
            "nasdaq100": NASDAQ100_FALLBACK,
            "eurostoxx50": EUROSTOXX50_FALLBACK,
        }[index_key]
        return pd.DataFrame({"Ticker": fallback, "Name": [""] * len(fallback)}), "fallback"


@st.cache_data(ttl=7 * 86400, show_spinner=False)
def get_ticker_name(ticker: str) -> str:
    """Firmenname zu einem Ticker (ein API-Call pro Ticker, 7 Tage gecacht).
    Nur fuer kleinere Universen wie Watchlisten gedacht."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ""
    except Exception:
        return ""


def parse_ticker_csv(uploaded_file) -> list:
    """Liest Ticker aus einer hochgeladenen CSV/TXT-Datei: pro Zeile zaehlt
    die erste Spalte (Komma, Semikolon oder Tab als Trenner), Header-Zeilen
    wie 'Ticker'/'Symbol' werden uebersprungen."""
    raw = uploaded_file.getvalue().decode("utf-8-sig", errors="ignore")
    tickers = []
    for line in raw.splitlines():
        first = line.replace(";", ",").replace("\t", ",").split(",")[0]
        first = first.strip().strip('"').strip("'").upper()
        if not first or first in ("TICKER", "SYMBOL", "TICKERS", "SYMBOLS", "NAME"):
            continue
        tickers.append(first)
    return list(dict.fromkeys(tickers))


@st.cache_data(ttl=900, show_spinner=False)
def load_price_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna(how="all")


@st.cache_data(ttl=900, show_spinner=False)
def load_universe_snapshot(tickers: tuple) -> tuple:
    """Laedt Tagesdaten fuer alle Ticker und berechnet die Kennzahlen.
    Gibt (DataFrame, uebersprungene_ticker) zurueck."""
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
    skipped = []
    for ticker in tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                df = raw[ticker].dropna(how="all")
            else:
                df = raw.dropna(how="all")
            if df.empty or len(df) < 60:
                skipped.append(ticker)
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
                "Währung": guess_currency(ticker),
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
            skipped.append(ticker)
            continue

    result = pd.DataFrame(rows)
    if not result.empty:
        # RS-Rang: Perzentil-Rang der Levy-RS ueber das gesamte geladene
        # Universum (1-99, aehnlich der IBD RS Rating), NaN bleibt NaN.
        result["RS-Rang"] = (result["Levy RS"].rank(pct=True) * 100).round(0)
    return result, tuple(skipped)


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


# Alle Screener-Filter an einer Stelle: Label -> Bedingung auf dem Snapshot.
FILTERS = {
    "Kurs über SMA20": lambda d: d["Kurs"] > d["SMA20"],
    "Kurs über SMA50": lambda d: d["Kurs"] > d["SMA50"],
    "Kurs über SMA200": lambda d: d["Kurs"] > d["SMA200"],
    "Golden Cross (SMA50 > SMA200)": lambda d: d["SMA50"] > d["SMA200"],
    "Death Cross (SMA50 < SMA200)": lambda d: d["SMA50"] < d["SMA200"],
    "RSI < 30 (überverkauft)": lambda d: d["RSI14"] < 30,
    "Positive 1-Monats-Performance": lambda d: d["1M %"] > 0,
    "Volumen-Ausbruch (>1.5x Ø)": lambda d: d["Vol-Ratio"] > 1.5,
    "Nahe 52W-Hoch (max. -10%)": lambda d: d["% vom 52W-Hoch"] >= -10,
}


st.title("📈 Finance Research Dashboard")

# Navigation als Radio statt st.tabs: st.tabs springt bei jeder Eingabe
# auf den ersten Tab zurueck, ein Radio mit key bleibt dagegen stabil.
PAGES = ("Kursdaten & Charts", "Watchlists & Screener")
page = st.radio("Bereich", PAGES, horizontal=True, key="nav", label_visibility="collapsed")

if page == PAGES[0]:
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
            currency = get_currency(ticker)
            df["SMA20"] = df["Close"].rolling(20).mean()
            df["SMA50"] = df["Close"].rolling(50).mean()
            df["RSI14"] = compute_rsi(df["Close"])

            latest = df.iloc[-1]
            prev_close = df["Close"].iloc[-2] if len(df) > 1 else latest["Close"]
            change_pct = (latest["Close"] / prev_close - 1) * 100

            m1, m2, m3 = st.columns(3)
            m1.metric("Letzter Kurs", f"{latest['Close']:.2f} {currency}", f"{change_pct:.2f}%")
            m2.metric("SMA20", f"{latest['SMA20']:.2f} {currency}" if pd.notna(latest["SMA20"]) else "–")
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
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], name="SMA20", line=dict(width=1.5, color=BRAND_DARK_BLUE)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], name="SMA50", line=dict(width=1.5, color=BRAND_LIGHT_BLUE)), row=1, col=1)
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volumen", marker_color=BRAND_LIGHT_BLUE), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI14"], name="RSI14", line=dict(color=BRAND_DARK_BLUE)), row=3, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

            fig.update_layout(
                height=800, xaxis_rangeslider_visible=False, showlegend=True,
                font=dict(family="Overpass, sans-serif", color=BRAND_DARK_BLUE),
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Rohdaten anzeigen"):
                st.dataframe(df.tail(200), use_container_width=True)

else:
    watchlists = load_watchlists()
    token_ok = _github_headers() is not None

    universe: tuple = ()
    provided_names: dict = {}
    heading = ""
    NEW_WL = "➕ Neue Watchlist anlegen"

    source = st.radio("Quelle", ["Meine Watchlists", "Index-Screening"], horizontal=True)

    if source == "Meine Watchlists":
        options = sorted(watchlists.keys()) + [NEW_WL]
        choice = st.selectbox("Watchlist", options, key="wl_select")

        if choice == NEW_WL:
            if not token_ok:
                st.warning("Zum Speichern muss ein gültiger `GITHUB_TOKEN` in den Streamlit-Secrets hinterlegt sein (siehe README).")
            with st.form("wl_create"):
                new_name = st.text_input("Name der Watchlist")
                new_tickers = st.text_input("Ticker (kommagetrennt, z.B. AAPL, SAP.DE, MC.PA)")
                csv_file = st.file_uploader("…oder Ticker aus CSV importieren (erste Spalte = Ticker)", type=["csv", "txt"])
                submitted = st.form_submit_button("Watchlist anlegen")
            if submitted:
                tickers = parse_ticker_csv(csv_file) if csv_file is not None else [
                    t.strip().upper() for t in new_tickers.split(",") if t.strip()
                ]
                if not new_name.strip():
                    st.error("Bitte einen Namen angeben.")
                elif not tickers:
                    st.error("Keine Ticker gefunden – Feld ausfüllen oder CSV hochladen.")
                else:
                    watchlists[new_name.strip()] = tickers
                    ok, msg = save_watchlists(watchlists)
                    if ok:
                        st.session_state["wl_select"] = new_name.strip()
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            universe = tuple(watchlists.get(choice, []))
            heading = choice

            with st.expander(f"„{choice}“ bearbeiten ({len(universe)} Titel)"):
                add_col, rem_col = st.columns(2)
                add_text = add_col.text_input("Ticker hinzufügen (kommagetrennt)", key=f"add_{choice}")
                if add_col.button("Hinzufügen", key=f"add_btn_{choice}"):
                    new = [t.strip().upper() for t in add_text.split(",") if t.strip()]
                    if new:
                        watchlists[choice] = list(dict.fromkeys(list(universe) + new))
                        ok, msg = save_watchlists(watchlists)
                        if ok:
                            st.rerun()
                        else:
                            st.error(msg)
                to_remove = rem_col.multiselect("Ticker entfernen", list(universe), key=f"rem_{choice}")
                if rem_col.button("Entfernen", key=f"rem_btn_{choice}") and to_remove:
                    watchlists[choice] = [t for t in universe if t not in to_remove]
                    ok, msg = save_watchlists(watchlists)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)
                if st.button("Watchlist löschen", key=f"del_{choice}"):
                    watchlists.pop(choice, None)
                    ok, msg = save_watchlists(watchlists)
                    if ok:
                        st.session_state.pop("wl_select", None)
                        st.rerun()
                    else:
                        st.error(msg)

            if not universe:
                st.info("Diese Watchlist ist leer – füge über „bearbeiten“ Ticker hinzu.")
    else:
        idx_label = st.selectbox("Index", list(INDEX_OPTIONS.keys()))
        with st.spinner(f"Lade Zusammensetzung {idx_label}…"):
            constituents, idx_source = get_index_constituents(INDEX_OPTIONS[idx_label])
        if idx_source == "fallback":
            st.warning(f"Live-Liste von Wikipedia nicht erreichbar – verwende statische Ersatzliste ({len(constituents)} Titel).")
        universe = tuple(constituents["Ticker"])
        provided_names = dict(zip(constituents["Ticker"], constituents["Name"]))
        heading = idx_label

    if universe:
        fcol1, fcol2 = st.columns([3, 1])
        active_filters = fcol1.multiselect(
            "Filter", list(FILTERS.keys()),
            placeholder="Keine Filter aktiv – alle Titel werden angezeigt",
        )
        min_rs_rank = fcol2.slider(
            "Min. RS-Rang (Levy)", 0, 99, 0,
            help="Perzentil-Rang der Relativen Stärke nach Levy über das gewählte Universum. 0 = aus.",
        )

        with st.spinner(f"Lade Kursdaten für {len(universe)} Titel…"):
            snapshot, skipped = load_universe_snapshot(universe)

        if snapshot.empty:
            st.error("Keine Kursdaten gefunden – bitte Ticker prüfen.")
        else:
            # Firmennamen: aus der Index-Liste, sonst (nur bei kleinen
            # Universen) einzeln von Yahoo nachladen.
            names = dict(provided_names)
            if not any(names.values()) and len(universe) <= 60:
                with st.spinner("Lade Firmennamen…"):
                    names = {t: get_ticker_name(t) for t in snapshot["Ticker"]}
            snapshot.insert(1, "Name", snapshot["Ticker"].map(names).fillna(""))

            result = snapshot
            for label in active_filters:
                result = result[FILTERS[label](result)]
            if min_rs_rank > 0:
                result = result[result["RS-Rang"] >= min_rs_rank]

            st.markdown(f"**{heading}: {len(result)} von {len(snapshot)} Titeln**")
            st.caption("🟢 Kurs über dem gleitenden Durchschnitt · 🔴 darunter (SMA20/50/200)")
            st.dataframe(
                style_sma_columns(result.sort_values("RS-Rang", ascending=False)),
                use_container_width=True, hide_index=True,
                height=min(620, 42 + 36 * max(len(result), 1)),
            )
            if skipped:
                st.caption(f"⚠️ Keine oder zu wenige Kursdaten für: {', '.join(skipped)}")

st.caption("Daten von Yahoo Finance über yfinance. Nur zu Informationszwecken, keine Anlageberatung.")
