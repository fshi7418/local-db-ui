import dash
from dash import html, dcc, callback, Input, Output, State, ctx
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

from models import Session
from components.skeet_targets import (
    SHOT_CELL_STYLE,
    SHOT_HEADER_STYLE,
    cell_id,
    get_sequence,
    miss_highlight,
    shot_columns,
)

dash.register_page(__name__, path="/skeet")


def get_skeet_rounds(discipline=None):
    try:
        session = Session()
        query = text("""
            select
                sk.id, v.visit_date, e.id as end_id, sk.discipline, sk.low_gun_start, coalesce(m.short_name, m."name") as gun,
                coalesce(a.short_name, a."name") as ammunition, car.name as cartridge, car.shot_size as shot,
                c1."name" as choke1, c1.constriction as constriction1,
                c2."name" as choke2, c2.constriction as constriction2,
                sk.num_break, sk.remarks
            from firearm_visit v
            join firearm_end e on v.id = e.firearm_visit_id
            join firearm_model m on e.firearm_model_id = m.id
            join firearm_ammunition a on e.firearm_ammunition_id = a.id
            join firearm_cartridge car on a.firearm_cartridge_id = car.id
            join skeet_round sk on e.id = sk.firearm_end_id
            left join shotgun_choke c1 on sk.shotgun_choke_id1 = c1.id
            left join shotgun_choke c2 on sk.shotgun_choke_id2 = c2.id
            order by visit_date desc, e.id desc
        """)
        result = session.execute(query).fetchall()
        session.close()

        data = []
        for row in result:
            if discipline and row[3] != discipline:
                continue
            data.append({
                "ID": row[0],
                "Visit Date": row[1].strftime("%Y-%m-%d") if row[1] else None,
                "End ID": row[2],
                "Discipline": row[3],
                "Low Gun Start": row[4],
                "Gun": row[5],
                "Ammunition": row[6],
                "Cartridge": row[7],
                "Shot": row[8],
                "Choke 1": row[9],
                "Constriction 1": row[10],
                "Choke 2": row[11],
                "Constriction 2": row[12],
                "Breaks": row[13],
                "Remarks": row[14],
            })
        return data
    except Exception as e:
        print(f"Error querying skeet rounds: {e}")
        return []


def get_skeet_shots(round_id):
    """Shot-by-shot record for one round, keyed by position in the sequence."""
    try:
        session = Session()
        rows = session.execute(text("""
            select shot_order, target_number, is_option, broken
            from skeet_shot
            where skeet_round_id = :id
            order by shot_order
        """), {"id": round_id}).fetchall()
        session.close()
        return [
            {"shot_order": r[0], "target_number": r[1], "is_option": r[2], "broken": r[3]}
            for r in rows
        ]
    except Exception as e:
        print(f"Error querying skeet shots for round {round_id}: {e}")
        return []


def get_disciplines():
    try:
        session = Session()
        result = session.execute(text("select distinct discipline from skeet_round where discipline is not null order by discipline")).fetchall()
        session.close()
        return [{"label": row[0], "value": row[0]} for row in result]
    except Exception as e:
        print(f"Error querying disciplines: {e}")
        return []


COLUMNS = [
    {"name": "ID",           "id": "ID",           "type": "numeric"},
    {"name": "Visit Date",   "id": "Visit Date",   "type": "text"},
    {"name": "End ID",       "id": "End ID",       "type": "numeric"},
    {"name": "Discipline",   "id": "Discipline",   "type": "text"},
    {"name": "Low Gun Start", "id": "Low Gun Start", "type": "text"},
    {"name": "Gun",          "id": "Gun",          "type": "text"},
    {"name": "Breaks",       "id": "Breaks",       "type": "numeric"},
    {"name": "Choke 1",      "id": "Choke 1",      "type": "text"},
    {"name": "Constriction 1", "id": "Constriction 1", "type": "text"},
    {"name": "Choke 2",      "id": "Choke 2",      "type": "text"},
    {"name": "Constriction 2", "id": "Constriction 2", "type": "text"},
    {"name": "Ammunition",   "id": "Ammunition",   "type": "text"},
    {"name": "Cartridge",    "id": "Cartridge",    "type": "text"},
    {"name": "Shot",         "id": "Shot",         "type": "text"},
    {"name": "Remarks",      "id": "Remarks",      "type": "text"},
]

# Columns available in the picker but hidden until the user asks for them:
# choke names and manufacturers (the constriction is the useful part), everything
# about the second choke, and the end id.
HIDDEN_BY_DEFAULT = {
    "End ID",
    "Choke 1",
    "Choke 2",
}

