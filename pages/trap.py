import dash
from dash import html, dcc, callback, Input, Output
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

from models import Session

dash.register_page(__name__, path="/trap")


def get_trap_rounds(discipline=None):
    try:
        session = Session()
        query = text("""
            select
                t.id, v.visit_date, e.id as end_id, t.discipline, ttp.target_presentation, m."name" as gun,
                a."name" as ammunition, car.name as cartridge, car.shot_size as shot,
                c_ma."name" as choke_manufacturer, c."name" as choke,
                c.constriction, c.diametre_in, t.num_break
            from firearm_visit v
            join firearm_end e on v.id = e.firearm_visit_id
            join firearm_model m on e.firearm_model_id = m.id
            join firearm_ammunition a on e.firearm_ammunition_id = a.id
            join firearm_cartridge car on a.firearm_cartridge_id = car.id
            join trap_round t on e.id = t.firearm_end_id
            left join shotgun_choke c on t.shotgun_choke_id = c.id
            left join firearm_manufacturer c_ma on c.firearm_manufacturer_id = c_ma.id
            left join trap_target_presentation ttp on t.trap_target_presentation_id = ttp.id
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
                "Target Presentation": row[4],
                "Breaks": row[13],
                "Gun": row[5],
                "Choke": row[10],
                "Constriction": row[11],
                "Choke Mfr": row[9],
                "Ammunition": row[6],
                "Cartridge": row[7],
                "Shot": row[8],
            })
        return data
    except Exception as e:
        print(f"Error querying trap rounds: {e}")
        return []


def get_disciplines():
    try:
        session = Session()
        result = session.execute(text("select distinct discipline from trap_round where discipline is not null order by discipline")).fetchall()
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
    {"name": "Target Presentation",   "id": "Target Presentation",   "type": "text"},
    {"name": "Breaks",                "id": "Breaks",                "type": "numeric"},
    {"name": "Gun",                   "id": "Gun",                   "type": "text"},
    {"name": "Choke",                 "id": "Choke",                 "type": "text"},
    {"name": "Constriction",          "id": "Constriction",          "type": "text"},
    {"name": "Choke Mfr",            "id": "Choke Mfr",            "type": "text"},
    {"name": "Ammunition",            "id": "Ammunition",            "type": "text"},
    {"name": "Cartridge",             "id": "Cartridge",             "type": "text"},
    {"name": "Shot",                  "id": "Shot",                  "type": "text"},
]

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H2("Trap"), width=12),
            className="mb-4",
        ),
        dbc.Row(
            dbc.Col([
                html.Label("Filter by Discipline"),
                dcc.Dropdown(
                    id="trap-filter-discipline",
                    options=get_disciplines(),
                    placeholder="All disciplines",
                    clearable=True,
                ),
            ], md=4),
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col(
                dbc.Spinner(html.Div(id="trap-rounds-datatable")),
                width=12,
            ),
        ),
    ],
    fluid=True,
)


@callback(
    Output("trap-rounds-datatable", "children"),
    Input("trap-filter-discipline", "value"),
)
def load_trap_table(discipline):
    data = get_trap_rounds(discipline=discipline)
    if not data:
        return html.P("No trap rounds found.", className="text-muted")
    df = pd.DataFrame(data)
    return DataTable(
        columns=COLUMNS,
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
