import re

import dash
from dash import html, dcc, callback, Input, Output, State, ctx
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# Import from local-db backend
from models import Session, postgres_session
from script_modules.add_archery_round import Round

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


# ── Reference data helpers (entry form) ────────────────────────────────────────

def _options(query, label_fn=lambda r: r[1]):
    try:
        session = Session()
        rows = session.execute(text(query)).fetchall()
        session.close()
        return [{"label": label_fn(r), "value": r[0]} for r in rows]
    except Exception as e:
        print(f"Error querying options: {e}")
        return []


def get_archery_ranges():
    return _options("select id, name from archery_range order by name")


def get_archery_risers():
    return _options(
        "select id, name from archery_riser order by name",
        lambda r: f"{r[0]} - {r[1]}",
    )


def get_archery_limbs():
    return _options(
        "select id, name from archery_limb order by name",
        lambda r: f"{r[0]} - {r[1]}",
    )


def get_archery_arrows():
    return _options(
        "select id, name, spine from archery_arrow order by name",
        lambda r: f"{r[0]} - {r[1]} (spine {r[2]})" if r[2] else f"{r[0]} - {r[1]}",
    )


def get_archery_arrow_rests():
    return _options(
        "select id, name, arrow_rest_type from archery_arrow_rest order by name",
        lambda r: f"{r[0]} - {r[1]} ({r[2]})" if r[2] else f"{r[0]} - {r[1]}",
    )


def get_archery_sights():
    return _options(
        "select id, name from archery_sight order by name",
        lambda r: f"{r[0]} - {r[1]}",
    )


def get_archery_release_aids():
    return _options(
        "select id, name from archery_release_aid order by name",
        lambda r: f"{r[0]} - {r[1]}",
    )


def get_archery_targets():
    return _options(
        "select id, type, full_size_cm, actual_size_cm from archery_target order by id",
        lambda r: f"{r[0]} - " + " – ".join(
            p for p in [
                r[1] or "Target",
                f"{r[2]:g} cm" if r[2] else None,
                f"actual {r[3]:g} cm" if r[3] and r[3] != r[2] else None,
            ] if p
        ),
    )


def get_archery_scoring_rules():
    return _options("select id, name from archery_scoring_rule order by id")


def get_last_round_defaults():
    """Equipment/settings from the most recent round, used to prefill the form."""
    try:
        session = Session()
        row = session.execute(text("""
            select archery_range_id, archery_scoring_rule_id, archery_target_id, distance_m,
                   archery_riser_id, archery_limb_id, draw_weight_lb, archery_arrow_id,
                   archery_arrow_rest_id, archery_sight_id, archery_release_aid_id,
                   sight, stabilisation, clicker, known_distance, variable_distance
            from archery_round
            order by date desc, id desc
            limit 1
        """)).fetchone()
        session.close()
    except Exception as e:
        print(f"Error querying last round: {e}")
        row = None
    if not row:
        return {"flags": []}
    flag_names = ["sight", "stabilisation", "clicker", "known_distance", "variable_distance"]
    return {
        "range": row[0], "scoring_rule": row[1], "target": row[2], "distance": row[3],
        "riser": row[4], "limb": row[5], "draw_weight": row[6], "arrow": row[7],
        "arrow_rest": row[8], "sight": row[9], "release_aid": row[10],
        "flags": [name for name, val in zip(flag_names, row[11:16]) if val],
    }


def parse_end_scores(raw):
    """Parse '10 9 x 8' (spaces or commas) into [10, 9, 'x', 8]. Raises ValueError."""
    tokens = [t for t in re.split(r"[\s,]+", (raw or "").strip()) if t]
    if not tokens:
        raise ValueError("Enter at least one score.")
    scores = []
    for t in tokens:
        if t.lower() == "x":
            scores.append("x")
        elif t.isdigit() and 0 <= int(t) <= 10:
            scores.append(int(t))
        else:
            raise ValueError(f"Invalid score '{t}': use integers 0–10 or 'x'.")
    return scores


def end_total(scores):
    return sum(10 if s == "x" else s for s in scores)


def render_archery_ends_table(ends):
    if not ends:
        return html.P("No ends added yet.", className="text-muted")
    rows = [
        {
            "End": i + 1,
            "Scores": " ".join(str(s).upper() for s in end),
            "Shots": len(end),
            "Total": end_total(end),
        }
        for i, end in enumerate(ends)
    ]
    all_scores = [10 if s == "x" else s for end in ends for s in end]
    summary = html.P(
        f"{len(ends)} ends · {len(all_scores)} shots · total {sum(all_scores)} · "
        f"avg {sum(all_scores) / len(all_scores):.2f}",
        className="fw-bold mb-0",
    )
    return html.Div([
        dbc.Table.from_dataframe(pd.DataFrame(rows), striped=True, bordered=True, hover=True, size="sm"),
        summary,
    ])


