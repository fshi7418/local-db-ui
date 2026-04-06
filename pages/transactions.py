import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from datetime import datetime
import sys

# Import from local-db backend
from models import postgres_session
from models.transactions import ExpenseTransactions, ExpenseBudget
from transaction_configs import ExpenseCat, ExpenseSource
from script_modules.add_transaction import add_expense

dash.register_page(__name__, path="/transactions")

# Helper: get list of valid categories
def get_categories():
    """Return list of (display_name, enum_name) tuples"""
    return [(cat.value, cat.name) for cat in ExpenseCat]

# Helper: get list of valid sources
def get_sources():
    """Return list of (display_name, enum_name) tuples"""
    return [(src.value, src.name) for src in ExpenseSource]

# Helper: get active budgets for a given year
def get_active_budgets(year):
    try:
        from models import Session
        session = Session()

        budgets = session.query(ExpenseBudget).filter(
            ExpenseBudget.budget_start_date >= datetime(year, 1, 1),
            ExpenseBudget.budget_end_date <= datetime(year, 12, 31)
        ).all()
        result = [{"label": f"{b.category} ({b.subcategory})", "value": b.id} for b in budgets]
        session.close()
        return result
    except Exception as e:
        print(f"Error querying budgets: {e}")
        return []

# Helper: query all transactions for chart, grouped by month and category
def build_spending_chart():
    try:
        from models import Session
        session = Session()
        rows = session.query(ExpenseTransactions).all()
        data = [
            {"Date": row.transaction_date, "Amount": row.amount, "Category": row.category}
            for row in rows
        ]
        session.close()
        if not data:
            return px.line(title="Spending by Category Over Time")
        df = pd.DataFrame(data)
        df["Month"] = pd.to_datetime(df["Date"]).dt.to_period("M").dt.to_timestamp()
        df = df.groupby(["Month", "Category"], as_index=False)["Amount"].sum()
        return px.line(df, x="Month", y="Amount", color="Category", title="Spending by Category Over Time")
    except Exception as e:
        print(f"Error building chart: {e}")
        return px.line(title="Spending by Category Over Time")


# Helper: query recent N transactions
def get_recent_transactions(n=40):
    try:
        # Use local session instance to avoid issues with closed sessions
        from models import Session
        session = Session()

        rows = session.query(ExpenseTransactions).order_by(
            ExpenseTransactions.transaction_date.desc()
        ).limit(n).all()

        data = []
        for row in rows:
            data.append({
                "ID": row.id,
                "Date": row.transaction_date.strftime("%Y-%m-%d"),
                "Amount": f"${row.amount:.2f}",
                "Category": row.category,
                "Source": row.expense_source,
                "Comment": row.expense_comment or "",
            })
        session.close()
        return data
    except Exception as e:
        print(f"Error querying transactions: {e}")
        return []

