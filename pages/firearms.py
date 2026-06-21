import dash
from dash import dcc, html, callback, Input, Output, State, ctx
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text
from datetime import datetime

from models import Session, postgres_session
from models.firearm import FirearmVisit, FirearmEnd, TrapRound, TrapShot, SkeetRound, FirearmRange

dash.register_page(__name__, path="/firearms")


# ── Reference data helpers ──────────────────────────────────────────────────────

def get_firearm_ranges():
    try:
        session = Session()
        rows = session.query(FirearmRange).order_by(FirearmRange.name).all()
        session.close()
        return [{"label": r.name, "value": r.id} for r in rows]
    except Exception as e:
        print(f"Error querying ranges: {e}")
        return []


def get_firearm_models():
    try:
        session = Session()
        rows = session.execute(text("""
            select m.id, mfr.name || ' – ' || m.name
            from firearm_model m
            join firearm_manufacturer mfr on m.firearm_manufacturer_id = mfr.id
            order by mfr.name, m.name
        """)).fetchall()
        session.close()
        return [{"label": row[1], "value": row[0]} for row in rows]
    except Exception as e:
        print(f"Error querying models: {e}")
        return []


def get_firearm_ammunition():
    try:
        session = Session()
        rows = session.execute(text(
            "select id, name from firearm_ammunition order by name"
        )).fetchall()
        session.close()
        return [{"label": row[1], "value": row[0]} for row in rows]
    except Exception as e:
        print(f"Error querying ammunition: {e}")
        return []


def get_firearm_cartridges():
    try:
        session = Session()
        rows = session.execute(text(
            "select id, name from firearm_cartridge order by name"
        )).fetchall()
        session.close()
        return [{"label": row[1], "value": row[0]} for row in rows]
    except Exception as e:
        print(f"Error querying cartridges: {e}")
        return []


def get_firearm_targets():
    try:
        session = Session()
        rows = session.execute(text(
            "select id, target_name from firearm_target order by target_name"
        )).fetchall()
        session.close()
        return [{"label": row[1] or f"Target {row[0]}", "value": row[0]} for row in rows]
    except Exception as e:
        print(f"Error querying targets: {e}")
        return []


def get_firearm_sights():
    try:
        session = Session()
        rows = session.execute(text(
            "select id, name, type from firearm_sight order by name"
        )).fetchall()
        session.close()
        return [
            {"label": f"{row[1]} ({row[2]})" if row[2] else row[1], "value": row[0]}
            for row in rows
        ]
    except Exception as e:
        print(f"Error querying sights: {e}")
        return []


def get_shotgun_chokes():
    try:
        session = Session()
        rows = session.execute(text("""
            select c.id,
                   coalesce(mfr.name || ' ', '') || c.name
                   || coalesce(' (' || c.constriction || ')', '')
            from shotgun_choke c
            left join firearm_manufacturer mfr on c.firearm_manufacturer_id = mfr.id
            order by c.name
        """)).fetchall()
        session.close()
        return [{"label": row[1], "value": row[0]} for row in rows]
    except Exception as e:
        print(f"Error querying chokes: {e}")
        return []


def get_trap_target_presentations():
    try:
        session = Session()
        rows = session.execute(text(
            "select id, target_presentation from trap_target_presentation order by target_presentation"
        )).fetchall()
        session.close()
        return [{"label": row[1], "value": row[0]} for row in rows]
    except Exception as e:
        print(f"Error querying trap target presentations: {e}")
        return []


def get_ammo_cartridge_id(ammo_id):
    try:
        session = Session()
        row = session.execute(
            text("select firearm_cartridge_id from firearm_ammunition where id = :id"),
            {"id": ammo_id},
        ).fetchone()
        session.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Error querying ammo cartridge: {e}")
        return None