ROUND_FLAG_OPTIONS = [
    {"label": " Sight used", "value": "sight"},
    {"label": " Stabiliser", "value": "stabilisation"},
    {"label": " Clicker", "value": "clicker"},
    {"label": " Known distance", "value": "known_distance"},
    {"label": " Variable distance", "value": "variable_distance"},
    {"label": " Hungry", "value": "hunger"},
]

YES_NO = [{"label": " Yes", "value": True}, {"label": " No", "value": False}]

ARCHERY_ROUND_COLUMNS = [
    "ID", "Date", "Num Shots", "Avg Shots", "Total Score", "Scoring Rule",
    "X", "10", "9", "Range", "Distance (m)", "Riser", "Limb", "Arrow",
    "Arrow Rest", "Arrow Rest Type", "Release Aid", "Seconds/Arrow", "Spine",
    "Draw Weight (lb)", "Sight", "Magnification", "StDev Ends", "StDev Shots",
    "Sight Used", "Clicker", "Stabilisation", "Known Distance",
    "Variable Distance", "Days Since Practice",
]

def _labelled(label, component, md):
    return dbc.Col([html.Label(label), component], md=md)


def round_entry_section():
    d = get_last_round_defaults()
    return [
        # ── Step 1: round details ─────────────────────────────────────────────────
        dbc.Row(
            dbc.Col(
                dbc.Card(dbc.CardBody([
                    html.H4("Add Archery Round", className="card-title"),
                    html.P(
                        "Equipment and settings are prefilled from the most recent round.",
                        className="text-muted small",
                    ),

                    dbc.Row([
                        _labelled("Is this today?", dbc.RadioItems(
                            id="ar-is-today", options=YES_NO, value=True, inline=True,
                        ), 3),
                        _labelled("Date (if not today)", dcc.DatePickerSingle(
                            id="ar-date", date=datetime.now().date(), disabled=True,
                        ), 3),
                        _labelled("Start Time (HHMM, optional)",
                                  dbc.Input(id="ar-time-start", placeholder="1030"), 3),
                        _labelled("End Time (HHMM, optional)",
                                  dbc.Input(id="ar-time-end", placeholder="1230"), 3),
                    ], className="mb-3"),

                    dbc.Row([
                        _labelled("Range *", dcc.Dropdown(
                            id="ar-range", options=get_archery_ranges(), value=d.get("range"),
                            placeholder="Select range",
                        ), 3),
                        _labelled("Scoring Rule *", dcc.Dropdown(
                            id="ar-scoring-rule", options=get_archery_scoring_rules(),
                            value=d.get("scoring_rule"), placeholder="Select scoring rule",
                        ), 3),
                        _labelled("Target", dcc.Dropdown(
                            id="ar-target", options=get_archery_targets(), value=d.get("target"),
                            placeholder="Select target",
                        ), 3),
                        _labelled("Distance (m) *", dbc.Input(
                            id="ar-distance", type="number", min=0, step="any", value=d.get("distance"),
                        ), 3),
                    ], className="mb-3"),

                    dbc.Row([
                        _labelled("Riser *", dcc.Dropdown(
                            id="ar-riser", options=get_archery_risers(), value=d.get("riser"),
                            placeholder="Select riser",
                        ), 3),
                        _labelled("Limb *", dcc.Dropdown(
                            id="ar-limb", options=get_archery_limbs(), value=d.get("limb"),
                            placeholder="Select limb",
                        ), 3),
                        _labelled("Draw Weight (lb)", dbc.Input(
                            id="ar-draw-weight", type="number", min=0, step="any",
                            value=d.get("draw_weight"),
                        ), 2),
                        _labelled("Arrow", dcc.Dropdown(
                            id="ar-arrow", options=get_archery_arrows(), value=d.get("arrow"),
                            placeholder="Select arrow",
                        ), 4),
                    ], className="mb-3"),

                    dbc.Row([
                        _labelled("Arrow Rest", dcc.Dropdown(
                            id="ar-arrow-rest", options=get_archery_arrow_rests(),
                            value=d.get("arrow_rest"), placeholder="Select arrow rest",
                        ), 4),
                        _labelled("Sight", dcc.Dropdown(
                            id="ar-sight", options=get_archery_sights(), value=d.get("sight"),
                            placeholder="Select sight",
                        ), 4),
                        _labelled("Release Aid", dcc.Dropdown(
                            id="ar-release-aid", options=get_archery_release_aids(),
                            value=d.get("release_aid"), placeholder="Select release aid",
                        ), 4),
                    ], className="mb-3"),

                    dbc.Row([
                        _labelled("Options", dbc.Checklist(
                            id="ar-flags", options=ROUND_FLAG_OPTIONS, value=d["flags"], inline=True,
                        ), 6),
                        _labelled("Seconds per Arrow (if timed)", dbc.Input(
                            id="ar-seconds-per-arrow", type="number", min=0, step="any",
                        ), 2),
                        _labelled("Mental (1–10)", dbc.Input(
                            id="ar-cond-mental", type="number", min=1, max=10, step=1,
                        ), 2),
                        _labelled("Range Condition (1–10)", dbc.Input(
                            id="ar-cond-env", type="number", min=1, max=10, step=1,
                        ), 2),
                    ], className="mb-3"),

                    dbc.Row(
                        _labelled("Did you record scores?", dbc.RadioItems(
                            id="ar-scored", options=YES_NO, value=True, inline=True,
                        ), 4),
                        className="mb-3",
                    ),

                    dbc.Button("Next: Enter Ends", id="ar-next-btn", color="primary"),
                ])),
                width=12,
            ),
            className="mb-3",
        ),

        dbc.Row(dbc.Col(html.Div(id="ar-alert"), width=12), className="mb-2"),

        # ── Step 2: ends (revealed after step 1 validates) ─────────────────────────
        dbc.Collapse(
            id="ar-ends-collapse",
            is_open=False,
            children=dbc.Card(dbc.CardBody([
                html.H4("Enter Ends", className="card-title"),

                # Scored: enter ends one at a time
                html.Div(id="ar-scored-section", children=[
                    dbc.Row([
                        _labelled("End scores (space-separated, 'x' for X)", dbc.Input(
                            id="ar-end-input", placeholder="x 10 9 9 8 7",
                            n_submit=0, autoComplete="off",
                        ), 6),
                        dbc.Col(
                            dbc.Button("Add End", id="ar-add-end-btn", color="success",
                                       className="mt-4"),
                            md="auto",
                        ),
                        dbc.Col(
                            dbc.Button("Remove Last End", id="ar-remove-end-btn",
                                       color="secondary", outline=True, className="mt-4"),
                            md="auto",
                        ),
                    ], className="mb-3"),
                    html.Div(id="ar-ends-table", children=render_archery_ends_table([]),
                             className="mb-3"),
                    dbc.Row(
                        _labelled("Were the shots ordered?", dbc.RadioItems(
                            id="ar-shots-ordered", options=YES_NO, value=False, inline=True,
                        ), 4),
                        className="mb-3",
                    ),
                ]),

                # Unscored: just totals
                html.Div(id="ar-unscored-section", children=dbc.Row([
                    _labelled("Number of Ends *", dbc.Input(id="ar-num-ends", type="number", min=0), 3),
                    _labelled("Number of Shots *", dbc.Input(id="ar-num-shots", type="number", min=0), 3),
                ], className="mb-3")),

                html.Hr(),
                dbc.Row([
                    dbc.Col(dbc.Button("Save Round", id="ar-save-btn", color="primary"), md="auto"),
                    dbc.Col(dbc.Button("Cancel", id="ar-cancel-btn", color="secondary", outline=True),
                            md="auto"),
                ]),
            ])),
        ),

        dbc.Row(dbc.Col(html.Div(id="ar-save-alert"), width=12), className="mb-4"),

        dcc.Store(id="ar-ends-store", data=[]),
        dcc.Store(id="ar-refresh-store", data=0),
    ]


