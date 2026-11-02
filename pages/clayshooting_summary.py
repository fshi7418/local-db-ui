import dash
from dash import html, dcc, callback, Input, Output
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
from sqlalchemy import text

from models import Session
from components.clayshooting_nav import clayshooting_header

dash.register_page(__name__, path="/clayshooting/summary", redirect_from=["/clayshooting"])

# Clay discipline -> firearm_target ids. Each firearm_end on one of these targets is one round.
DISCIPLINE_TARGETS = [
    ("ATA Trap", [16, 18, 26]),
    ("International Trap", [19, 25]),
    ("NSSA Skeet", [21, 28]),
    ("International Skeet", [23, 24, 27]),
    ("ATA Trap Doubles", [22]),
]


def get_discipline_summary(start_date, end_date):
    """Rounds and shots per clay discipline, plus a total, for an inclusive date range."""
    try:
        session = Session()
        clauses, params = "", {}
        if start_date:
            clauses += " and v.visit_date >= :start_date"
            params["start_date"] = start_date
        if end_date:
            clauses += " and v.visit_date <= :end_date"
            params["end_date"] = end_date
        target_ids = [i for _, ids in DISCIPLINE_TARGETS for i in ids]
        rows = session.execute(
            text(f"""
                select e.firearm_target_id, count(*) as rounds, coalesce(sum(e.quantity), 0) as shots
                from firearm_end e
                join firearm_visit v on e.firearm_visit_id = v.id
                where e.firearm_target_id = any(:target_ids){clauses}
                group by e.firearm_target_id
            """),
            {"target_ids": target_ids, **params},
        ).fetchall()
        session.close()
    except Exception as e:
        print(f"Error querying clay discipline summary: {e}")
        return []

    by_target = {r[0]: (r[1], r[2]) for r in rows}
    data = []
    for name, ids in DISCIPLINE_TARGETS:
        counts = [by_target.get(i, (0, 0)) for i in ids]
        data.append({
            "Discipline": name,
            "Rounds": sum(c[0] for c in counts),
            "Shots": sum(c[1] for c in counts),
        })
    total = {
        "Discipline": "Total",
        "Rounds": sum(d["Rounds"] for d in data),
        "Shots": sum(d["Shots"] for d in data),
    }
    data.append(total)
    for row in data:
        row["% of Rounds"] = row["Rounds"] / total["Rounds"] if total["Rounds"] else 0
    return data


layout = dbc.Container(
    [
        clayshooting_header(),
        dbc.Row(
            dbc.Col([
                html.Label("Date Range"),
                html.Br(),
                dcc.DatePickerRange(
                    id="clay-summary-range",
                    display_format="YYYY-MM-DD",
                    clearable=True,
                ),
            ], md=6),
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col(
                DataTable(
                    id="clay-summary-table",
                    columns=[
                        {"name": "Discipline", "id": "Discipline"},
                        {"name": "Rounds", "id": "Rounds", "type": "numeric"},
                        {"name": "% of Rounds", "id": "% of Rounds", "type": "numeric",
                         "format": {"specifier": ".1%"}},
                        {"name": "Shots", "id": "Shots", "type": "numeric"},
                    ],
                    data=[],
                    # sorted in the callback so the Total row stays at the bottom
                    sort_action="custom",
                    sort_by=[],
                    style_cell={"textAlign": "left", "padding": "10px"},
                    style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"},
                        {"if": {"filter_query": '{Discipline} = "Total"'}, "fontWeight": "bold"},
                    ],
                ),
                md=6,
            ),
        ),
    ],
    fluid=True,
)


@callback(
    Output("clay-summary-table", "data"),
    Input("clay-summary-range", "start_date"),
    Input("clay-summary-range", "end_date"),
    Input("clay-summary-table", "sort_by"),
)
def update_summary(start_date, end_date, sort_by):
    data = get_discipline_summary(start_date, end_date)
    rows, total = data[:-1], data[-1:]
    for sort in reversed(sort_by or []):
        rows.sort(key=lambda r: r[sort["column_id"]], reverse=sort["direction"] == "desc")
    return rows + total
