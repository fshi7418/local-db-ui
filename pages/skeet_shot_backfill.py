import dash
from dash import html, dcc, callback, Input, Output, State, no_update
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
from sqlalchemy import text

from models import Session, postgres_session
from models.firearm import SkeetShot

dash.register_page(__name__, path="/skeet-shot-backfill")


# ── Target sequences ────────────────────────────────────────────────────────────
# Each entry is (label, station, house, single_double, pair_order). The order of
# the list is the order the targets are shot, so shot_order is the 1-based index.
# The American option ("OPT") is resolved at save time — it repeats the first
# target missed in the round, or the last target (8L) if the shooter ran 24.

AMERICAN_SEQUENCE = [
    ("1H",  1, "high", "single", None),
    ("1L",  1, "low",  "single", None),
    ("1DH", 1, "high", "double", 1),
    ("1DL", 1, "low",  "double", 2),
    ("2H",  2, "high", "single", None),
    ("2L",  2, "low",  "single", None),
    ("2DH", 2, "high", "double", 1),
    ("2DL", 2, "low",  "double", 2),
    ("3H",  3, "high", "single", None),
    ("3L",  3, "low",  "single", None),
    ("4H",  4, "high", "single", None),
    ("4L",  4, "low",  "single", None),
    ("5H",  5, "high", "single", None),
    ("5L",  5, "low",  "single", None),
    ("6H",  6, "high", "single", None),
    ("6L",  6, "low",  "single", None),
    ("6DL", 6, "low",  "double", 1),
    ("6DH", 6, "high", "double", 2),
    ("7H",  7, "high", "single", None),
    ("7L",  7, "low",  "single", None),
    ("7DL", 7, "low",  "double", 1),
    ("7DH", 7, "high", "double", 2),
    ("8H",  8, "high", "single", None),
    ("8L",  8, "low",  "single", None),
    ("OPT", None, None, None, None),
]

INTERNATIONAL_SEQUENCE = [
    ("1H",  1, "high", "single", None),
    ("1DH", 1, "high", "double", 1),
    ("1DL", 1, "low",  "double", 2),
    ("2H",  2, "high", "single", None),
    ("2DH", 2, "high", "double", 1),
    ("2DL", 2, "low",  "double", 2),
    ("3H",  3, "high", "single", None),
    ("3DH", 3, "high", "double", 1),
    ("3DL", 3, "low",  "double", 2),
    ("4H",  4, "high", "single", None),
    ("4L",  4, "low",  "single", None),
    ("5L",  5, "low",  "single", None),
    ("5DL", 5, "low",  "double", 1),
    ("5DH", 5, "high", "double", 2),
    ("6L",  6, "low",  "single", None),
    ("6DL", 6, "low",  "double", 1),
    ("6DH", 6, "high", "double", 2),
    ("7DL", 7, "low",  "double", 1),
    ("7DH", 7, "high", "double", 2),
    ("4DH", 4, "high", "double", 1),
    ("4DL", 4, "low",  "double", 2),
    ("4DL", 4, "low",  "double", 1),
    ("4DH", 4, "high", "double", 2),
    ("8H",  8, "high", "single", None),
    ("8L",  8, "low",  "single", None),
]

SEQUENCES = {
    "american": AMERICAN_SEQUENCE,
    "international": INTERNATIONAL_SEQUENCE,
}

OPTION_LABEL = "OPT"


def get_sequence(discipline):
    """Return the target sequence for a discipline, or None if unsupported."""
    return SEQUENCES.get((discipline or "").strip().lower())


def cell_id(index):
    """Column id for the shot at 1-based position `index`.

    Labels repeat within a round (ISSF shoots station 4 doubles twice), so the
    position — not the label — is what identifies a column.
    """
    return f"shot-{index}"


# ── Data helpers ────────────────────────────────────────────────────────────────

def get_round_info(round_id):
    try:
        session = Session()
        row = session.execute(text("""
            select sk.id, sk.discipline, sk.num_break, v.visit_date, m."name" as gun
            from skeet_round sk
            join firearm_end e on sk.firearm_end_id = e.id
            join firearm_visit v on e.firearm_visit_id = v.id
            left join firearm_model m on e.firearm_model_id = m.id
            where sk.id = :id
        """), {"id": round_id}).fetchone()
        existing = session.execute(
            text("select count(*) from skeet_shot where skeet_round_id = :id"),
            {"id": round_id},
        ).scalar()
        session.close()
        if not row:
            return None
        return {
            "id": row[0],
            "discipline": row[1],
            "num_break": row[2],
            "visit_date": row[3].strftime("%Y-%m-%d") if row[3] else None,
            "gun": row[4],
            "existing_shots": existing or 0,
        }
    except Exception as e:
        print(f"Error querying skeet round {round_id}: {e}")
        return None