# Layout (a function so dropdown options and defaults refresh on each page load)
def layout():
    return dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    html.H2("Archery"),
                    width=12,
                ),
                className="mb-4"
            ),

            *round_entry_section(),

            # Archery Rounds Overview
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.H4("Archery Rounds", className="card-title"),
                            html.Label("Columns to Display"),
                            dcc.Dropdown(
                                id="archery-rounds-columns",
                                options=[{"label": col, "value": col} for col in ARCHERY_ROUND_COLUMNS],
                                value=ARCHERY_ROUND_COLUMNS,
                                multi=True,
                                placeholder="Select columns",
                                className="mb-3",
                            ),
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


# ── Entry form callbacks ────────────────────────────────────────────────────────

def _validate_round_details(is_today, date_str, range_id, scoring_rule_id, distance,
                            riser_id, limb_id, time_start, time_end, cond_mental, cond_env):
    """Return an error message, or None if the round details are valid."""
    if not is_today and not date_str:
        return "Date is required."
    missing = [
        name for name, val in [
            ("Range", range_id), ("Scoring Rule", scoring_rule_id), ("Distance", distance),
            ("Riser", riser_id), ("Limb", limb_id),
        ] if val in (None, "")
    ]
    if missing:
        return f"Required: {', '.join(missing)}."
    for name, t in [("Start time", time_start), ("End time", time_end)]:
        if t and not re.fullmatch(r"\d{4}", t.strip()):
            return f"{name} must be 4 digits (HHMM)."
    for name, c in [("Mental condition", cond_mental), ("Range condition", cond_env)]:
        if c is not None and not 1 <= c <= 10:
            return f"{name} must be between 1 and 10."
    return None