# Layout
layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H2("Transactions"),
                width=12,
            ),
            className="mb-4"
        ),

        # Input Form
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H4("Add New Transaction", className="card-title"),

                        # Date selection
                        dbc.Row([
                            dbc.Col([
                                html.Label("Is this today?"),
                                dbc.RadioItems(
                                    id="trans-is-today",
                                    options=[
                                        {"label": " Yes", "value": True},
                                        {"label": " No", "value": False},
                                    ],
                                    value=True,
                                    inline=True,
                                ),
                            ], md=6),
                            dbc.Col([
                                html.Label("Date (if not today)"),
                                dcc.DatePickerSingle(
                                    id="trans-date",
                                    date=datetime.now().date(),
                                    disabled=True,
                                ),
                            ], md=6),
                        ], className="mb-3"),

                        # Amount
                        dbc.Row(
                            dbc.Col([
                                html.Label("Amount"),
                                dbc.Input(
                                    id="trans-amount",
                                    type="number",
                                    placeholder="10.50",
                                    step=0.01,
                                ),
                            ], md=6),
                            className="mb-3",
                        ),

                        # Category and Source
                        dbc.Row([
                            dbc.Col([
                                html.Label("Category"),
                                dcc.Dropdown(
                                    id="trans-category",
                                    options=[{"label": display, "value": enum_name} for display, enum_name in get_categories()],
                                    placeholder="Select category",
                                ),
                            ], md=6),
                            dbc.Col([
                                html.Label("Source"),
                                dcc.Dropdown(
                                    id="trans-source",
                                    options=[{"label": display, "value": enum_name} for display, enum_name in get_sources()],
                                    placeholder="Select source",
                                ),
                            ], md=6),
                        ], className="mb-3"),

                        # Budget
                        dbc.Row(
                            dbc.Col([
                                html.Label("Budget (optional)"),
                                dcc.Dropdown(
                                    id="trans-budget",
                                    placeholder="Select budget",
                                ),
                            ], md=6),
                            className="mb-3",
                        ),

                        # Comment
                        dbc.Row(
                            dbc.Col([
                                html.Label("Comment"),
                                dbc.Textarea(
                                    id="trans-comment",
                                    placeholder="Optional comment",
                                    style={"height": "80px"},
                                ),
                            ], md=12),
                            className="mb-3",
                        ),

                        # Submit button
                        dbc.Row(
                            dbc.Col([
                                dbc.Button(
                                    "Add Transaction",
                                    id="trans-submit",
                                    color="primary",
                                    size="lg",
                                    className="w-100",
                                ),
                            ], md=12),
                        ),
                    ]),
                    className="mb-4",
                ),
                width=12,
            ),
        ),

        # Alert for feedback
        dbc.Row(
            dbc.Col(
                html.Div(id="trans-alert"),
                width=12,
            ),
            className="mb-3",
        ),

        # Spending chart
        dbc.Row(
            dbc.Col(
                dcc.Graph(id="trans-chart", figure=build_spending_chart()),
                width=12,
            ),
            className="mb-4",
        ),

        # Recent transactions table
        dbc.Row(
            dbc.Col([
                html.H4("Recent Transactions"),
                dbc.Spinner(
                    html.Div(
                        id="trans-table",
                        children=dbc.Table.from_dataframe(
                            pd.DataFrame(get_recent_transactions(40)),
                            striped=True,
                            bordered=True,
                            hover=True,
                            size="sm",
                        ),
                    ),
                ),
            ], width=12),
        ),
    ],
    fluid=True,
)

# Callback: toggle date picker based on "is today" radio
@callback(
    Output("trans-date", "disabled"),
    Input("trans-is-today", "value"),
)
def toggle_date_picker(is_today):
    return is_today

# Callback: populate budgets when date changes
@callback(
    Output("trans-budget", "options"),
    Input("trans-date", "date"),
)
def populate_budgets(date_str):
    if date_str:
        year = datetime.fromisoformat(date_str).year
        return get_active_budgets(year)
    return []

# Callback: submit transaction
@callback(
    Output("trans-alert", "children"),
    Output("trans-table", "children"),
    Output("trans-chart", "figure"),
    Output("trans-amount", "value"),
    Output("trans-category", "value"),
    Output("trans-source", "value"),
    Output("trans-budget", "value"),
    Output("trans-comment", "value"),
    Input("trans-submit", "n_clicks"),
    [
        State("trans-is-today", "value"),
        State("trans-date", "date"),
        State("trans-amount", "value"),
        State("trans-category", "value"),
        State("trans-source", "value"),
        State("trans-budget", "value"),
        State("trans-comment", "value"),
    ],
    prevent_initial_call=True,
)
def submit_transaction(n_clicks, is_today, date_str, amount, category, source, budget_id, comment):
    try:
        # Determine date
        if is_today:
            date = datetime.now().date()
        else:
            date = datetime.fromisoformat(date_str).date()

        # Validate
        if not amount or amount <= 0:
            raise ValueError("Amount must be positive")
        if not category:
            raise ValueError("Category is required")
        if not source:
            raise ValueError("Source is required")

        # Insert
        add_expense(
            e_date=date,
            e_amount=float(amount),
            e_category_str=category,
            e_source_str=source,
            e_comment=comment or "",
            e_budget_id=budget_id or "",
        )

        # Refresh table
        table_data = get_recent_transactions(10)
        table = dbc.Table.from_dataframe(
            pd.DataFrame(table_data),
            striped=True,
            bordered=True,
            hover=True,
            size="sm",
        )

        alert = dbc.Alert("Transaction added successfully!", color="success", dismissable=True)

        # Clear form
        return alert, table, build_spending_chart(), None, None, None, None, ""

    except Exception as e:
        alert = dbc.Alert(f"Error: {str(e)}", color="danger", dismissable=True)
        # Return current table (no change)
        table_data = get_recent_transactions(10)
        table = dbc.Table.from_dataframe(
            pd.DataFrame(table_data),
            striped=True,
            bordered=True,
            hover=True,
            size="sm",
        )
        return alert, table, build_spending_chart(), amount, category, source, budget_id, comment
