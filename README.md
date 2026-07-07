# Finance Research Dashboard

Web-Dashboard für Kursdaten/Charts und einen einfachen Stock-Screener, basierend auf
Ideen aus der [Finance](https://github.com/shashankvemuri/Finance)-Sammlung
(`Finance-master.zip`), neu implementiert mit [Streamlit](https://streamlit.io) und
[yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance, kein API-Key nötig).

## App

Der Code liegt in [`streamlit_app/app.py`](streamlit_app/app.py) und hat zwei Bereiche:

- **Kursdaten & Charts**: Ticker eingeben, Candlestick-Chart mit SMA20/SMA50, Volumen
  und RSI(14).
- **Watchlists & Screener**: Watchlists anlegen (manuell oder per CSV-Import,
  erste Spalte = Ticker), ansehen, bearbeiten (Ticker hinzufügen/entfernen) und
  nach technischen Kriterien filtern – oder alternativ einen ganzen Index
  screenen (S&P 500, Nasdaq-100, Euro Stoxx 50, live von Wikipedia geladen).
  Die Tabelle zeigt Firmennamen und Währung, Filter (SMA20/50/200, Golden/Death
  Cross, RSI, Levy-RS-Rang, Performance, Volumen, 52W-Hoch) werden über eine
  kompakte Mehrfachauswahl kombiniert. SMA-Spalten sind farblich markiert
  (grün = Kurs über dem jeweiligen SMA, rot = darunter).

## Watchlisten dauerhaft speichern (GitHub-Token einrichten)

Watchlisten werden als `streamlit_app/watchlists.json` im Repo gespeichert, damit sie
geräteübergreifend erhalten bleiben. Dafür braucht die App Schreibzugriff auf das
Repo über ein GitHub Personal Access Token:

1. Auf GitHub unter **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens** ein neues Token erstellen, das nur auf dieses Repo
   (`bauntay/financeresearch`) beschränkt ist, mit der Berechtigung
   **Contents: Read and write**.
2. In der Streamlit-Cloud-App unter **Settings → Secrets** Folgendes eintragen:
   ```toml
   GITHUB_TOKEN = "dein_token_hier"
   GITHUB_BRANCH = "main"  # optional, Standard ist "main"
   ```
3. Speichern – die App liest den Token automatisch über `st.secrets`. Ohne
   Token kann die App die Watchlisten weiterhin anzeigen, aber nicht neu
   speichern oder löschen.

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
