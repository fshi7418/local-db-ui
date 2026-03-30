# local-db-ui

A Dash-based web UI for the `local-db` backend.

## Setup

1. **Activate the virtual environment:**
   ```bash
   source ~/Environments/local-db-ui/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app:**
   ```bash
   python app.py
   ```

   Then open `http://localhost:8050` in your browser.

## Structure

- `app.py` — main Dash app with multi-page routing
- `pages/` — individual page modules (transactions, books, firearms, archery)
- `components/` — reusable Dash components (tables, forms, etc.)
- `.env` — environment configuration (PYTHONPATH, DB credentials)

## Pages

- **Transactions** — add expenses, view recent transactions
- **Books** — add books, authors, publishers, series (coming soon)
- **Firearms** — add firearms, manufacturers, models, sights (coming soon)
- **Archery** — add archery sessions (coming soon)

## Architecture

The app imports directly from the `local-db` backend:
- Models from `models/`
- Business logic from `script_modules/`
- Utilities from `utilities.py`

PYTHONPATH is configured in `.env` to point to `/home/franks/Repos/local-db`.
