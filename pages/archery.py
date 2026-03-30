import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/archery")

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H2("Archery"),
                width=12,
            ),
            className="mb-4"
        ),
        dbc.Row(
            dbc.Col(
                html.P("Archery page coming soon..."),
                width=12,
            )
        ),
    ],
    fluid=True,
)