ROUND_DETAIL_STATES = [
    State("ar-is-today", "value"),
    State("ar-date", "date"),
    State("ar-range", "value"),
    State("ar-scoring-rule", "value"),
    State("ar-distance", "value"),
    State("ar-riser", "value"),
    State("ar-limb", "value"),
    State("ar-time-start", "value"),
    State("ar-time-end", "value"),
    State("ar-cond-mental", "value"),
    State("ar-cond-env", "value"),
]


@callback(
    Output("ar-date", "disabled"),
    Input("ar-is-today", "value"),
)
def toggle_archery_date(is_today):
    return is_today


@callback(
    Output("ar-scored-section", "style"),
    Output("ar-unscored-section", "style"),
    Input("ar-scored", "value"),
)
def toggle_scored_sections(scored):
    if scored:
        return {}, {"display": "none"}
    return {"display": "none"}, {}


@callback(
    Output("ar-ends-collapse", "is_open"),
    Output("ar-alert", "children"),
    Input("ar-next-btn", "n_clicks"),
    Input("ar-cancel-btn", "n_clicks"),
    *ROUND_DETAIL_STATES,
    prevent_initial_call=True,
)
def handle_archery_next(_next, _cancel, *details):
    if ctx.triggered_id == "ar-cancel-btn":
        return False, None
    error = _validate_round_details(*details)
    if error:
        return False, dbc.Alert(error, color="warning")
    return True, None


@callback(
    Output("ar-ends-store", "data"),
    Output("ar-ends-table", "children"),
    Output("ar-end-input", "value"),
    Output("ar-save-alert", "children", allow_duplicate=True),
    Input("ar-add-end-btn", "n_clicks"),
    Input("ar-end-input", "n_submit"),
    Input("ar-remove-end-btn", "n_clicks"),
    Input("ar-cancel-btn", "n_clicks"),
    State("ar-end-input", "value"),
    State("ar-ends-store", "data"),
    prevent_initial_call=True,
)
def update_archery_ends(_add, _submit, _remove, _cancel, raw, ends):
    ends = ends or []
    if ctx.triggered_id == "ar-cancel-btn":
        return [], render_archery_ends_table([]), None, None
    if ctx.triggered_id == "ar-remove-end-btn":
        ends = ends[:-1]
        return ends, render_archery_ends_table(ends), raw, None
    try:
        scores = parse_end_scores(raw)
    except ValueError as e:
        return ends, render_archery_ends_table(ends), raw, dbc.Alert(str(e), color="warning")
    ends = ends + [scores]
    return ends, render_archery_ends_table(ends), None, None


