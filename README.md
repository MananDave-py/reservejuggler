# MoneyMaxxer

MoneyMaxxer is an educational treasury dashboard. It forecasts hourly withdrawals from a CSV, suggests how to divide available cash across four reserve tiers, keeps per-user allocation history, and can ask Gemini to explain the trade-offs.

> **For evaluation and learning only.** The included data is synthetic; allocations are illustrative and are not financial advice.

## Try the demo

The app starts with empty portfolios. To see a real calculation, sign in with a demo account and upload the included CSV yourself.

- **Demo username:** `alex`
- **Demo password:** `alex123`
- **Sample CSV:** [`data/treasury_4tier_dataset_2027.csv`](data/treasury_4tier_dataset_2027.csv) — 8,760 unique hourly rows covering Jan 1–Dec 31, 2027.

After opening the app, sign in, choose **Upload CSV**, select the sample file, and click **Run**. You can also create your own account; new accounts start with no uploads or sample portfolio data. Market news is optional: without a Marketaux key, the app continues with neutral news points. The Gemini portfolio explanation is optional and requires a Gemini API key.

## Fastest start: Windows portable app

Download **MoneyMaxxer-Standalone.exe** from the repository's [GitHub Releases](https://github.com/MananDave-py/reservejuggler/releases) and run it directly, or download and unzip **MoneyMaxxer-Windows.zip** and run `MoneyMaxxer.exe`. The standalone executable bundles the app into one file; the ZIP starts faster and keeps the bundled runtime and app files together. Both versions open the local landing page in your browser and store the local database under `%LOCALAPPDATA%\MoneyMaxxer`.

Both Windows downloads include Python and the required packages, so they do not require a separate Python installation or dependency download. Windows may show a SmartScreen prompt for an unsigned demo executable. The app listens only on your own computer at `http://127.0.0.1:8000/`; if that port is already occupied, it picks an available local port and opens it for you.

## Run with Docker

Docker Desktop is required for this option. From the project folder run:

```powershell
docker compose up --build
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). The Compose setup builds the container, applies database migrations, prepares static files, and creates the demo accounts. Uploaded allocation history persists in the `moneymaxxer-data` volume. Stop the app with `Ctrl+C`; use `docker compose down` to stop and remove the container while preserving that volume.

## Publish a judge-facing web link

The [`render.yaml`](render.yaml) Blueprint configures a Render Docker web service and PostgreSQL database. Connect this private GitHub repository to Render, choose **New Blueprint**, and review its resources before applying them. Render generates the Django secret and connects the database. The demo accounts are seeded so judges can sign in and upload the sample CSV.

The Blueprint uses Render's free plans to avoid creating paid resources without your approval. Free web services can spin down when idle, and free PostgreSQL has a limited lifetime. Check Render's current limits before relying on it for a longer-term public demo; a paid always-on service and database are more dependable. The repository owner must grant Render access because this GitHub repository is private.

The demo accounts share one database, so their upload histories are shared. Judges can register separate accounts for isolated histories. Never add API keys to the repo or commit `.env`; set provider keys as hosting secrets or enter them in the app.

## Run from source

Python 3.12 or newer is recommended.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_dummy_users
python manage.py runserver
```

Then open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). On macOS or Linux, create/activate a virtual environment with the installed Python and run the same pip and Django commands.

## Optional API keys

Copy `.env.example` to `.env` in the project folder and replace the placeholders:

```dotenv
MARKETAUX_API_TOKEN=your_marketaux_token
GEMINI_API_KEY=your_gemini_key
```

Compose passes `.env` to the container. The Windows portable app reads an optional `.env` placed beside `MoneyMaxxer.exe`. Never commit real keys. The core forecast and allocation work without either key; live news and Gemini explanations require their respective credentials and network access.

## What the CSV contains

The included file is synthetic hourly treasury data. It has timestamps, deposits, withdrawals, net cash flow, repo-window flags, repo rates, government-bond yield/price/duration, equity index/volatility, and example liquidation haircuts. It contains no personal or real customer data. Uploads are validated for the required columns and hourly timestamps.

## Windows bundle build

On Windows with Python 3.12+:

```powershell
python -m pip install -r requirements.txt pyinstaller
./build_windows.ps1
```

The distributable ZIP and standalone executable are written to `dist/MoneyMaxxer-Windows.zip` and `dist/MoneyMaxxer-Standalone.exe`. They include the runnable app and demo CSV.

## Project notes

- Django authentication keeps uploads and allocation history scoped to the signed-in user.
- Registration creates an account but asks the user to sign in afterward.
- Local user data is stored in SQLite. Docker persists it in a named volume; the portable app uses the current Windows user's Local AppData. The Render deployment uses PostgreSQL.
- Local development and the Windows bundle use Django's development server. Docker deployments use Gunicorn with production security settings.
