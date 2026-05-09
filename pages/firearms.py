import dash
from dash import html
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

# Import from local-db backend
from models import Session

dash.register_page(__name__, path="/firearms")

# Helper: query shots by model
def get_shots_by_model():
    try:
        session = Session()
        query = text("""
            select m.name as manufacturer, model.name as model, sum(e.quantity) as num_shots
            from firearm_end e, firearm_model model, firearm_manufacturer m
            where e.firearm_model_id = model.id
            and model.firearm_manufacturer_id = m.id
            and e.quantity is not null
            group by m.name, model.name
            order by sum(e.quantity) desc
            limit 15
        """)
        result = session.execute(query).fetchall()
        session.close()

        data = []
        for row in result:
            data.append({
                "Manufacturer": row[0],
                "Model": row[1],
                "Shots": int(row[2]),
            })
        return data
    except Exception as e:
        print(f"Error querying shots by model: {e}")
        return []

# Helper: query shots by cartridge
def get_shots_by_cartridge():
    try:
        session = Session()
        query = text("""
            select c.name, c.shot_size, sum(e.quantity) as num_shots, c.shot_load_oz, c.shot_load_g
            from firearm_end e, firearm_cartridge c, firearm_visit v
            where e.firearm_cartridge_id = c.id
            and v.id = e.firearm_visit_id
            group by c.id
            order by sum(e.quantity) desc
            limit 15
        """)
        result = session.execute(query).fetchall()
        session.close()

        data = []
        for row in result:
            data.append({
                "Cartridge": row[0],
                "Shot Size": row[1],
                "Num Shots": int(row[2]) if row[2] else 0,
                "Load (oz)": row[3],
                "Load (g)": row[4],
            })
        return data
    except Exception as e:
        print(f"Error querying shots by cartridge: {e}")
        return []

# Layout
layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H2("Firearms"),
                width=12,
            ),
            className="mb-4"
        ),

        # Shots by Model
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H4("Shots by Model", className="card-title"),
                        html.Div(id="shots-by-model-table"),
                    ]),
                ),
                width=12,
            ),
            className="mb-4"
        ),

        # Shots by Cartridge
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H4("Shots by Cartridge", className="card-title"),
                        html.Div(id="shots-by-cartridge-table"),
                    ]),
                ),
                width=12,
            ),
            className="mb-4"
        ),

    ],
    fluid=True,
)

# Callbacks to populate tables
@dash.callback(
    dash.Output("shots-by-model-table", "children"),
    dash.Input("shots-by-model-table", "id"),
)
def update_shots_by_model(_):
    data = get_shots_by_model()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True)

@dash.callback(
    dash.Output("shots-by-cartridge-table", "children"),
    dash.Input("shots-by-cartridge-table", "id"),
)
def update_shots_by_cartridge(_):
    data = get_shots_by_cartridge()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True)
