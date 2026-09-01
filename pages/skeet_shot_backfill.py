import dash
from dash import html, dcc, callback, Input, Output, State, no_update
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
from sqlalchemy import text

from models import Session, postgres_session
from models.firearm import SkeetShot
from components.skeet_targets import (
    OPTION_LABEL,
    SHOT_CELL_STYLE,
    SHOT_HEADER_STYLE,
    cell_id,
    get_sequence,
    miss_highlight,
    shot_columns,
)

dash.register_page(__name__, path="/skeet-shot-backfill")


# ── Data helpers ────────────────────────────────────────────────────────────────

def get_round_info(round_id):
    try:
        session = Session()
        row = session.execute(text("""
            select sk.id, sk.discipline, sk.num_break, v.visit_date, coalesce(m.short_name, m."name") as gun
            from skeet_round sk
            join firearm_end e on sk.firearm_end_id = e.id
            join firearm_visit v on e.firearm_visit_id = v.id
            left join firearm_model m on e.firearm_model_id = m.id
            where sk.id = :id
        """), {"id": round_id}).fetchone()
        shots = session.execute(
            text("""
                select shot_order, broken
                from skeet_shot
                where skeet_round_id = :id
                order by shot_order
            """),
            {"id": round_id},
        ).fetchall()
        session.close()
        if not row:
            return None
        return {
            "id": row[0],
            "discipline": row[1],
            "num_break": row[2],
            "visit_date": row[3].strftime("%Y-%m-%d") if row[3] else None,
            "gun": row[4],
            "existing_shots": len(shots),
            # position in the target sequence -> 1 (hit) / 0 (miss)
            "stored": {s[0]: 1 if s[1] else 0 for s in shots},
        }
    except Exception as e:
        print(f"Error querying skeet round {round_id}: {e}")
        return None


def build_table(sequence, stored=None):
    """Editable one-row table for a round.

    `stored` maps a 1-based sequence position to 1/0 for a round that already
    has a shot-by-shot record; any position it does not cover falls back to 1,
    so a fresh round is an all-hits template.
    """
    stored = stored or {}
    return DataTable(
        id="ssb-table",
        columns=shot_columns(sequence),
        data=[{cell_id(i): stored.get(i, 1) for i in range(1, len(sequence) + 1)}],
        editable=True,
        style_table={"overflowX": "auto"},
        style_cell=SHOT_CELL_STYLE,
        style_header=SHOT_HEADER_STYLE,
        # highlight a cell as soon as it is set to 0, so misses stand out
        style_data_conditional=miss_highlight(sequence),
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
    Output("ssb-overwrite", "value"),
    Input("ssb-load-btn", "n_clicks"),
    State("ssb-round-id", "value"),
    prevent_initial_call=True,
)
def load_round(_, round_id):
    if round_id is None:
        return dbc.Alert("Enter a skeet round ID.", color="warning"), None, False, None, None, []

    info = get_round_info(int(round_id))
    if info is None:
        return (
            dbc.Alert(f"No skeet round found with ID {int(round_id)}.", color="danger"),
            None, False, None, None, [],
        )

    sequence = get_sequence(info["discipline"])
    if sequence is None:
        return (
            dbc.Alert(
                f"Round {info['id']} has discipline {info['discipline']!r}, which has "
                f"no defined target sequence. Supported: American, International.",
                color="danger",
            ),
            None, False, None, None, [],
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
        note = (
            f"Showing the {info['existing_shots']} shot(s) already recorded for this "
            f"round. Tick “Replace existing shots” to save any changes."
        )
        if info["existing_shots"] != len(sequence):
            note += (
                f" Only {info['existing_shots']} of {len(sequence)} targets are on "
                f"file; the rest default to 1."
            )
        children.append(html.Div(note, className="mt-2 fw-bold"))

    store = {"round_id": info["id"], "discipline": info["discipline"]}
    return (
        dbc.Alert(children, color=colour),
        build_table(sequence, info["stored"]),
        True,
        store,
        None,
        [],
    )


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