DEFAULT_COLUMNS = [col["id"] for col in COLUMNS if col["id"] not in HIDDEN_BY_DEFAULT]

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H2("Skeet"), width=12),
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col([
                    html.Label("Filter by Discipline"),
                    dcc.Dropdown(
                        id="skeet-filter-discipline",
                        options=get_disciplines(),
                        placeholder="All disciplines",
                        clearable=True,
                    ),
                ], md=4),
                dbc.Col([
                    html.Label("Date Range"),
                    dcc.DatePickerRange(
                        id="skeet-filter-date-range",
                        display_format="YYYY-MM-DD",
                        clearable=True,
                    ),
                ], md=5),
            ],
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col([
                html.Label("Columns to Display"),
                dcc.Dropdown(
                    id="skeet-filter-columns",
                    options=[{"label": col["name"], "value": col["id"]} for col in COLUMNS],
                    value=DEFAULT_COLUMNS,
                    multi=True,
                    placeholder="Select columns",
                ),
            ], md=12),
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col(
                dbc.Spinner(html.Div(id="skeet-table")),
                width=12,
            ),
        ),

        # Shot-by-shot detail (shown when a round is selected)
        dbc.Row(
            dbc.Col([
                html.Div(id="skeet-shots-header"),
                html.Div(id="skeet-shots-container"),
            ], width=12),
            id="skeet-shots-row",
            style={"display": "none"},
            className="mb-3",
        ),
    ],
    fluid=True,
)


@callback(
    Output("skeet-table", "children"),
    Input("skeet-filter-discipline", "value"),
    Input("skeet-filter-date-range", "start_date"),
    Input("skeet-filter-date-range", "end_date"),
    Input("skeet-filter-columns", "value"),
)
def load_skeet_table(discipline, start_date, end_date, selected_columns):
    data = get_skeet_rounds(discipline=discipline)
    if start_date:
        data = [r for r in data if r["Visit Date"] and r["Visit Date"] >= start_date]
    if end_date:
        data = [r for r in data if r["Visit Date"] and r["Visit Date"] <= end_date]
    if not data:
        return html.P("No skeet rounds found.", className="text-muted")
    if selected_columns:
        columns = [col for col in COLUMNS if col["id"] in selected_columns]
    else:
        columns = COLUMNS
    df = pd.DataFrame(data)
    return DataTable(
        id="skeet-rounds-table",
        columns=columns,
        data=df.to_dict("records"),
        sort_action="native",
        filter_action="native",
        page_action="native",
        page_size=10,
        row_selectable="single",
        selected_rows=[],
        style_cell={"textAlign": "left", "padding": "10px"},
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"},
            {"if": {"state": "selected"}, "backgroundColor": "rgba(0, 116, 217, 0.1)",
             "border": "1px solid #0074D9"},
        ],
    )


# Callback: drill down into the shot-by-shot record when a round is selected
@callback(
    Output("skeet-shots-row", "style"),
    Output("skeet-shots-header", "children"),
    Output("skeet-shots-container", "children"),
    Input("skeet-rounds-table", "selected_rows"),
    Input("skeet-filter-discipline", "value"),
    Input("skeet-filter-date-range", "start_date"),
    Input("skeet-filter-date-range", "end_date"),
    State("skeet-rounds-table", "data"),
)
def load_skeet_shots(selected_rows, _discipline, _start_date, _end_date, table_data):
    hidden = ({"display": "none"}, "", None)

    # changing a filter rebuilds the table, so drop any open drill-down
    if ctx.triggered_id != "skeet-rounds-table":
        return hidden
    if not selected_rows or not table_data:
        return hidden

    row = table_data[selected_rows[0]]
    round_id = row.get("ID")
    discipline = row.get("Discipline")
    header = html.H5(
        f"Round {round_id} · {discipline or '—'} · {row.get('Visit Date') or '—'}",
        className="mt-3 mb-2",
    )

    sequence = get_sequence(discipline)
    if sequence is None:
        return (
            {"display": "block"},
            header,
            html.P(
                f"No target sequence is defined for discipline {discipline!r}.",
                className="text-muted",
            ),
        )

    shots = get_skeet_shots(round_id)
    if not shots:
        return (
            {"display": "block"},
            header,
            html.P(
                "No shot-by-shot record for this round. Add one on the "
                "Skeet Shot Backfill page.",
                className="text-muted",
            ),
        )

    # shot_order is the 1-based position in the discipline's target sequence
    cells = {}
    for shot in shots:
        position = shot["shot_order"]
        if 1 <= position <= len(sequence):
            cells[cell_id(position)] = 1 if shot["broken"] else 0

    breaks = sum(1 for s in shots if s["broken"])
    summary = [f"{breaks}/{len(shots)} broken"]
    if len(shots) != len(sequence):
        summary.append(
            f"only {len(shots)} of {len(sequence)} targets recorded"
        )
    option = next((s for s in shots if s["is_option"]), None)
    if option is not None:
        label = sequence[option["target_number"] - 1][0]
        summary.append(f"option repeated target {option['target_number']} ({label})")

    table = DataTable(
        id="skeet-shots-table",
        columns=shot_columns(sequence),
        data=[cells],
        editable=False,
        style_table={"overflowX": "auto"},
        style_cell=SHOT_CELL_STYLE,
        style_header=SHOT_HEADER_STYLE,
        style_data_conditional=miss_highlight(sequence),
    )
    return (
        {"display": "block"},
        header,
        html.Div([table, html.Small(" · ".join(summary), className="text-muted")]),
    )
