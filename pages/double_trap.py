import dash
from dash import html, dcc, callback, Input, Output
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

from models import Session

dash.register_page(__name__, path="/double-trap")


def get_double_trap_rounds(discipline=None):
    try:
        session = Session()
        query = text("""
            select
                dt.id, v.visit_date, e.id as end_id, dt.discipline, m."name" as gun,
                a."name" as ammunition, car.name as cartridge, car.shot_size as shot,
                car.shot_load_oz, car.shot_load_g,
                c1."name" as choke1, c1.constriction as constriction1,
                c2."name" as choke2, c2.constriction as constriction2,
                dt.num_break, dt.starting_station,
                dt.distance_yard, dt.distance_m
            from firearm_visit v
            join firearm_end e on v.id = e.firearm_visit_id
            join firearm_model m on e.firearm_model_id = m.id
            join firearm_ammunition a on e.firearm_ammunition_id = a.id
            join firearm_cartridge car on a.firearm_cartridge_id = car.id
            join double_trap_round dt on e.id = dt.firearm_end_id
            left join shotgun_choke c1 on dt.shotgun_choke_id1 = c1.id
            left join shotgun_choke c2 on dt.shotgun_choke_id2 = c2.id
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
                "Dist (yd)": row[16],
                "Dist (m)": row[17],
                "Breaks": row[14],
                "Start Station": row[15],
                "Gun": row[4],
                "Choke 1": row[10],
                "Constriction 1": row[11],
                "Choke 2": row[12],
                "Constriction 2": row[13],
                "Ammunition": row[5],
                "Cartridge": row[6],
                "Shot": row[7],
                "Shot Load (oz)": row[8],
                "Shot Load (g)": row[9],
            })
        return data
    except Exception as e:
        print(f"Error querying double trap rounds: {e}")
        return []


def get_disciplines():
    try:
        session = Session()
        result = session.execute(text("select distinct discipline from double_trap_round where discipline is not null order by discipline")).fetchall()
        session.close()
        return [{"label": row[0], "value": row[0]} for row in result]
    except Exception as e:
        print(f"Error querying disciplines: {e}")
        return []


COLUMNS = [
    {"name": "ID",                    "id": "ID",                    "type": "numeric"},
    {"name": "Visit Date",            "id": "Visit Date",            "type": "text"},
    {"name": "End ID",                "id": "End ID",                "type": "numeric"},
    {"name": "Discipline",            "id": "Discipline",            "type": "text"},
    {"name": "Dist (yd)",             "id": "Dist (yd)",             "type": "numeric"},
    {"name": "Dist (m)",              "id": "Dist (m)",              "type": "numeric"},
    {"name": "Breaks",                "id": "Breaks",                "type": "numeric"},
    {"name": "Start Station",         "id": "Start Station",         "type": "numeric"},
    {"name": "Gun",                   "id": "Gun",                   "type": "text"},
    {"name": "Choke 1",               "id": "Choke 1",               "type": "text"},
    {"name": "Constriction 1",        "id": "Constriction 1",        "type": "text"},
    {"name": "Choke 2",               "id": "Choke 2",               "type": "text"},
    {"name": "Constriction 2",        "id": "Constriction 2",        "type": "text"},
    {"name": "Ammunition",            "id": "Ammunition",            "type": "text"},
    {"name": "Cartridge",             "id": "Cartridge",             "type": "text"},
    {"name": "Shot",                  "id": "Shot",                  "type": "text"},
    {"name": "Shot Load (oz)",        "id": "Shot Load (oz)",        "type": "numeric"},
    {"name": "Shot Load (g)",         "id": "Shot Load (g)",         "type": "numeric"},
]

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H2("Double Trap"), width=12),
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col([
                    html.Label("Filter by Discipline"),
                    dcc.Dropdown(
                        id="double-trap-filter-discipline",
                        options=get_disciplines(),
                        placeholder="All disciplines",
                        clearable=True,
                    ),
                ], md=4),
                dbc.Col([
                    html.Label("Date Range"),
                    dcc.DatePickerRange(
                        id="double-trap-filter-date-range",
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
                    id="double-trap-filter-columns",
                    options=[{"label": col["name"], "value": col["id"]} for col in COLUMNS],
                    value=[col["id"] for col in COLUMNS],
                    multi=True,
                    placeholder="Select columns",
                ),
            ], md=12),
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col(
                dbc.Spinner(html.Div(id="double-trap-rounds-datatable")),
                width=12,
            ),
        ),
    ],
    fluid=True,
)


@callback(
    Output("double-trap-rounds-datatable", "children"),
    Input("double-trap-filter-discipline", "value"),
    Input("double-trap-filter-date-range", "start_date"),
    Input("double-trap-filter-date-range", "end_date"),
    Input("double-trap-filter-columns", "value"),
)
def load_double_trap_table(discipline, start_date, end_date, selected_columns):
    data = get_double_trap_rounds(discipline=discipline)
    if start_date:
        data = [r for r in data if r["Visit Date"] and r["Visit Date"] >= start_date]
    if end_date:
        data = [r for r in data if r["Visit Date"] and r["Visit Date"] <= end_date]
    if not data:
        return html.P("No double trap rounds found.", className="text-muted")
    if selected_columns:
        columns = [col for col in COLUMNS if col["id"] in selected_columns]
    else:
        columns = COLUMNS
    df = pd.DataFrame(data)
    return DataTable(
        columns=columns,
        data=df.to_dict("records"),
        sort_action="native",
        filter_action="native",
        page_action="native",
        page_size=50,
        style_cell={"textAlign": "left", "padding": "10px"},
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"}
        ],
    )
