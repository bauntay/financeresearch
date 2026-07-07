# Finance Research Dashboard

Web-Dashboard für Kursdaten/Charts und einen einfachen Stock-Screener, basierend auf
Ideen aus der [Finance](https://github.com/shashankvemuri/Finance)-Sammlung
(`Finance-master.zip`), neu implementiert mit [Streamlit](https://streamlit.io) und
[yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance, kein API-Key nötig).

## App

Der Code liegt in [`streamlit_app/app.py`](streamlit_app/app.py) und hat zwei Bereiche:

- **Kursdaten & Charts**: Ticker eingeben, Candlestick-Chart mit SMA20/SMA50, Volumen
  und RSI(14).
- **Stock-Screener**: filtert eine Liste von Aktien (Standardliste oder eigene
  Ticker) nach einfachen Kriterien (über SMA50/SMA200, RSI < 30, nahe am
  52-Wochen-Hoch).

## Online nutzen (kein eigener Server nötig)

Die App läuft kostenlos über **Streamlit Community Cloud** – du brauchst dafür
keine Installation, nur einen Browser:

1. Auf [share.streamlit.io](https://share.streamlit.io) mit dem GitHub-Account
   anmelden.
2. "New app" → dieses Repository und den Branch
   `claude/stock-data-html-solution-8d5imz` auswählen.
3. Als "Main file path" `streamlit_app/app.py` angeben.
4. Deploy klicken – danach ist die App dauerhaft unter einem Link wie
   `https://<app-name>.streamlit.app` erreichbar.

## Lokal ausführen (optional)

```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```
