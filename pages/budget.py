import dash
from dash import dcc, html, callback, Input, Output
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

from models import Session

dash.register_page(__name__, path="/budget")

VALID_YEARS = [2025, 2026]

BUDGET_QUERY = text("""
    SELECT
        b.budget_start_date,
        b.budget_end_date,
        b.income_expense,
        b.category,
        b.subcategory,
        b.frequency * b.amount AS budget_total,
        CASE WHEN b.income_expense = 'expense'
             THEN -1 * COALESCE(SUM(t.amount), 0)
             ELSE COALESCE(SUM(t.amount), 0)
        END AS amount_so_far
    FROM expense_budget b
    LEFT JOIN expense_transactions t
        ON t.expense_budget_id = b.id
    WHERE b.budget_start_date = :start_date
      AND b.budget_end_date = :end_date
    GROUP BY b.id
    ORDER BY b.category, b.subcategory
""")


def get_budget_data(year):
    try:
        session = Session()
        result = session.execute(
            BUDGET_QUERY,
            {"start_date": f"{year}-01-01", "end_date": f"{year}-12-31"},
        )
        rows = result.fetchall()
        columns = result.keys()
        session.close()
        return pd.DataFrame(rows, columns=columns)
    except Exception as e:
        print(f"Error querying budget: {e}")
        return pd.DataFrame()


layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H2("Budget"), width=12),
            className="mb-4",
        ),
        dbc.Row(
            dbc.Col(
                [
                    html.Label("Year"),
                    dcc.Dropdown(
                        id="budget-year",
                        options=[{"label": str(y), "value": y} for y in VALID_YEARS],
                        value=2026,
                        clearable=False,
                        style={"width": "200px"},
                    ),
                ],
                width=12,
            ),
            className="mb-4",
        ),
        dbc.Row(
            dbc.Col(
                dbc.Spinner(html.Div(id="budget-table")),
                width=12,
            ),
        ),
    ],
    fluid=True,
)


@callback(
    Output("budget-table", "children"),
    Input("budget-year", "value"),
)
def update_budget_table(year):
    if year is None:
        return html.P("Select a year.", className="text-muted")

    df = get_budget_data(year)
    if df.empty:
        return html.P("No budget data found for this year.", className="text-muted")

    df["budget_start_date"] = pd.to_datetime(df["budget_start_date"]).dt.strftime("%Y-%m-%d")
    df["budget_end_date"] = pd.to_datetime(df["budget_end_date"]).dt.strftime("%Y-%m-%d")

    columns = [
        {"name": "Start Date", "id": "budget_start_date", "type": "text"},
        {"name": "End Date", "id": "budget_end_date", "type": "text"},
        {"name": "Type", "id": "income_expense", "type": "text"},
        {"name": "Category", "id": "category", "type": "text"},
        {"name": "Subcategory", "id": "subcategory", "type": "text"},
        {"name": "Budget Total", "id": "budget_total", "type": "numeric", "format": {"specifier": "$.2f"}},
        {"name": "Amount So Far", "id": "amount_so_far", "type": "numeric", "format": {"specifier": "$.2f"}},
    ]

    return DataTable(
        columns=columns,
        data=df.to_dict("records"),
        sort_action="native",
        style_cell={"textAlign": "left", "padding": "10px"},
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"},
        ],
    )
