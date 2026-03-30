import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/")

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H2("Welcome"),
                width=12,
            ),
            className="mb-4"
        ),
        dbc.Row(
            dbc.Col(
                html.P("Select a page from the navigation bar above."),
                width=12,
            )
        ),
    ],
    fluid=True,
)