def build_table(sequence):
    columns = [
        {
            "name": label,
            "id": cell_id(i),
            "type": "numeric",
        }
        for i, (label, *_rest) in enumerate(sequence, start=1)
    ]
    data = [{cell_id(i): 1 for i in range(1, len(sequence) + 1)}]
    # highlight a cell as soon as it is set to 0, so misses stand out
    miss_style = [
        {
            "if": {"filter_query": f"{{{cell_id(i)}}} = 0", "column_id": cell_id(i)},
            "backgroundColor": "#f8d7da",
            "fontWeight": "bold",
        }
        for i in range(1, len(sequence) + 1)
    ]
    return DataTable(
        id="ssb-table",
        columns=columns,
        data=data,
        editable=True,
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "center",
            "padding": "6px",
            "minWidth": "52px",
            "width": "52px",
            "maxWidth": "52px",
        },
        style_header={
            "backgroundColor": "rgb(230, 230, 230)",
            "fontWeight": "bold",
            "whiteSpace": "normal",
        },
        style_data_conditional=miss_style,
    )


# ── Layout ──────────────────────────────────────────────────────────────────────

layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H2("Skeet Shot Backfill"), width=12),
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col(
                html.P(
                    "Enter a skeet round ID to load its target sequence, then mark "
                    "each missed target as 0. Every cell starts at 1 (hit).",
                    className="text-muted",
                ),
                width=12,
            ),
        ),
        dbc.Row(
            [
                dbc.Col([
                    html.Label("Skeet Round ID"),
                    dbc.Input(id="ssb-round-id", type="number", min=1, step=1,
                              placeholder="skeet_round.id"),
                ], md=3),
                dbc.Col(
                    dbc.Button("Load Round", id="ssb-load-btn", color="primary"),
                    md=2,
                    className="d-flex align-items-end",
                ),
            ],
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col(html.Div(id="ssb-round-info"), width=12),
            className="mb-3",
        ),
        dcc.Store(id="ssb-round-store"),
        dbc.Collapse(
            id="ssb-entry-collapse",
            is_open=False,
            children=dbc.Card(dbc.CardBody([
                html.H6("Shot-by-shot Result", className="card-title"),
                html.Div(id="ssb-table-container", className="mb-3"),
                dbc.Row([
                    dbc.Col(
                        dbc.Checklist(
                            id="ssb-overwrite",
                            options=[{"label": " Replace existing shots for this round",
                                      "value": "overwrite"}],
                            value=[],
                            switch=True,
                        ),
                        md=6,
                    ),
                ], className="mb-3"),
                dbc.Button("Save Shots", id="ssb-save-btn", color="success"),
            ]), className="bg-light"),
        ),
        dbc.Row(
            dbc.Col(html.Div(id="ssb-save-result", className="mt-3"), width=12),
        ),
    ],
    fluid=True,
)


# ── Callbacks ───────────────────────────────────────────────────────────────────

@callback(
    Output("ssb-round-info", "children"),
    Output("ssb-table-container", "children"),
    Output("ssb-entry-collapse", "is_open"),
    Output("ssb-round-store", "data"),
    Output("ssb-save-result", "children", allow_duplicate=True),
    Input("ssb-load-btn", "n_clicks"),
    State("ssb-round-id", "value"),
    prevent_initial_call=True,
)
def load_round(_, round_id):
    if round_id is None:
        return dbc.Alert("Enter a skeet round ID.", color="warning"), None, False, None, None

    info = get_round_info(int(round_id))
    if info is None:
        return (
            dbc.Alert(f"No skeet round found with ID {int(round_id)}.", color="danger"),
            None, False, None, None,
        )

    sequence = get_sequence(info["discipline"])
    if sequence is None:
        return (
            dbc.Alert(
                f"Round {info['id']} has discipline {info['discipline']!r}, which has "
                f"no defined target sequence. Supported: American, International.",
                color="danger",
            ),
            None, False, None, None,
        )

    details = [
        f"Discipline: {info['discipline']}",
        f"Visit: {info['visit_date']}",
        f"Gun: {info['gun'] or '—'}",
        f"Recorded breaks: {info['num_break'] if info['num_break'] is not None else '—'}",
    ]
    children = [html.Div(" · ".join(details))]
    colour = "info"
    if info["existing_shots"]:
        colour = "warning"
        children.append(html.Div(
            f"This round already has {info['existing_shots']} shot(s) recorded. "
            f"Tick “Replace existing shots” to overwrite them.",
            className="mt-2 fw-bold",
        ))

    store = {"round_id": info["id"], "discipline": info["discipline"]}
    return dbc.Alert(children, color=colour), build_table(sequence), True, store, None