def get_visits_data():
    try:
        session = Session()
        rows = session.execute(text("""
            select
                v.firearm_range_id, v.visit_date, v.time_start, v.time_end,
                rng.name, rng.address_street, rng.address_city, rng.address_province, rng.address_country
            from firearm_visit v, firearm_range rng
            where v.firearm_range_id = rng.id
            order by v.visit_date desc, v.id desc
        """)).fetchall()
        session.close()
        return [
            {
                "Range ID": r[0],
                "Date": str(r[1]),
                "Start": r[2],
                "End": r[3],
                "Range": r[4],
                "Street": r[5],
                "City": r[6],
                "Province": r[7],
                "Country": r[8],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"Error querying visits: {e}")
        return []


def get_ammunition_data():
    try:
        session = Session()
        rows = session.execute(text("""
            select
                a.id as ammunition_id, a.name as ammunition_name, mfr.name as manufacturer,
                c.id as cartridge_id, c.name as cartridge_name, c.shot_size, c.shot_load_oz, c.shot_load_g, c.shot_material
            from firearm_ammunition a
            left join firearm_manufacturer mfr on a.firearm_manufacturer_id = mfr.id
            left join firearm_cartridge c on a.firearm_cartridge_id = c.id
            order by mfr.name, a.name
        """)).fetchall()
        session.close()
        return [
            {
                "ID": r[0],
                "Ammunition": r[1],
                "Manufacturer": r[2],
                "Cartridge ID": r[3],
                "Cartridge": r[4],
                "Shot Size": r[5],
                "Load (oz)": r[6],
                "Load (g)": r[7],
                "Shot Material": r[8],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"Error querying ammunition data: {e}")
        return []


# ── Stats helpers ───────────────────────────────────────────────────────────────

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
        return [{"Manufacturer": r[0], "Model": r[1], "Shots": int(r[2])} for r in result]
    except Exception as e:
        print(f"Error querying shots by model: {e}")
        return []


def get_shots_by_ammunition():
    try:
        session = Session()
        query = text("""
            select a.name as ammunition, max(m.name) as manufacturer, max(c.name) as cartridge, a.casing, a.tip, a.muzzle_velocity_fps, a.weight_grain, sum(e.quantity) as num_shots
            from firearm_end e, firearm_ammunition a, firearm_cartridge c, firearm_manufacturer m
            where e.firearm_ammunition_id = a.id
            and a.firearm_cartridge_id = c.id
            and a.firearm_manufacturer_id = m.id
            group by a.id
            order by sum(e.quantity) desc
        """)
        result = session.execute(query).fetchall()
        session.close()
        return [
            {
                "Ammunition": r[0],
                "Manufacturer": r[1],
                "Cartridge": r[2],
                "Casing": r[3],
                "Tip": r[4],
                "Muzzle Velocity (fps)": r[5],
                "Weight (grain)": r[6],
                "Num Shots": int(r[7]) if r[7] else 0,
            }
            for r in result
        ]
    except Exception as e:
        print(f"Error querying shots by ammunition: {e}")
        return []


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
        return [
            {
                "Cartridge": r[0],
                "Shot Size": r[1],
                "Num Shots": int(r[2]) if r[2] else 0,
                "Load (oz)": r[3],
                "Load (g)": r[4],
            }
            for r in result
        ]
    except Exception as e:
        print(f"Error querying shots by cartridge: {e}")
        return []


# ── Render helper ───────────────────────────────────────────────────────────────

def render_ends_table(ends):
    if not ends:
        return html.P("No ends added yet.", className="text-muted")
    return dbc.Table.from_dataframe(
        pd.DataFrame(ends), striped=True, bordered=True, hover=True, size="sm"
    )


# ── Constants ───────────────────────────────────────────────────────────────────

STANCE_OPTIONS = [
    {"label": "Standing", "value": "standing"},
    {"label": "Benchrest", "value": "benchrest"},
    {"label": "From Cover", "value": "from_cover"},
    {"label": "Retention", "value": "retention"},
    {"label": "Sitting", "value": "sitting"},
    {"label": "Walking", "value": "walking"},
]

TRAP_STYLE_OPTIONS = [
    {"label": "International", "value": "International"},
    {"label": "American (ATA)", "value": "American"},
]

SKEET_STYLE_OPTIONS = [
    {"label": "International", "value": "International"},
    {"label": "American", "value": "American"},
]

# Default reset values for end form fields (33 values, one per add_end output after alert/store/table)
_RESET_END = (
    None, "ammo", None, None,     # model, ammo-type, ammo, cartridge
    None, "yd", None,             # quantity, dist-unit, distance
    None, None, None, None,       # target, shots-scored, pts-stab, support-hands
    None, None,                   # sight, stance
    False, "yd", None, None,         # is-trap, trap-dist-unit, trap-distance, trap-style
    None, None, None, None, False,   # trap-num-break, trap-start-station, trap-choke, trap-target-presentation, trap-by-station
    None, None, None, None, None, # station 1–5
    False, None, None, None, None, False,   # is-skeet, skeet-discipline, skeet-num-break, skeet-choke1, skeet-choke2, skeet-low-gun-start
)


# ── Layout ──────────────────────────────────────────────────────────────────────

layout = dbc.Container(
    [
        dbc.Row(dbc.Col(html.H2("Firearms"), width=12), className="mb-4"),

        # ── Visit form ────────────────────────────────────────────────────────────
        dbc.Row(
            dbc.Col(
                dbc.Card(dbc.CardBody([
                    html.H4("Add Firearm Visit", className="card-title"),

                    dbc.Row([
                        dbc.Col([
                            html.Label("Is this today?"),
                            dbc.RadioItems(
                                id="fv-is-today",
                                options=[
                                    {"label": " Yes", "value": True},
                                    {"label": " No", "value": False},
                                ],
                                value=True,
                                inline=True,
                            ),
                        ], md=4),
                        dbc.Col([
                            html.Label("Date (if not today)"),
                            dcc.DatePickerSingle(
                                id="fv-date",
                                date=datetime.now().date(),
                                disabled=True,
                            ),
                        ], md=4),
                    ], className="mb-3"),

                    dbc.Row(
                        dbc.Col([
                            html.Label("Range"),
                            dcc.Dropdown(
                                id="fv-range",
                                options=get_firearm_ranges(),
                                placeholder="Select range",
                            ),
                        ], md=6),
                        className="mb-3",
                    ),

                    dbc.Row([
                        dbc.Col([
                            html.Label("Start Time (HHMM, optional)"),
                            dbc.Input(id="fv-time-start", placeholder="1030"),
                        ], md=3),
                        dbc.Col([
                            html.Label("End Time (HHMM, optional)"),
                            dbc.Input(id="fv-time-end", placeholder="1230"),
                        ], md=3),
                    ], className="mb-3"),

                    dbc.Row(
                        dbc.Col(
                            dbc.Button("Create Visit", id="fv-create-btn", color="primary"),
                            md=4,
                        ),
                    ),
                ])),
                width=12,
            ),
            className="mb-3",
        ),

        dbc.Row(dbc.Col(html.Div(id="fv-alert"), width=12), className="mb-2"),

        # ── End form (revealed after visit is created) ────────────────────────────
        dbc.Collapse(
            id="fe-collapse",
            is_open=False,
            children=dbc.Card(dbc.CardBody([
                html.H4("Add End", className="card-title"),
                html.Div(id="fv-visit-badge"),
                html.Hr(),

                # Firearm model
                dbc.Row(
                    dbc.Col([
                        html.Label("Firearm Model *"),
                        dcc.Dropdown(
                            id="fe-model",
                            options=get_firearm_models(),
                            placeholder="Select model",
                        ),
                    ], md=6),
                    className="mb-3",
                ),

                # Ammunition / Cartridge toggle
                dbc.Row(
                    dbc.Col([
                        html.Label("Ammunition"),
                        dbc.RadioItems(
                            id="fe-ammo-type",
                            options=[
                                {"label": " Select by Ammunition", "value": "ammo"},
                                {"label": " Select by Cartridge", "value": "cartridge"},
                            ],
                            value="ammo",
                            inline=True,
                        ),
                    ], md=12),
                    className="mb-2",
                ),
                dbc.Row([
                    dbc.Col(
                        dcc.Dropdown(
                            id="fe-ammo",
                            options=get_firearm_ammunition(),
                            placeholder="Select ammunition",
                        ),
                        md=6, id="fe-ammo-col",
                    ),
                    dbc.Col(
                        dcc.Dropdown(
                            id="fe-cartridge",
                            options=get_firearm_cartridges(),
                            placeholder="Select cartridge",
                        ),
                        md=6, id="fe-cartridge-col",
                    ),
                ], className="mb-3"),

                # Quantity + Distance
                dbc.Row([
                    dbc.Col([
                        html.Label("Quantity (optional)"),
                        dbc.Input(id="fe-quantity", type="number", min=0),
                    ], md=2),
                    dbc.Col([
                        html.Label("Distance Unit"),
                        dbc.RadioItems(
                            id="fe-dist-unit",
                            options=[
                                {"label": " yd", "value": "yd"},
                                {"label": " m", "value": "m"},
                            ],
                            value="yd",
                            inline=True,
                        ),
                    ], md=2),
                    dbc.Col([
                        html.Label("Distance (optional)"),
                        dbc.Input(id="fe-distance", type="number", min=0),
                    ], md=2),
                ], className="mb-3"),

                # Target + scores
                dbc.Row([
                    dbc.Col([
                        html.Label("Target (optional)"),
                        dcc.Dropdown(
                            id="fe-target",
                            options=get_firearm_targets(),
                            placeholder="Select target",
                        ),
                    ], md=4),
                    dbc.Col([
                        html.Label("Shots Scored (optional)"),
                        dbc.Input(id="fe-shots-scored", type="number", min=0),
                    ], md=2),
                    dbc.Col([
                        html.Label("Pts of Stabilisation (optional)"),
                        dbc.Input(id="fe-pts-stab", type="number", min=0),
                    ], md=3),
                    dbc.Col([
                        html.Label("Supporting Hands (optional)"),
                        dbc.Input(id="fe-support-hands", type="number", min=0),
                    ], md=3),
                ], className="mb-3"),

                # Sight + Stance
                dbc.Row([
                    dbc.Col([
                        html.Label("Sight (optional)"),
                        dcc.Dropdown(
                            id="fe-sight",
                            options=get_firearm_sights(),
                            placeholder="Select sight",
                        ),
                    ], md=4),
                    dbc.Col([
                        html.Label("Stance (optional)"),
                        dcc.Dropdown(
                            id="fe-stance",
                            options=STANCE_OPTIONS,
                            placeholder="Select stance",
                        ),
                    ], md=4),
                ], className="mb-3"),

                # Trap round toggle
                dbc.Row(
                    dbc.Col([
                        html.Label("Is this a Trap Round?"),
                        dbc.RadioItems(
                            id="fe-is-trap",
                            options=[
                                {"label": " Yes", "value": True},
                                {"label": " No", "value": False},
                            ],
                            value=False,
                            inline=True,
                        ),
                    ], md=6),
                    className="mb-2",
                ),

                # Trap round details (collapsible)
                dbc.Collapse(
                    id="fe-trap-collapse",
                    is_open=False,
                    children=dbc.Card(dbc.CardBody([
                        html.H6("Trap Round Details"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Distance Unit"),
                                dbc.RadioItems(
                                    id="fe-trap-dist-unit",
                                    options=[
                                        {"label": " yd", "value": "yd"},
                                        {"label": " m", "value": "m"},
                                    ],
                                    value="yd",
                                    inline=True,
                                ),
                            ], md=2),
                            dbc.Col([
                                html.Label("Distance (optional)"),
                                dbc.Input(id="fe-trap-distance", type="number", min=0),
                            ], md=2),
                            dbc.Col([
                                html.Label("Style"),
                                dcc.Dropdown(
                                    id="fe-trap-style",
                                    options=TRAP_STYLE_OPTIONS,
                                    placeholder="Select style",
                                ),
                            ], md=3),
                            dbc.Col([
                                html.Label("Num Breaks (optional)"),
                                dbc.Input(id="fe-trap-num-break", type="number", min=0),
                            ], md=2),
                            dbc.Col([
                                html.Label("Starting Station (optional)"),
                                dbc.Input(id="fe-trap-start-station", type="number", min=1, max=5),
                            ], md=2),
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Choke (optional)"),
                                dcc.Dropdown(
                                    id="fe-trap-choke",
                                    options=get_shotgun_chokes(),
                                    placeholder="Select choke",
                                ),
                            ], md=5),
                            dbc.Col([
                                html.Label("Target Presentation (optional)"),
                                dcc.Dropdown(
                                    id="fe-trap-target-presentation",
                                    options=get_trap_target_presentations(),
                                    placeholder="Select presentation",
                                ),
                            ], md=5),
                        ], className="mb-3"),
                        dbc.Row(
                            dbc.Col([
                                html.Label("Breaks by station?"),
                                dbc.RadioItems(
                                    id="fe-trap-by-station",
                                    options=[
                                        {"label": " Yes", "value": True},
                                        {"label": " No", "value": False},
                                    ],
                                    value=False,
                                    inline=True,
                                ),
                            ], md=6),
                            className="mb-2",
                        ),
                        dbc.Collapse(
                            id="fe-station-collapse",
                            is_open=False,
                            children=dbc.Row([
                                dbc.Col([
                                    html.Label(f"Station {i}"),
                                    dbc.Input(
                                        id=f"fe-station-{i}",
                                        type="number",
                                        min=0,
                                        placeholder="Breaks",
                                    ),
                                ], md=2)
                                for i in range(1, 6)
                            ]),
                        ),
                    ]), className="bg-light"),
                ),

                # Skeet round toggle
                dbc.Row(
                    dbc.Col([
                        html.Label("Is this a Skeet Round?"),
                        dbc.RadioItems(
                            id="fe-is-skeet",
                            options=[
                                {"label": " Yes", "value": True},
                                {"label": " No", "value": False},
                            ],
                            value=False,
                            inline=True,
                        ),
                    ], md=6),
                    className="mb-2 mt-2",
                ),

                # Skeet round details (collapsible)
                dbc.Collapse(
                    id="fe-skeet-collapse",
                    is_open=False,
                    children=dbc.Card(dbc.CardBody([
                        html.H6("Skeet Round Details"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Discipline *"),
                                dcc.Dropdown(
                                    id="fe-skeet-discipline",
                                    options=SKEET_STYLE_OPTIONS,
                                    placeholder="Select discipline",
                                ),
                            ], md=3),
                            dbc.Col([
                                html.Label("Num Breaks (optional)"),
                                dbc.Input(id="fe-skeet-num-break", type="number", min=0),
                            ], md=2),
                            dbc.Col([
                                html.Label("Low Gun Start?"),
                                dbc.RadioItems(
                                    id="fe-skeet-low-gun-start",
                                    options=[
                                        {"label": " Yes", "value": True},
                                        {"label": " No", "value": False},
                                    ],
                                    value=False,
                                    inline=True,
                                ),
                            ], md=3),
                        ], className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                html.Label("Choke 1 (optional)"),
                                dcc.Dropdown(
                                    id="fe-skeet-choke1",
                                    options=get_shotgun_chokes(),
                                    placeholder="Select choke",
                                ),
                            ], md=5),
                            dbc.Col([
                                html.Label("Choke 2 (optional)"),
                                dcc.Dropdown(
                                    id="fe-skeet-choke2",
                                    options=get_shotgun_chokes(),
                                    placeholder="Select choke",
                                ),
                            ], md=5),
                        ], className="mb-3"),
                    ]), className="bg-light"),
                ),

                html.Hr(),
                dbc.Row([
                    dbc.Col(
                        dbc.Button("Add End", id="fe-add-btn", color="success"),
                        md=2,
                    ),
                    dbc.Col(
                        dbc.Button("Clear & Restart Visit", id="fv-reset-btn", color="secondary", outline=True),
                        md=2,
                    ),
                ], className="mt-2"),
            ])),
        ),

        dbc.Row(dbc.Col(html.Div(id="fe-alert"), width=12), className="mb-2"),
        dbc.Row(dbc.Col(html.Div(id="fe-ends-table"), width=12), className="mb-4"),

        dbc.Row(
            dbc.Col(
                dbc.Card(dbc.CardBody([
                    html.H4("Visits", className="card-title"),
                    html.Div(id="visits-table"),
                ])),
                width=12,
            ),
            className="mb-4",
        ),

        dcc.Store(id="fv-visit-id-store", data=None),
        dcc.Store(id="fe-ends-store", data=[]),

        # ── Existing stats ────────────────────────────────────────────────────────
        dbc.Row(
            dbc.Col(
                dbc.Card(dbc.CardBody([
                    html.H4("Shots by Model", className="card-title"),
                    html.Div(id="shots-by-model-table"),
                ])),
                width=12,
            ),
            className="mb-4",
        ),

        dbc.Row(
            dbc.Col(
                dbc.Card(dbc.CardBody([
                    html.H4("Shots by Cartridge", className="card-title"),
                    html.Div(id="shots-by-cartridge-table"),
                ])),
                width=12,
            ),
            className="mb-4",
        ),

        dbc.Row(
            dbc.Col(
                dbc.Card(dbc.CardBody([
                    html.H4("Shots by Ammunition", className="card-title"),
                    html.Div(id="shots-by-ammunition-table"),
                ])),
                width=12,
            ),
            className="mb-4",
        ),

        dbc.Row(
            dbc.Col(
                dbc.Card(dbc.CardBody([
                    html.H4("Ammunition", className="card-title"),
                    html.Div(id="ammunition-table"),
                ])),
                width=12,
            ),
            className="mb-4",
        ),
    ],
    fluid=True,
)


