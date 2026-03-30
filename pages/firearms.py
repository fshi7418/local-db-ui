import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/firearms")

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H2("Firearms"),
                width=12,
            ),
            className="mb-4"
        ),
        dbc.Row(
            dbc.Col(
                html.P("Firearms page coming soon..."),
                width=12,
            )
        ),
    ],
    fluid=True,
)