@callback(
    Output("ssb-save-result", "children"),
    Output("ssb-round-info", "children", allow_duplicate=True),
    Input("ssb-save-btn", "n_clicks"),
    State("ssb-table", "data"),
    State("ssb-round-store", "data"),
    State("ssb-overwrite", "value"),
    prevent_initial_call=True,
)
def save_shots(_, table_data, store, overwrite):
    if not store or not table_data:
        return dbc.Alert("Load a round first.", color="warning"), no_update

    round_id = store["round_id"]
    sequence = get_sequence(store["discipline"])
    if sequence is None:
        return dbc.Alert("Unsupported discipline.", color="danger"), no_update

    row = table_data[0]

    # every cell must be 0 or 1
    results = []
    bad = []
    for i, (label, *_rest) in enumerate(sequence, start=1):
        raw = row.get(cell_id(i))
        try:
            value = int(raw)
        except (TypeError, ValueError):
            bad.append(f"{label} (position {i})")
            continue
        if value not in (0, 1):
            bad.append(f"{label} (position {i})")
            continue
        results.append(value)
    if bad:
        return dbc.Alert(
            "Every cell must be 1 (hit) or 0 (miss). Check: " + ", ".join(bad),
            color="danger",
        ), no_update

    info = get_round_info(round_id)
    if info is None:
        return dbc.Alert(f"Skeet round {round_id} no longer exists.", color="danger"), no_update
    if info["existing_shots"] and "overwrite" not in (overwrite or []):
        return dbc.Alert(
            f"Round {round_id} already has {info['existing_shots']} shot(s). "
            f"Tick “Replace existing shots for this round” to overwrite them.",
            color="warning",
        ), no_update

    try:
        deleted = 0
        if info["existing_shots"]:
            deleted = postgres_session.query(SkeetShot).filter(
                SkeetShot.skeet_round_id == round_id
            ).delete(synchronize_session=False)

        option_note = None
        for i, (label, station, house, single_double, pair_order) in enumerate(sequence, start=1):
            if label == OPTION_LABEL:
                # the option repeats the first target missed; a clean 24 means it
                # repeats the last target of the round
                missed = [n for n, hit in enumerate(results[:i - 1], start=1) if hit == 0]
                target_number = missed[0] if missed else i - 1
                _, station, house, single_double, pair_order = sequence[target_number - 1]
                is_option = True
                option_note = (
                    f"Option shot recorded as a repeat of target {target_number} "
                    f"({sequence[target_number - 1][0]})."
                )
            else:
                target_number = i
                is_option = False

            postgres_session.add(SkeetShot(
                skeet_round_id=round_id,
                shot_order=i,
                target_number=target_number,
                station=station,
                house=house,
                single_double=single_double,
                pair_order=pair_order,
                is_option=is_option,
                broken=bool(results[i - 1]),
            ))

        postgres_session.commit()
    except Exception as e:
        postgres_session.rollback()
        return dbc.Alert(f"Error saving shots: {e}", color="danger", dismissable=True), no_update

    total = sum(results)
    lines = [html.Div(f"Saved {len(results)} shots for round {round_id}. Breaks: {total}/{len(results)}.")]
    if deleted:
        lines.append(html.Div(f"Replaced {deleted} previously recorded shot(s)."))
    if option_note:
        lines.append(html.Div(option_note))
    if info["num_break"] is not None and info["num_break"] != total:
        lines.append(html.Div(
            f"Note: skeet_round.num_break is {info['num_break']}, which does not match "
            f"the {total} break(s) entered here. The round total was left unchanged.",
            className="fw-bold",
        ))

    refreshed = get_round_info(round_id)
    details = " · ".join([
        f"Discipline: {refreshed['discipline']}",
        f"Visit: {refreshed['visit_date']}",
        f"Gun: {refreshed['gun'] or '—'}",
        f"Recorded breaks: {refreshed['num_break'] if refreshed['num_break'] is not None else '—'}",
        f"Shots on file: {refreshed['existing_shots']}",
    ])
    return (
        dbc.Alert(lines, color="success", dismissable=True),
        dbc.Alert(details, color="info"),
    )
