import dash
from dash import html, callback, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# Import from local-db backend
from models import Session

dash.register_page(__name__, path="/archery")

# Helper: query archery rounds overview
def get_archery_rounds():
    try:
        session = Session()
        query = text("""
            select
                rd.id, rd.date, rd.num_shots, rd.avg_shots, rd.total_score, sc.name as scoring_rule, rd.num_x, rd.num_10, rd.num_9, rng.name as range, rd.distance_m, r.name as riser, l.name as limb, a.name as arrow, ar.name as arrow_rest, ar.arrow_rest_type as arrow_rest_type,
                rls.name as release_aid, rd.seconds_per_arrow,
                a.spine, rd.draw_weight_lb, s.name as sight, s.magnification, rd.stdev_ends, rd.stdev_shots,
                rd.sight as sight_used, rd.clicker, rd.stabilisation, rd.known_distance, rd.variable_distance, rd.days_since_last_practice
            from archery_round rd
            join archery_riser r on rd.archery_riser_id = r.id
            join archery_limb l on rd.archery_limb_id = l.id
            left join archery_arrow a on rd.archery_arrow_id = a.id
            left join archery_arrow_rest ar on rd.archery_arrow_rest_id = ar.id
            join archery_range rng on rd.archery_range_id = rng.id
            left join archery_sight s on rd.archery_sight_id = s.id
            join archery_scoring_rule sc on rd.archery_scoring_rule_id = sc.id
            left join archery_target tgt ON tgt.id = rd.archery_target_id
            left join archery_release_aid rls on rls.id = rd.archery_release_aid_id
            where true
            order by rd.date desc, rd.id desc
            limit 20
        """)
        result = session.execute(query).fetchall()
        session.close()

        data = []
        for row in result:
            data.append({
                "ID": row[0],
                "Date": row[1].strftime("%Y-%m-%d") if row[1] else None,
                "Num Shots": row[2],
                "Avg Shots": row[3],
                "Total Score": row[4],
                "Scoring Rule": row[5],
                "X": row[6],
                "10": row[7],
                "9": row[8],
                "Range": row[9],
                "Distance (m)": row[10],
                "Riser": row[11],
                "Limb": row[12],
                "Arrow": row[13],
                "Arrow Rest": row[14],
                "Arrow Rest Type": row[15],
                "Release Aid": row[16],
                "Seconds/Arrow": row[17],
                "Spine": row[18],
                "Draw Weight (lb)": row[19],
                "Sight": row[20],
                "Magnification": row[21],
                "StDev Ends": row[22],
                "StDev Shots": row[23],
                "Sight Used": row[24],
                "Clicker": row[25],
                "Stabilisation": row[26],
                "Known Distance": row[27],
                "Variable Distance": row[28],
                "Days Since Practice": row[29],
            })
        return data
    except Exception as e:
        print(f"Error querying archery rounds: {e}")
        return []

# Helper: query total shots categorized by bow type, limb, draw weight
def get_shots_categorized(start_date, end_date):
    try:
        session = Session()
        query = text("""
            select t.name as bow_type, l.name as limb, r.draw_weight_lb, sum(num_shots) as num_shots
            from archery_round r, archery_limb l, archery_bow_type t
            where r.archery_limb_id = l.id
            and l.archery_bow_type_id = t.id
            and r.date >= :start_date
            and r.date <= :end_date
            group by l.name, t.name, r.draw_weight_lb
            order by sum(num_shots) desc
        """)
        result = session.execute(query, {"start_date": start_date, "end_date": end_date}).fetchall()
        session.close()

        data = []
        for row in result:
            data.append({
                "Bow Type": row[0],
                "Limb": row[1],
                "Draw Weight (lb)": row[2],
                "Num Shots": int(row[3]),
            })
        return data
    except Exception as e:
        print(f"Error querying shots categorized: {e}")
        return []

# Layout
layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H2("Archery"),
                width=12,
            ),
            className="mb-4"
        ),

        # Archery Rounds Overview
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H4("Archery Rounds", className="card-title"),
                        html.Div(id="archery-rounds-table"),
                    ]),
                ),
                width=12,
            ),
            className="mb-4"
        ),

        # Total Shots Categorized
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H4("Total Shots Categorized", className="card-title"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Start Date"),
                                dbc.Input(
                                    id="shots-cat-start-date",
                                    type="date",
                                    value="2026-01-01",
                                ),
                            ], md=6),
                            dbc.Col([
                                html.Label("End Date"),
                                dbc.Input(
                                    id="shots-cat-end-date",
                                    type="date",
                                    value="2026-12-31",
                                ),
                            ], md=6),
                        ], className="mb-3"),
                        html.Div(id="shots-categorized-table"),
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
    dash.Output("archery-rounds-table", "children"),
    dash.Input("archery-rounds-table", "id"),
)
def update_archery_rounds(_):
    data = get_archery_rounds()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True)

@callback(
    Output("shots-categorized-table", "children"),
    Input("shots-cat-start-date", "value"),
    Input("shots-cat-end-date", "value"),
)
def update_shots_categorized(start_date, end_date):
    if not start_date or not end_date:
        return html.P("Please select both dates")
    data = get_shots_categorized(start_date, end_date)
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True)