# ── Callbacks ───────────────────────────────────────────────────────────────────

@callback(
    Output("fv-date", "disabled"),
    Input("fv-is-today", "value"),
)
def toggle_date(is_today):
    return is_today


@callback(
    Output("fe-collapse", "is_open"),
    Output("fv-visit-id-store", "data"),
    Output("fv-alert", "children"),
    Output("fv-visit-badge", "children"),
    Output("fe-ends-store", "data", allow_duplicate=True),
    Output("fe-ends-table", "children", allow_duplicate=True),
    Input("fv-create-btn", "n_clicks"),
    Input("fv-reset-btn", "n_clicks"),
    State("fv-is-today", "value"),
    State("fv-date", "date"),
    State("fv-range", "value"),
    State("fv-time-start", "value"),
    State("fv-time-end", "value"),
    prevent_initial_call=True,
)
def handle_visit(_create, _reset, is_today, date_str, range_id, time_start, time_end):
    if ctx.triggered_id == "fv-reset-btn":
        return False, None, None, None, [], render_ends_table([])

    try:
        visit_date = (
            datetime.now().date() if is_today
            else datetime.fromisoformat(date_str).date()
        )
        visit = FirearmVisit(
            visit_date=visit_date,
            firearm_range_id=int(range_id) if range_id else None,
            time_start=time_start or None,
            time_end=time_end or None,
        )
        postgres_session.add(visit)
        postgres_session.commit()

        alert = dbc.Alert(
            f"Visit #{visit.id} created for {visit_date}.",
            color="success",
            dismissable=True,
        )
        badge = dbc.Badge(
            f"Visit #{visit.id} – {visit_date}",
            color="success",
            className="mb-2 fs-6",
        )
        return True, visit.id, alert, badge, [], render_ends_table([])

    except Exception as e:
        postgres_session.rollback()
        return (
            False, None,
            dbc.Alert(f"Error creating visit: {e}", color="danger", dismissable=True),
            None, [], render_ends_table([]),
        )


