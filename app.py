import os
import sys
from dotenv import load_dotenv
import dash
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

# Load environment variables
load_dotenv()

# Ensure local-db is in PYTHONPATH and set correct working directory
local_db_path = os.getenv("PYTHONPATH", "/home/franks/Repos/local-db").split(":")[0]
if local_db_path not in sys.path:
    sys.path.insert(0, local_db_path)

# Change to local-db directory for configs.json to be found
# os.chdir(local_db_path)

# Initialize Dash app
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    pages_folder="pages",
    use_pages=True
)

# Define app layout
app.layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1("Local DB - Web UI", className="mb-4 mt-4"),
                width=12,
            )
        ),
        dbc.Row(
            dbc.Col(
                dbc.Nav(
                    [
                        dbc.NavLink("Transactions", href="/transactions", active="exact"),
                        dbc.NavLink("Budget", href="/budget", active="exact"),
                        dbc.NavLink("Books", href="/books", active="exact"),
                        dbc.NavLink("Archery", href="/archery", active="exact"),
                        dbc.NavLink("Archery Data", href="/archery-data", active="exact"),
                        dbc.NavLink("Firearms", href="/firearms", active="exact"),
                        dbc.NavLink("Firearm Data", href="/firearm-data", active="exact"),
                        dbc.NavLink("Trap", href="/trap", active="exact"),
                        dbc.NavLink("Double Trap", href="/double-trap", active="exact"),
                        dbc.NavLink("Skeet", href="/skeet", active="exact"),
                        dbc.NavLink("Skeet Shot Backfill", href="/skeet-shot-backfill", active="exact"),
                    ],
                ),
                width=12,
            )
        ),
        html.Hr(),
        dcc.Location(id="url", refresh=False),
        dash.page_container,
    ],
    fluid=True,
)

if __name__ == "__main__":
    app.run_server(debug=False, host='0.0.0.0', port=8050)
