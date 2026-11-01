"""Heading and tab bar shared by the clay shooting pages."""
from dash import html
import dash_bootstrap_components as dbc

TABS = [
    ("Trap", "/clayshooting/trap"),
    ("Double Trap", "/clayshooting/double-trap"),
    ("Skeet", "/clayshooting/skeet"),
]


def clayshooting_header():
    return html.Div(
        [
            html.H2("Clayshooting", className="mb-3"),
            dbc.Nav(
                [dbc.NavLink(label, href=href, active="exact") for label, href in TABS],
                class_name="nav-tabs",
            ),
        ],
        className="mb-4",
    )