@callback(
    Output("fe-ammo-col", "style"),
    Output("fe-cartridge-col", "style"),
    Input("fe-ammo-type", "value"),
)
def toggle_ammo_cartridge(ammo_type):
    if ammo_type == "ammo":
        return {}, {"display": "none"}
    return {"display": "none"}, {}


@callback(
    Output("fe-trap-collapse", "is_open"),
    Output("fe-skeet-collapse", "is_open"),
    Output("fe-is-trap", "value"),
    Output("fe-is-skeet", "value"),
    Input("fe-is-trap", "value"),
    Input("fe-is-skeet", "value"),
)
def toggle_trap_skeet(is_trap, is_skeet):
    # An end cannot be both a trap round and a skeet round.
    if ctx.triggered_id == "fe-is-trap" and is_trap:
        is_skeet = False
    elif ctx.triggered_id == "fe-is-skeet" and is_skeet:
        is_trap = False
    return bool(is_trap), bool(is_skeet), is_trap, is_skeet


@callback(
    Output("fe-station-collapse", "is_open"),
    Input("fe-trap-by-station", "value"),
)
def toggle_stations(by_station):
    return bool(by_station)


@callback(
    Output("fe-alert", "children"),
    Output("fe-ends-store", "data"),
    Output("fe-ends-table", "children"),
    Output("fe-model", "value"),
    Output("fe-ammo-type", "value"),
    Output("fe-ammo", "value"),
    Output("fe-cartridge", "value"),
    Output("fe-quantity", "value"),
    Output("fe-dist-unit", "value"),
    Output("fe-distance", "value"),
    Output("fe-target", "value"),
    Output("fe-shots-scored", "value"),
    Output("fe-pts-stab", "value"),
    Output("fe-support-hands", "value"),
    Output("fe-sight", "value"),
    Output("fe-stance", "value"),
    Output("fe-is-trap", "value", allow_duplicate=True),
    Output("fe-trap-dist-unit", "value"),
    Output("fe-trap-distance", "value"),
    Output("fe-trap-style", "value"),
    Output("fe-trap-num-break", "value"),
    Output("fe-trap-start-station", "value"),
    Output("fe-trap-choke", "value"),
    Output("fe-trap-target-presentation", "value"),
    Output("fe-trap-by-station", "value"),
    Output("fe-station-1", "value"),
    Output("fe-station-2", "value"),
    Output("fe-station-3", "value"),
    Output("fe-station-4", "value"),
    Output("fe-station-5", "value"),
    Output("fe-is-skeet", "value", allow_duplicate=True),
    Output("fe-skeet-discipline", "value"),
    Output("fe-skeet-num-break", "value"),
    Output("fe-skeet-choke1", "value"),
    Output("fe-skeet-choke2", "value"),
    Output("fe-skeet-low-gun-start", "value"),
    Input("fe-add-btn", "n_clicks"),
    State("fv-visit-id-store", "data"),
    State("fe-model", "value"),
    State("fe-ammo-type", "value"),
    State("fe-ammo", "value"),
    State("fe-cartridge", "value"),
    State("fe-quantity", "value"),
    State("fe-dist-unit", "value"),
    State("fe-distance", "value"),
    State("fe-target", "value"),
    State("fe-shots-scored", "value"),
    State("fe-pts-stab", "value"),
    State("fe-support-hands", "value"),
    State("fe-sight", "value"),
    State("fe-stance", "value"),
    State("fe-is-trap", "value"),
    State("fe-trap-dist-unit", "value"),
    State("fe-trap-distance", "value"),
    State("fe-trap-style", "value"),
    State("fe-trap-num-break", "value"),
    State("fe-trap-start-station", "value"),
    State("fe-trap-choke", "value"),
    State("fe-trap-target-presentation", "value"),
    State("fe-trap-by-station", "value"),
    State("fe-station-1", "value"),
    State("fe-station-2", "value"),
    State("fe-station-3", "value"),
    State("fe-station-4", "value"),
    State("fe-station-5", "value"),
    State("fe-is-skeet", "value"),
    State("fe-skeet-discipline", "value"),
    State("fe-skeet-num-break", "value"),
    State("fe-skeet-choke1", "value"),
    State("fe-skeet-choke2", "value"),
    State("fe-skeet-low-gun-start", "value"),
    State("fe-ends-store", "data"),
    prevent_initial_call=True,
)
def add_end(
    _,
    visit_id, model_id, ammo_type, ammo_id, cartridge_id,
    quantity, dist_unit, distance,
    target_id, shots_scored, pts_stab, support_hands,
    sight_id, stance,
    is_trap, trap_dist_unit, trap_distance, trap_style,
    trap_num_break, trap_start_station, trap_choke_id, trap_target_presentation_id, trap_by_station,
    s1, s2, s3, s4, s5,
    is_skeet, skeet_discipline, skeet_num_break, skeet_choke1, skeet_choke2, skeet_low_gun_start,
    ends_store,
):
    ends_store = ends_store or []

    def warn(msg):
        return (
            dbc.Alert(msg, color="warning"),
            ends_store,
            render_ends_table(ends_store),
        ) + _RESET_END

    if not visit_id:
        return warn("No visit created yet.")
    if not model_id:
        return warn("Firearm model is required.")
    if is_trap and is_skeet:
        return warn("An end cannot be both a trap round and a skeet round.")
    if is_skeet and not skeet_discipline:
        return warn("Skeet discipline is required.")

    try:
        distance_m = None
        if distance is not None:
            distance_m = float(distance) * 0.9144 if dist_unit == "yd" else float(distance)

        actual_ammo_id = None
        actual_cartridge_id = None
        if ammo_type == "ammo" and ammo_id:
            actual_ammo_id = int(ammo_id)
            actual_cartridge_id = get_ammo_cartridge_id(ammo_id)
        elif ammo_type == "cartridge" and cartridge_id:
            actual_cartridge_id = int(cartridge_id)

        end_obj = FirearmEnd(
            firearm_visit_id=int(visit_id),
            firearm_model_id=int(model_id),
            firearm_cartridge_id=actual_cartridge_id,
            firearm_ammunition_id=actual_ammo_id,
            quantity=int(quantity) if quantity is not None else None,
            distance_m=distance_m,
            firearm_target_id=int(target_id) if target_id else None,
            shots_scored=int(shots_scored) if shots_scored is not None else None,
            points_of_stabilisation=int(pts_stab) if pts_stab is not None else None,
            supporting_hands=int(support_hands) if support_hands is not None else None,
            firearm_sight_id=int(sight_id) if sight_id else None,
            stance=stance or None,
        )
        postgres_session.add(end_obj)
        postgres_session.flush()

        if is_trap:
            trap_dist_yard = trap_dist_m = None
            if trap_distance is not None:
                if trap_dist_unit == "yd":
                    trap_dist_yard = float(trap_distance)
                    trap_dist_m = trap_dist_yard * 0.9144
                else:
                    trap_dist_m = float(trap_distance)
                    trap_dist_yard = trap_dist_m * 1.09361

            trap_obj = TrapRound(
                firearm_end_id=end_obj.id,
                distance_yard=trap_dist_yard,
                distance_m=trap_dist_m,
                discipline=trap_style or None,
                num_break=int(trap_num_break) if trap_num_break is not None else None,
                starting_station=int(trap_start_station) if trap_start_station is not None else None,
                shotgun_choke_id=int(trap_choke_id) if trap_choke_id else None,
                trap_target_presentation_id=int(trap_target_presentation_id) if trap_target_presentation_id else None,
            )
            postgres_session.add(trap_obj)
            postgres_session.flush()

            if trap_by_station:
                for station_num, breaks in enumerate([s1, s2, s3, s4, s5], start=1):
                    if breaks is not None:
                        postgres_session.add(TrapShot(
                            trap_round_id=trap_obj.id,
                            station=station_num,
                            num_break=int(breaks),
                        ))

        if is_skeet:
            skeet_obj = SkeetRound(
                firearm_end_id=end_obj.id,
                discipline=skeet_discipline,
                num_break=int(skeet_num_break) if skeet_num_break is not None else None,
                shotgun_choke_id1=int(skeet_choke1) if skeet_choke1 else None,
                shotgun_choke_id2=int(skeet_choke2) if skeet_choke2 else None,
                low_gun_start=bool(skeet_low_gun_start),
            )
            postgres_session.add(skeet_obj)
            postgres_session.flush()

        postgres_session.commit()

        new_row = {
            "End ID": end_obj.id,
            "Qty": quantity if quantity is not None else "",
            "Dist (m)": round(distance_m, 1) if distance_m is not None else "",
            "Trap": "Yes" if is_trap else "No",
            "Skeet": "Yes" if is_skeet else "No",
        }
        new_store = ends_store + [new_row]
        return (
            dbc.Alert(f"End #{end_obj.id} added.", color="success", dismissable=True),
            new_store,
            render_ends_table(new_store),
        ) + _RESET_END

    except Exception as e:
        postgres_session.rollback()
        return (
            dbc.Alert(f"Error adding end: {e}", color="danger", dismissable=True),
            ends_store,
            render_ends_table(ends_store),
        ) + _RESET_END


