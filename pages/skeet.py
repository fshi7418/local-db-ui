import dash
from dash import html, callback, Input, Output
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

from models import Session

dash.register_page(__name__, path="/skeet")


def get_skeet_rounds():
    try:
        session = Session()
        query = text("""
            select
                sk.id, v.visit_date, e.id as end_id, sk.discipline, m."name" as gun,
                a."name" as ammunition, car.name as cartridge, car.shot_size as shot,
                c1."name" as choke1, c1.constriction as constriction1,
                c2."name" as choke2, c2.constriction as constriction2,
                sk.num_break
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
            data.append({
                "ID": row[0],
                "Visit Date": row[1].strftime("%Y-%m-%d") if row[1] else None,
                "End ID": row[2],
                "Discipline": row[3],
                "Gun": row[4],
                "Ammunition": row[5],
                "Cartridge": row[6],
                "Shot": row[7],
                "Choke 1": row[8],
                "Constriction 1": row[9],
                "Choke 2": row[10],
                "Constriction 2": row[11],
                "Breaks": row[12],
            })
        return data
    except Exception as e:
        print(f"Error querying skeet rounds: {e}")
        return []


COLUMNS = [
    {"name": "ID",           "id": "ID",           "type": "numeric"},
    {"name": "Visit Date",   "id": "Visit Date",   "type": "text"},
    {"name": "End ID",       "id": "End ID",       "type": "numeric"},
    {"name": "Discipline",   "id": "Discipline",   "type": "text"},
    {"name": "Gun",          "id": "Gun",          "type": "text"},
    {"name": "Breaks",       "id": "Breaks",       "type": "numeric"},
    {"name": "Choke 1",      "id": "Choke 1",      "type": "text"},
    {"name": "Constriction 1", "id": "Constriction 1", "type": "text"},
    {"name": "Choke 2",      "id": "Choke 2",      "type": "text"},
    {"name": "Constriction 2", "id": "Constriction 2", "type": "text"},
    {"name": "Ammunition",   "id": "Ammunition",   "type": "text"},
    {"name": "Cartridge",    "id": "Cartridge",    "type": "text"},
    {"name": "Shot",         "id": "Shot",         "type": "text"},
]

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H2("Skeet"), width=12),
            className="mb-4",
        ),
        dbc.Row(
            dbc.Col(
                dbc.Spinner(html.Div(id="skeet-table")),
                width=12,
            ),
        ),
    ],
    fluid=True,
)


@callback(
    Output("skeet-table", "children"),
    Input("skeet-table", "id"),
)
def load_skeet_table(_):
    data = get_skeet_rounds()
    if not data:
        return html.P("No skeet rounds found.", className="text-muted")
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
