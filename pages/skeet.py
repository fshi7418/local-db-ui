import dash
from dash import html, dcc, callback, Input, Output, State, ctx, no_update
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
from sqlalchemy import text

from models import Session, postgres_session
from models.firearm import SkeetShot
from components.clayshooting_nav import clayshooting_header
from components.skeet_targets import (
    SHOT_CELL_STYLE,
    SHOT_HEADER_STYLE,
    build_shot_rows,
    cell_id,
    get_sequence,
    miss_highlight,
    parse_shot_cells,
    shot_columns,
)

dash.register_page(
    __name__,
    path="/clayshooting/skeet",
    redirect_from=["/skeet", "/skeet-shot-backfill"],
)

HIDDEN = {"display": "none"}
SHOWN = {"display": "block"}


def get_skeet_rounds(discipline=None):
    try:
        session = Session()
        query = text("""
            select
                sk.id, v.visit_date, e.id as end_id, sk.discipline, coalesce(sk.sequence, sk.discipline) as sequence, sk.low_gun_start, coalesce(m.short_name, m."name") as gun,
                coalesce(a.short_name, a."name") as ammunition, car.name as cartridge, car.shot_size as shot,
                c1."name" as choke1, c1.constriction as constriction1,
                c2."name" as choke2, c2.constriction as constriction2,
                sk.num_break, sk.remarks
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
            if discipline and row[3] != discipline:
                continue
            data.append({
                "ID": row[0],
                "Visit Date": row[1].strftime("%Y-%m-%d") if row[1] else None,
                "End ID": row[2],
                "Discipline": row[3],
                "Sequence": row[4],
                "Low Gun Start": row[5],
                "Gun": row[6],
                "Ammunition": row[7],
                "Cartridge": row[8],
                "Shot": row[9],
                "Choke 1": row[10],
                "Constriction 1": row[11],
                "Choke 2": row[12],
                "Constriction 2": row[13],
                "Breaks": row[14],
                "Remarks": row[15],
            })
        return data
    except Exception as e:
        print(f"Error querying skeet rounds: {e}")
        return []


def get_round_info(round_id):
    """One round and its shot-by-shot record, keyed by position in the sequence."""
    try:
        session = Session()
        row = session.execute(text("""
            select sk.id, sk.discipline, coalesce(sk.sequence, sk.discipline) as sequence,
                   sk.num_break, v.visit_date
            from skeet_round sk
            join firearm_end e on sk.firearm_end_id = e.id
            join firearm_visit v on e.firearm_visit_id = v.id
            where sk.id = :id
        """), {"id": round_id}).fetchone()
        shots = session.execute(text("""
            select shot_order, target_number, is_option, broken
            from skeet_shot
            where skeet_round_id = :id
            order by shot_order
        """), {"id": round_id}).fetchall()
        session.close()
        if not row:
            return None
        return {
            "id": row[0],
            "discipline": row[1],
            "sequence": row[2],
            "num_break": row[3],
            "visit_date": row[4].strftime("%Y-%m-%d") if row[4] else None,
            "shots": [
                {"shot_order": s[0], "target_number": s[1], "is_option": s[2], "broken": s[3]}
                for s in shots
            ],
        }
    except Exception as e:
        print(f"Error querying skeet round {round_id}: {e}")
        return None


def get_rounds_shots(round_ids):
    """Shot-by-shot records for several rounds: {round id: {shot_order: broken}}."""
    if not round_ids:
        return {}
    try:
        session = Session()
        rows = session.execute(text("""
            select skeet_round_id, shot_order, broken
            from skeet_shot
            where skeet_round_id = any(:ids)
        """), {"ids": list(round_ids)}).fetchall()
        session.close()
    except Exception as e:
        print(f"Error querying skeet shots: {e}")
        return None
    shots = {}
    for round_id, shot_order, broken in rows:
        shots.setdefault(round_id, {})[shot_order] = 1 if broken else 0
    return shots


MULTI_TOTAL_STYLE = {"fontWeight": "bold", "backgroundColor": "rgb(240, 240, 240)"}
MULTI_MISMATCH_STYLE = {"backgroundColor": "#fff3cd", "fontWeight": "bold"}


def render_multi_rounds(rounds, shots):
    """Read-only shot grid for several rounds, one row per round, in the given order.

    Rounds are grouped into consecutive blocks that share a target sequence, since
    American and International sequences have different targets in each column.
    """
    blocks = []
    for r in rounds:
        name = r.get("Sequence")
        if blocks and blocks[-1][0] == name:
            blocks[-1][1].append(r)
        else:
            blocks.append((name, [r]))

    children = []
    for name, block in blocks:
        if len(blocks) > 1:
            children.append(html.H6(f"{name or '—'} sequence", className="mt-3"))
        sequence = get_sequence(name)
        if sequence is None:
            ids = ", ".join(str(r["ID"]) for r in block)
            children.append(html.P(
                f"No target sequence is defined for {name!r} (rounds {ids}).",
                className="text-muted",
            ))
            continue

        n = len(sequence)
        data, style = [], []
        hits_per_col = [0] * n
        recorded_per_col = [0] * n
        for k, r in enumerate(block):
            stored = shots.get(r["ID"], {})
            row = {"Round": r["ID"], "Date": r.get("Visit Date"), "Breaks": r.get("Breaks")}
            for i in range(1, n + 1):
                value = stored.get(i)
                row[cell_id(i)] = "" if value is None else value
                if value is not None:
                    recorded_per_col[i - 1] += 1
                    hits_per_col[i - 1] += value
            hits = sum(stored.get(i, 0) for i in range(1, n + 1))
            recorded = sum(1 for i in range(1, n + 1) if i in stored)
            row["Recorded"] = f"{hits}/{recorded}" if recorded else "none"
            if recorded and r.get("Breaks") is not None and hits != r["Breaks"]:
                style.append({"if": {"row_index": k, "column_id": "Recorded"}, **MULTI_MISMATCH_STYLE})
            data.append(row)

        total = {"Round": "Total", "Date": "", "Breaks": sum(r.get("Breaks") or 0 for r in block)}
        for i in range(n):
            total[cell_id(i + 1)] = f"{hits_per_col[i]}/{recorded_per_col[i]}" if recorded_per_col[i] else ""
        all_hits, all_recorded = sum(hits_per_col), sum(recorded_per_col)
        total["Recorded"] = f"{all_hits}/{all_recorded}" if all_recorded else "none"
        data.append(total)
        style.append({"if": {"row_index": len(data) - 1}, **MULTI_TOTAL_STYLE})

        columns = (
            [{"name": "Round", "id": "Round"}, {"name": "Date", "id": "Date"},
             {"name": "Breaks", "id": "Breaks"}, {"name": "Recorded", "id": "Recorded"}]
            + shot_columns(sequence)
        )
        children.append(DataTable(
            columns=columns,
            data=data,
            style_table={"overflowX": "auto"},
            style_cell=SHOT_CELL_STYLE,
            style_cell_conditional=[
                {"if": {"column_id": c}, "minWidth": "90px", "width": "90px", "maxWidth": "90px"}
                for c in ("Date", "Recorded")
            ],
            style_header=SHOT_HEADER_STYLE,
            style_data_conditional=miss_highlight(sequence) + style,
        ))
    children.append(html.Small(
        "Blank cells have no shot recorded. Recorded = hits / targets on file; it is "
        "highlighted when it differs from the round's Breaks. The Total row counts "
        "hits per target.",
        className="text-muted",
    ))
    return children


def shots_summary(sequence, shots):
    """One line describing a round's stored shots."""
    if not shots:
        return (
            "No shot-by-shot record yet. Every target starts as a hit, and nothing "
            "is saved until you press Save Shots."
        )
    breaks = sum(1 for s in shots if s["broken"])
    summary = [f"{breaks}/{len(shots)} broken"]
    if len(shots) != len(sequence):
        summary.append(
            f"only {len(shots)} of {len(sequence)} targets recorded; the rest show as 1"
        )
    option = next((s for s in shots if s["is_option"]), None)
    if option is not None:
        label = sequence[option["target_number"] - 1][0]
        summary.append(f"option repeated target {option['target_number']} ({label})")
    return " · ".join(summary)


def get_disciplines():
    try:
        session = Session()
        result = session.execute(text("select distinct discipline from skeet_round where discipline is not null order by discipline")).fetchall()
        session.close()
        return [{"label": row[0], "value": row[0]} for row in result]
    except Exception as e:
        print(f"Error querying disciplines: {e}")
        return []


COLUMNS = [
    {"name": "ID",           "id": "ID",           "type": "numeric"},
    {"name": "Visit Date",   "id": "Visit Date",   "type": "text"},
    {"name": "End ID",       "id": "End ID",       "type": "numeric"},
    {"name": "Discipline",   "id": "Discipline",   "type": "text"},
    {"name": "Sequence",     "id": "Sequence",     "type": "text"},
    {"name": "Low Gun Start", "id": "Low Gun Start", "type": "text"},
    {"name": "Gun",          "id": "Gun",          "type": "text"},
    {"name": "Breaks",       "id": "Breaks",       "type": "numeric"},
    {"name": "Choke 1",      "id": "Choke 1",      "type": "text"},
    {"name": "Constriction 1", "id": "Constriction 1", "type": "text"},
    {"name": "Choke 2",      "id": "Choke 2",      "type": "text"},
    {"name": "Constriction 2", "id": "Constriction 2", "type": "text"},
    {"name": "Ammunition",   "id": "Ammunition",   "type": "text"},
    {"name": "Cartridge",    "id": "Cartridge",    "type": "text"},
    {"name": "Shot",         "id": "Shot",         "type": "text"},
    {"name": "Remarks",      "id": "Remarks",      "type": "text"},
]

# Columns available in the picker but hidden until the user asks for them:
# choke names and manufacturers (the constriction is the useful part), everything
# about the second choke, and the end id.
HIDDEN_BY_DEFAULT = {
    "End ID",
    "Choke 1",
    "Choke 2",
}

DEFAULT_COLUMNS = [col["id"] for col in COLUMNS if col["id"] not in HIDDEN_BY_DEFAULT]

layout = dbc.Container(
    [
        clayshooting_header(),
        dbc.Row(
            [
                dbc.Col([
                    html.Label("Filter by Discipline"),
                    dcc.Dropdown(
                        id="skeet-filter-discipline",
                        options=get_disciplines(),
                        placeholder="All disciplines",
                        clearable=True,
                    ),
                ], md=4),
                dbc.Col([
                    html.Label("Date Range"),
                    dcc.DatePickerRange(
                        id="skeet-filter-date-range",
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
                    id="skeet-filter-columns",
                    options=[{"label": col["name"], "value": col["id"]} for col in COLUMNS],
                    value=DEFAULT_COLUMNS,
                    multi=True,
                    placeholder="Select columns",
                ),
            ], md=12),
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col([
                html.P(
                    "Filter with the controls above or the table's column filters, then tick "
                    "rounds to see their shots. One round opens an editable grid; several "
                    "show side by side in the table's order.",
                    className="text-muted small mb-2",
                ),
                html.Div([
                    dbc.Button("Select all filtered", id="skeet-select-all", size="sm",
                               color="secondary", outline=True, className="me-2"),
                    dbc.Button("Clear selection", id="skeet-clear-selection", size="sm",
                               color="secondary", outline=True),
                ], className="mb-2"),
                dbc.Spinner(html.Div(id="skeet-table")),
                DataTable(
                    id="skeet-rounds-table",
                    columns=[],
                    data=[],
                    sort_action="native",
                    filter_action="native",
                    page_action="native",
                    page_size=10,
                    row_selectable="multi",
                    selected_rows=[],
                    style_table={"overflowX": "auto"},
                    style_cell={"textAlign": "left", "padding": "10px"},
                    style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"},
                        {"if": {"state": "selected"}, "backgroundColor": "rgba(0, 116, 217, 0.1)",
                         "border": "1px solid #0074D9"},
                    ],
                ),
            ], width=12),
        ),

        # Shot-by-shot record (shown when rounds are selected). These components stay
        # in the layout permanently because the save callback reads them as State.
        dcc.Store(id="skeet-round-store"),
        dcc.Store(id="skeet-shown-rounds"),
        dbc.Row(
            dbc.Col([
                html.Div(id="skeet-shots-header"),
                html.Div(id="skeet-shots-message"),
                html.Div(id="skeet-multi-shots"),
                html.Div(
                    [
                        DataTable(
                            id="skeet-shots-table",
                            columns=[],
                            data=[],
                            editable=True,
                            style_table={"overflowX": "auto"},
                            style_cell=SHOT_CELL_STYLE,
                            style_header=SHOT_HEADER_STYLE,
                        ),
                        html.Small(id="skeet-shots-summary", className="text-muted"),
                        html.Div(
                            dbc.Checklist(
                                id="skeet-replace-shots",
                                options=[{"label": " Replace existing shots for this round",
                                          "value": "overwrite"}],
                                value=[],
                                switch=True,
                            ),
                            id="skeet-replace-row",
                            className="mt-3",
                            style=HIDDEN,
                        ),
                        dbc.Button("Save Shots", id="skeet-save-shots", color="success", className="mt-3"),
                    ],
                    id="skeet-shots-editor",
                    style=HIDDEN,
                ),
                html.Div(id="skeet-save-result", className="mt-3"),
            ], width=12),
            id="skeet-shots-row",
            style=HIDDEN,
            className="mb-3",
        ),
    ],
    fluid=True,
)


@callback(
    Output("skeet-table", "children"),
    Output("skeet-rounds-table", "columns"),
    Output("skeet-rounds-table", "data"),
    Output("skeet-rounds-table", "selected_rows"),
    Output("skeet-rounds-table", "style_table"),
    Input("skeet-filter-discipline", "value"),
    Input("skeet-filter-date-range", "start_date"),
    Input("skeet-filter-date-range", "end_date"),
    Input("skeet-filter-columns", "value"),
    State("skeet-rounds-table", "selected_rows"),
    State("skeet-rounds-table", "data"),
)
def load_skeet_table(discipline, start_date, end_date, selected_columns, selected_rows, old_data):
    data = get_skeet_rounds(discipline=discipline)
    if start_date:
        data = [r for r in data if r["Visit Date"] and r["Visit Date"] >= start_date]
    if end_date:
        data = [r for r in data if r["Visit Date"] and r["Visit Date"] <= end_date]
    if not data:
        return (html.P("No skeet rounds found.", className="text-muted"),
                [], [], [], {"display": "none"})
    if selected_columns:
        columns = [col for col in COLUMNS if col["id"] in selected_columns]
    else:
        columns = COLUMNS
    # keep the rounds that were selected and are still in the table
    kept_ids = {old_data[i]["ID"] for i in (selected_rows or []) if old_data and i < len(old_data)}
    selected = [i for i, r in enumerate(data) if r["ID"] in kept_ids]
    return None, columns, data, selected, {"overflowX": "auto"}


# Callback: select every round that passes the current filters, or none
@callback(
    Output("skeet-rounds-table", "selected_rows", allow_duplicate=True),
    Input("skeet-select-all", "n_clicks"),
    Input("skeet-clear-selection", "n_clicks"),
    State("skeet-rounds-table", "derived_virtual_indices"),
    prevent_initial_call=True,
)
def select_all_rounds(_all, _clear, virtual_indices):
    if ctx.triggered_id == "skeet-select-all":
        return list(virtual_indices or [])
    return []


# Callback: show the shot-by-shot record of the selected rounds. One round opens the
# editable grid; several open a read-only grid ordered as the table shows them.
@callback(
    Output("skeet-shots-row", "style"),
    Output("skeet-shots-header", "children"),
    Output("skeet-shots-message", "children"),
    Output("skeet-shots-editor", "style"),
    Output("skeet-shots-table", "columns"),
    Output("skeet-shots-table", "data"),
    Output("skeet-shots-table", "style_data_conditional"),
    Output("skeet-shots-summary", "children"),
    Output("skeet-replace-row", "style"),
    Output("skeet-replace-shots", "value"),
    Output("skeet-round-store", "data"),
    Output("skeet-save-result", "children"),
    Output("skeet-multi-shots", "children"),
    Output("skeet-shown-rounds", "data"),
    Input("skeet-rounds-table", "selected_rows"),
    Input("skeet-rounds-table", "derived_virtual_indices"),
    State("skeet-rounds-table", "data"),
    State("skeet-shown-rounds", "data"),
)
def load_skeet_shots(selected_rows, virtual_indices, table_data, shown):
    hidden = (HIDDEN, "", None, HIDDEN, [], [], [], "", HIDDEN, [], None, None, None, [])
    if not selected_rows or not table_data:
        return hidden

    # selected rounds in the order the table shows them (after sorting); rounds
    # hidden by a column filter drop out
    selected = set(selected_rows)
    order = virtual_indices if virtual_indices is not None else range(len(table_data))
    rounds = [table_data[i] for i in order if i in selected and i < len(table_data)]
    if not rounds:
        return hidden
    ids = [r["ID"] for r in rounds]

    # re-sorting or re-filtering without changing what is shown keeps the grid,
    # including any unsaved edits
    if ids == shown:
        return (no_update,) * 14

    if len(rounds) > 1:
        shots = get_rounds_shots(ids)
        header = html.H5(f"{len(rounds)} rounds selected", className="mt-3 mb-2")
        if shots is None:
            multi = dbc.Alert("Could not load the shots for these rounds.", color="danger")
        else:
            multi = render_multi_rounds(rounds, shots)
        message = html.P("Select a single round to edit its shots.", className="text-muted small")
        return (SHOWN, header, message, HIDDEN, [], [], [], "", HIDDEN, [], None, None, multi, ids)

    info = get_round_info(ids[0])
    if info is None:
        return hidden

    discipline = info["discipline"]
    sequence_name = info["sequence"]
    title = discipline or "—"
    if sequence_name != discipline:
        title += f" field, {sequence_name or '—'} sequence"
    header = html.H5(
        f"Round {info['id']} · {title} · {info['visit_date'] or '—'}",
        className="mt-3 mb-2",
    )

    sequence = get_sequence(sequence_name)
    if sequence is None:
        message = html.P(
            f"No target sequence is defined for {sequence_name!r}.",
            className="text-muted",
        )
        return SHOWN, header, message, HIDDEN, [], [], [], "", HIDDEN, [], None, None, None, ids

    # shot_order is the 1-based position in the round's target sequence; a target
    # with nothing on file shows as a hit
    stored = {s["shot_order"]: 1 if s["broken"] else 0 for s in info["shots"]}
    row = {cell_id(i): stored.get(i, 1) for i in range(1, len(sequence) + 1)}

    return (
        SHOWN,
        header,
        None,
        SHOWN,
        shot_columns(sequence),
        [row],
        miss_highlight(sequence),
        shots_summary(sequence, info["shots"]),
        SHOWN if info["shots"] else HIDDEN,
        [],
        {"round_id": info["id"], "sequence": sequence_name},
        None,
        None,
        ids,
    )


# Callback: save the shot-by-shot record for the selected round
@callback(
    Output("skeet-save-result", "children", allow_duplicate=True),
    Output("skeet-shots-summary", "children", allow_duplicate=True),
    Output("skeet-replace-row", "style", allow_duplicate=True),
    Output("skeet-replace-shots", "value", allow_duplicate=True),
    Input("skeet-save-shots", "n_clicks"),
    State("skeet-shots-table", "data"),
    State("skeet-round-store", "data"),
    State("skeet-replace-shots", "value"),
    prevent_initial_call=True,
)
def save_shots(_, table_data, store, overwrite):
    def failed(alert):
        return alert, no_update, no_update, no_update

    if not store or not table_data:
        return failed(dbc.Alert("Select a round first.", color="warning"))

    round_id = store["round_id"]
    sequence = get_sequence(store["sequence"])
    if sequence is None:
        return failed(dbc.Alert("Unsupported sequence.", color="danger"))

    # every cell must be 0 or 1
    results, bad = parse_shot_cells(sequence, table_data[0])
    if bad:
        return failed(dbc.Alert(
            "Every cell must be 1 (hit) or 0 (miss). Check: " + ", ".join(bad),
            color="danger",
        ))

    info = get_round_info(round_id)
    if info is None:
        return failed(dbc.Alert(f"Skeet round {round_id} no longer exists.", color="danger"))
    existing_shots = len(info["shots"])
    if existing_shots and "overwrite" not in (overwrite or []):
        return failed(dbc.Alert(
            f"Round {round_id} already has {existing_shots} shot(s). "
            f"Tick “Replace existing shots for this round” to overwrite them.",
            color="warning",
        ))

    try:
        deleted = 0
        if existing_shots:
            deleted = postgres_session.query(SkeetShot).filter(
                SkeetShot.skeet_round_id == round_id
            ).delete(synchronize_session=False)

        shot_rows, option_note = build_shot_rows(sequence, results)
        for shot_row in shot_rows:
            postgres_session.add(SkeetShot(skeet_round_id=round_id, **shot_row))

        postgres_session.commit()
    except Exception as e:
        postgres_session.rollback()
        return failed(dbc.Alert(f"Error saving shots: {e}", color="danger", dismissable=True))

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
    return (
        dbc.Alert(lines, color="success", dismissable=True),
        shots_summary(sequence, refreshed["shots"] if refreshed else []),
        SHOWN,
        [],
    )
