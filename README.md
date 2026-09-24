# Macroeconomic Fragility Barometer

> Prefer a visual guide? Open [README.html](README.html) in a browser.

Local Streamlit dashboard for an early-warning **Composite Macro Fragility Index**. It combines energy/physical-flow pressure, credit and rates, market breadth, and a local Ollama geopolitical-news heuristic. It is an analytical aid, not investment advice.

## Setup

Requires Python 3.11+ and (only for geopolitical scoring) a running local Ollama instance with `batiai/qwen3.6-35b:iq4` available.

```cmd
cd C:\Barometer\macro_barometer
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
```

### Configure `.env` and API keys

`.env.example` is a safe template; it does **not** contain working keys. Create your own `.env` file beside it, then edit the copy—not the example file:

```cmd
copy .env.example .env
notepad .env
```

Enter your keys after the equals signs, with no quotes or extra spaces:

```ini
FRED_API_KEY=paste_your_fred_key_here
EIA_API_KEY=paste_your_eia_key_here
OLLAMA_HOST=http://localhost:11434
```

Save the file, then restart the dashboard or run a new `python main.py --refresh` command. `.env` is ignored by Git, so it is not included in source control; do not paste its contents into issues, chat, or screenshots.

#### Get a FRED key (credit, yields, and financial-stress data)

1. Create or sign in to a free [FRED account](https://fredaccount.stlouisfed.org/).
2. Open the [FRED API key page](https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html) while signed in and request an API key for this application.
3. Copy the generated key into `FRED_API_KEY=` in `.env`, then save.

FRED requires an account before you can request or view keys and recommends a separate key per application. [FRED API key guidance](https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html)

#### Get an EIA key (weekly distillate and SPR inventory data)

1. Complete the free [EIA Open Data API registration form](https://www.eia.gov/opendata/register.php).
2. EIA emails the key to the address supplied; check spam or allow-list `developer@eia.gov` if it does not arrive.
3. Copy the key into `EIA_API_KEY=` in `.env`, then save.

EIA requires an API key for its API and sends it to the registration email address. [EIA registration](https://www.eia.gov/opendata/register.php), [EIA API documentation](https://www.eia.gov/opendata/documentation.php)

Both keys are optional: without them, the dashboard keeps running with cached data and visibly reports the fallback. Market data uses Yahoo Finance without a key. The Ollama host and model are set in `config.yaml`.

The included `.streamlit/config.toml` turns off Streamlit usage telemetry for this project. On the first ever Streamlit launch, its optional email prompt is normal; leaving it blank and pressing Enter is sufficient.

## Run

Double-click `launch_barometer.bat` in `C:\AI\Codex\Barometer` to start the dashboard. Keep its command window open while using the app; closing it stops the local server.

Fetch live data once, then start the dashboard:

```cmd
python main.py --refresh
python -m streamlit run app.py
```

### Explore safely with built-in demo data

For a fully offline visual smoke test, write deterministic sample data first:

```cmd
python main.py --seed-demo
python -m streamlit run app.py
```

> **⚠️ Warning:** Do not mix demo data with live data. The demo script writes mock values that use different scales than real-world APIs. If you fetch live data into a demo database, the math engine interprets the scale discrepancies as a catastrophic market crash, resulting in a false 100/100 "Red" score.
> **To switch from demo mode to live mode, you must delete the database first:**
> `del data\macro_data.db`

### Scheduling

To run the background collector every hour:

```cmd
python main.py --watch 3600
```

For Windows Task Scheduler, schedule `C:\Barometer\refresh_barometer.bat` daily. It collects the sources, records or updates that day's composite score, and exits. The dashboard's **Macro Fragility Trend** chart reads these daily snapshots. The open dashboard also has a selectable cache-refresh interval (default: one day); enable **Also refresh live sources** only if you want the open dashboard itself to perform the potentially slow data and Ollama run.

## Design notes

- Data is stored in `data/macro_data.db`; repeated fetches upsert daily observations.
- Composite snapshots are stored once per day in the same database, which creates the Macro Fragility Trend chart over time.
- Quantitative measures use a direction-aware, winsorized rolling 252-observation min-max transformation. Higher score always means greater fragility.
- Available pillar weights are rebalanced when a data source is unavailable; the dashboard shows data coverage instead of silently treating absent data as low risk.
- Ollama headline analysis uses **Chain-of-Thought reasoning** against a strict 1-5 rubric to eliminate LLM hallucinations. It allows five minutes per request, validates strict Pydantic JSON, retries once on a malformed/failed response, then records a neutral `50` fallback with its status. Change `ollama.timeout_seconds` in `config.yaml` if your hardware needs a different allowance.

## Verification

```powershell
pytest -q
python -m compileall .
```

## Troubleshooting

### Dashboard is stuck at 100 or "Red Regime" / Charts look erratic
If your charts show wild "sawtooth" patterns or your composite score is artificially pegged near 100.0, you likely mixed demo data with live data. 
**Fix:** Stop the dashboard, delete the contaminated database by running `del data\macro_data.db`, and run a clean `python main.py --refresh`. Do not run `--seed-demo` again.