# ── Existing stat callbacks ──────────────────────────────────────────────────────

@dash.callback(
    dash.Output("visits-table", "children"),
    dash.Input("visits-table", "id"),
)
def update_visits_table(_):
    data = get_visits_data()
    if not data:
        return html.P("No visits recorded.")
    df = pd.DataFrame(data)
    return DataTable(
        columns=[{"name": c, "id": c} for c in df.columns],
        data=df.to_dict("records"),
        sort_action="native",
        filter_action="native",
        page_action="native",
        page_size=10,
        style_cell={"textAlign": "left", "padding": "10px"},
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"}
        ],
    )


@dash.callback(
    dash.Output("shots-by-model-table", "children"),
    dash.Input("shots-by-model-table", "id"),
)
def update_shots_by_model(_):
    data = get_shots_by_model()
    if not data:
        return html.P("No data available")
    return dbc.Table.from_dataframe(pd.DataFrame(data), striped=True, bordered=True, hover=True)


@dash.callback(
    dash.Output("shots-by-cartridge-table", "children"),
    dash.Input("shots-by-cartridge-table", "id"),
)
def update_shots_by_cartridge(_):
    data = get_shots_by_cartridge()
    if not data:
        return html.P("No data available")
    return dbc.Table.from_dataframe(pd.DataFrame(data), striped=True, bordered=True, hover=True)


@dash.callback(
    dash.Output("shots-by-ammunition-table", "children"),
    dash.Input("shots-by-ammunition-table", "id"),
)
def update_shots_by_ammunition(_):
    data = get_shots_by_ammunition()
    if not data:
        return html.P("No data available")
    return dbc.Table.from_dataframe(pd.DataFrame(data), striped=True, bordered=True, hover=True)


@dash.callback(
    dash.Output("ammunition-table", "children"),
    dash.Input("ammunition-table", "id"),
)
def update_ammunition_table(_):
    data = get_ammunition_data()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    return DataTable(
        columns=[{"name": c, "id": c} for c in df.columns],
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