@callback(
    Output("ar-save-alert", "children"),
    Output("ar-refresh-store", "data"),
    Output("ar-ends-collapse", "is_open", allow_duplicate=True),
    Output("ar-ends-store", "data", allow_duplicate=True),
    Output("ar-ends-table", "children", allow_duplicate=True),
    Output("ar-num-ends", "value"),
    Output("ar-num-shots", "value"),
    Input("ar-save-btn", "n_clicks"),
    *ROUND_DETAIL_STATES,
    State("ar-target", "value"),
    State("ar-draw-weight", "value"),
    State("ar-arrow", "value"),
    State("ar-arrow-rest", "value"),
    State("ar-sight", "value"),
    State("ar-release-aid", "value"),
    State("ar-flags", "value"),
    State("ar-seconds-per-arrow", "value"),
    State("ar-scored", "value"),
    State("ar-ends-store", "data"),
    State("ar-shots-ordered", "value"),
    State("ar-num-ends", "value"),
    State("ar-num-shots", "value"),
    State("ar-refresh-store", "data"),
    prevent_initial_call=True,
)
def save_archery_round(
    _,
    is_today, date_str, range_id, scoring_rule_id, distance,
    riser_id, limb_id, time_start, time_end, cond_mental, cond_env,
    target_id, draw_weight, arrow_id, arrow_rest_id, sight_id, release_aid_id,
    flags, seconds_per_arrow, scored, ends, shots_ordered, num_ends, num_shots, refresh,
):
    ends = ends or []
    flags = flags or []

    def warn(msg):
        return (dbc.Alert(msg, color="warning"), dash.no_update, True,
                ends, render_archery_ends_table(ends), num_ends, num_shots)

    error = _validate_round_details(
        is_today, date_str, range_id, scoring_rule_id, distance,
        riser_id, limb_id, time_start, time_end, cond_mental, cond_env,
    )
    if error:
        return warn(error)
    if scored and not ends:
        return warn("Add at least one end before saving.")
    if not scored and (num_ends is None or num_shots is None):
        return warn("Number of ends and number of shots are required.")

    round_date = datetime.now() if is_today else datetime.fromisoformat(date_str)
    round_date = datetime(round_date.year, round_date.month, round_date.day)

    try:
        rnd = Round(
            round_date, int(range_id), float(distance),
            int(target_id) if target_id else None,
            "sight" in flags, "clicker" in flags, "stabilisation" in flags,
            int(riser_id), int(limb_id),
            ends if scored else [],
            "hunger" in flags, int(scoring_rule_id),
            start_time=(time_start or "").strip() or None,
            end_time=(time_end or "").strip() or None,
            draw_weight_lb_=float(draw_weight) if draw_weight is not None else None,
            arrow_id_=int(arrow_id) if arrow_id else None,
            arrow_rest_id_=int(arrow_rest_id) if arrow_rest_id else None,
            condition_mental=int(cond_mental) if cond_mental is not None else None,
            condition_env=int(cond_env) if cond_env is not None else None,
            sight_id_=int(sight_id) if sight_id else None,
            release_aid_id_=int(release_aid_id) if release_aid_id else None,
            known_distance_="known_distance" in flags,
            variable_distance_="variable_distance" in flags,
            num_shots_=None if scored else int(num_shots),
            num_ends_=None if scored else int(num_ends),
            seconds_per_arrow_=float(seconds_per_arrow) if seconds_per_arrow else None,
            shots_ordered_=bool(shots_ordered),
        )
        if scored:
            rnd.construct_round(postgres_session)
        else:
            rnd.construct_unscored_round(postgres_session)
        rnd.insert_round(postgres_session)
    except Exception as e:
        postgres_session.rollback()
        return warn(f"Error saving round: {e}")

    if scored:
        msg = (f"Round #{rnd.round_id} saved for {round_date.date()}: "
               f"{rnd.num_ends} ends, {rnd.num_shots} shots, total {rnd.total_score}, "
               f"avg {rnd.avg_shots:.2f}.")
    else:
        msg = (f"Round #{rnd.round_id} saved for {round_date.date()}: "
               f"{rnd.num_ends} ends, {rnd.num_shots} shots (unscored).")
    return (dbc.Alert(msg, color="success", dismissable=True), (refresh or 0) + 1, False,
            [], render_archery_ends_table([]), None, None)


# Callbacks to populate tables
@dash.callback(
    dash.Output("archery-rounds-table", "children"),
    dash.Input("archery-rounds-columns", "value"),
    dash.Input("ar-refresh-store", "data"),
)
def update_archery_rounds(selected_columns, _refresh):
    data = get_archery_rounds()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    # Define numeric columns for proper sorting
    numeric_cols = [
        "ID", "Num Shots", "Avg Shots", "Total Score", "X", "10", "9",
        "Distance (m)", "Seconds/Arrow", "Draw Weight (lb)", "Magnification",
        "StDev Ends", "StDev Shots", "Days Since Practice"
    ]
    display_cols = [col for col in df.columns if not selected_columns or col in selected_columns]
    columns = [
        {"name": col, "id": col, "type": "numeric" if col in numeric_cols else "text"}
        for col in display_cols
    ]
    return DataTable(
        columns=columns,
        data=df.to_dict("records"),
        sort_action="native",
        filter_action="native",
        style_cell={"textAlign": "left", "padding": "10px", "fontSize": "12px"},
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"}
        ],
    )

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
    columns = [
        {"name": "Bow Type", "id": "Bow Type", "type": "text"},
        {"name": "Limb", "id": "Limb", "type": "text"},
        {"name": "Draw Weight (lb)", "id": "Draw Weight (lb)", "type": "numeric"},
        {"name": "Num Shots", "id": "Num Shots", "type": "numeric"},
    ]
    return DataTable(
        columns=columns,
        data=df.to_dict("records"),
        sort_action="native",
        filter_action="native",
        style_cell={"textAlign": "left", "padding": "10px"},
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"}
        ],
    )
