import dash
from dash import html, callback, Input, Output
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

from models import Session

dash.register_page(__name__, path="/trap")


def get_trap_rounds():
    try:
        session = Session()
        query = text("""
            select
                t.id, v.visit_date, e.id as end_id, t.discipline, m."name" as gun,
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
            order by visit_date desc, e.id desc
        """)
        result = session.execute(query).fetchall()
        session.close()

        data = []
        for row in result:
            data.append({
                "ID": row[0],
                "Visit Date": row[1].strftime("%Y-%m-%d") if row[1] else None,
                "End ID": row[2],
                "Discipline": row[3],
                "Breaks": row[12],
                "Gun": row[4],
                "Choke": row[9],
                "Constriction": row[10],
                "Choke Mfr": row[8],
                "Ammunition": row[5],
                "Cartridge": row[6],
                "Shot": row[7],
            })
        return data
    except Exception as e:
        print(f"Error querying trap rounds: {e}")
        return []


COLUMNS = [
    {"name": "ID",            "id": "ID",            "type": "numeric"},
    {"name": "Visit Date",    "id": "Visit Date",    "type": "text"},
    {"name": "End ID",        "id": "End ID",        "type": "numeric"},
    {"name": "Discipline",    "id": "Discipline",    "type": "text"},
    {"name": "Breaks",        "id": "Breaks",        "type": "numeric"},
    {"name": "Gun",           "id": "Gun",           "type": "text"},
    {"name": "Choke",         "id": "Choke",         "type": "text"},
    {"name": "Constriction",  "id": "Constriction",  "type": "text"},
    {"name": "Choke Mfr",    "id": "Choke Mfr",    "type": "text"},
    {"name": "Ammunition",    "id": "Ammunition",    "type": "text"},
    {"name": "Cartridge",     "id": "Cartridge",     "type": "text"},
    {"name": "Shot",          "id": "Shot",          "type": "text"},
]

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H2("Trap"), width=12),
            className="mb-4",
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
    Input("trap-rounds-datatable", "id"),
)
def load_trap_table(_):
    data = get_trap_rounds()
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
