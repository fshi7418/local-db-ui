import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/books")

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H2("Books"),
                width=12,
            ),
            className="mb-4"
        ),
        dbc.Row(
            dbc.Col(
                html.P("Books page coming soon..."),
                width=12,
            )
        ),
    ],
    fluid=True,
)
