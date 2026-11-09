import dash
from dash import dcc, html, callback, Input, Output, State, ctx, no_update
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text
from datetime import datetime

from models import Session, postgres_session
from models.firearm import (
    FirearmVisit, FirearmEnd, TrapRound, TrapShot,
    DoubleTrapRound, DoubleTrapShot, SkeetRound, SkeetShot, FirearmRange,
)
from components.skeet_targets import (
    SHOT_CELL_STYLE,
    SHOT_HEADER_STYLE,
    blank_shot_row,
    build_shot_rows,
    get_sequence,
    miss_highlight,
    parse_shot_cells,
    shot_columns,
)

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
            select m.id, mfr.name || ' – ' || coalesce(m.short_name, m.name)
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
            "select id, coalesce(short_name, name) from firearm_ammunition order by name"
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
                v.id, v.firearm_range_id, v.visit_date, v.time_start, v.time_end,
                rng.name, rng.address_street, rng.address_city, rng.address_province, rng.address_country
            from firearm_visit v, firearm_range rng
            where v.firearm_range_id = rng.id
            order by v.visit_date desc, v.id desc
        """)).fetchall()
        session.close()
        return [
            {
                "Visit ID": r[0],
                "Range ID": r[1],
                "Date": str(r[2]),
                "Start": r[3],
                "End": r[4],
                "Range": r[5],
                "Street": r[6],
                "City": r[7],
                "Province": r[8],
                "Country": r[9],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"Error querying visits: {e}")
        return []


VISIT_END_COLUMNS = [
    "End ID", "Firearm", "Cartridge", "Ammunition", "Shots", "Scored", "Distance (m)",
    "Target", "Sight", "Sight Type", "Stance", "Hands", "Stabilisation Pts", "Remarks",
]
VISIT_END_DEFAULT_COLUMNS = ["End ID", "Firearm", "Cartridge", "Ammunition", "Shots", "Target", "Remarks"]


def get_visit_ends(visit_id):
    """Ends of one visit, with names in place of the ids they reference."""
    try:
        session = Session()
        rows = session.execute(text("""
            select
                e.id,
                coalesce(m.short_name, m.name) as firearm,
                coalesce(car.short_name, car.name) as cartridge,
                coalesce(a.short_name, a.name) as ammunition,
                e.quantity, e.shots_scored, e.distance_m,
                t.target_name, s.name as sight, s.type as sight_type,
                e.stance, e.supporting_hands, e.points_of_stabilisation,
                e.remarks, e.firearm_target_id, t.type
            from firearm_end e
            left join firearm_model m on m.id = e.firearm_model_id
            left join firearm_cartridge car on car.id = e.firearm_cartridge_id
            left join firearm_ammunition a on a.id = e.firearm_ammunition_id
            left join firearm_target t on t.id = e.firearm_target_id
            left join firearm_sight s on s.id = e.firearm_sight_id
            where e.firearm_visit_id = :visit_id
            order by e.id
        """), {"visit_id": visit_id}).fetchall()
        session.close()
    except Exception as e:
        print(f"Error querying visit ends: {e}")
        return None
    return [
        {
            "End ID": r[0],
            "Firearm": r[1],
            "Cartridge": r[2],
            "Ammunition": r[3],
            "Shots": r[4],
            "Scored": r[5],
            "Distance (m)": r[6],
            "Target": r[7],
            "Sight": r[8],
            "Sight Type": r[9],
            "Stance": r[10],
            "Hands": r[11],
            "Stabilisation Pts": r[12],
            "Remarks": r[13],
            # not displayed; used to pick the shot table when the end is selected
            "_target_id": r[14],
            "_target_type": r[15],
        }
        for r in rows
    ]


# Which table holds an end's shot-by-shot record depends on its target. Any target
# not listed here keeps its shots in firearm_shot.
TRAP_TARGET_IDS = {16, 18, 19, 25, 26}     # trap_round -> trap_shot
DOUBLE_TRAP_TARGET_IDS = {22}              # double_trap_round -> double_trap_shot
SKEET_TARGET_IDS = {21, 23, 24, 27, 28}    # skeet_round -> skeet_shot


def shot_source(target_id):
    if target_id in TRAP_TARGET_IDS:
        return "trap"
    if target_id in DOUBLE_TRAP_TARGET_IDS:
        return "double_trap"
    if target_id in SKEET_TARGET_IDS:
        return "skeet"
    return "firearm"


def _query(session, sql, **params):
    return session.execute(text(sql), params).fetchall()


def get_firearm_shots(session, end_id):
    """firearm_shot rows for an end: (score, is_x, num_shots), best score first."""
    return _query(session, """
        select score, is_x, num_shots from firearm_shot
        where firearm_end_id = :end_id
        order by score desc nulls last, is_x desc nulls last, id
    """, end_id=end_id)


def get_end_shots(end_id, target_id):
    """The shot-by-shot record of one end, read from the table its target uses."""
    source = shot_source(target_id)
    try:
        session = Session()
        result = {"source": source, "round": None, "shots": [], "fallback": []}
        if source in ("trap", "double_trap"):
            round_table, shot_table = f"{source}_round", f"{source}_shot"
            rnd = _query(session, f"""
                select id, discipline, num_break, starting_station
                from {round_table} where firearm_end_id = :end_id
            """, end_id=end_id)
            if rnd:
                result["round"] = dict(zip(("id", "discipline", "num_break", "starting_station"), rnd[0]))
                result["shots"] = _query(session, f"""
                    select station, num_break from {shot_table}
                    where {round_table}_id = :round_id order by id
                """, round_id=rnd[0][0])
        elif source == "skeet":
            rnd = _query(session, """
                select id, discipline, coalesce(sequence, discipline), num_break
                from skeet_round where firearm_end_id = :end_id
            """, end_id=end_id)
            if rnd:
                result["round"] = dict(zip(("id", "discipline", "sequence", "num_break"), rnd[0]))
                result["shots"] = _query(session, """
                    select shot_order, broken from skeet_shot
                    where skeet_round_id = :round_id order by shot_order
                """, round_id=rnd[0][0])
        else:
            result["shots"] = get_firearm_shots(session, end_id)
        # some older clay ends only have a hit/miss tally in firearm_shot
        if source != "firearm" and not result["shots"]:
            result["fallback"] = get_firearm_shots(session, end_id)
        session.close()
        return result
    except Exception as e:
        print(f"Error querying shots for end {end_id}: {e}")
        return None


_SHOT_TABLE_STYLE = dict(
    style_table={"overflowX": "auto"},
    style_cell=SHOT_CELL_STYLE,
    style_header=SHOT_HEADER_STYLE,
)


def render_station_shots(round_info, shots):
    """Trap and double trap: breaks at each station."""
    row = {f"st-{i}": s[1] for i, s in enumerate(shots)}
    row["total"] = sum(s[1] or 0 for s in shots)
    columns = [{"name": f"Station {s[0]}", "id": f"st-{i}"} for i, s in enumerate(shots)]
    columns.append({"name": "Total", "id": "total"})
    return DataTable(
        columns=columns, data=[row],
        style_data_conditional=[{"if": {"column_id": "total"}, "fontWeight": "bold"}],
        **{**_SHOT_TABLE_STYLE, "style_cell": {**SHOT_CELL_STYLE, "minWidth": "80px",
                                              "width": "80px", "maxWidth": "80px"}},
    )


def render_skeet_shots(round_info, shots):
    sequence = get_sequence(round_info["sequence"])
    if sequence is None:
        return html.P(f"No target sequence is defined for {round_info['sequence']!r}.",
                      className="text-muted")
    stored = {s[0]: 1 if s[1] else 0 for s in shots}
    row = {f"shot-{i}": stored.get(i, "") for i in range(1, len(sequence) + 1)}
    return DataTable(
        columns=shot_columns(sequence), data=[row],
        style_data_conditional=miss_highlight(sequence),
        **_SHOT_TABLE_STYLE,
    )


def render_firearm_shots(shots, target_type):
    """firearm_shot is a tally: how many shots landed on each score."""
    binary = target_type == "Binary"
    data = []
    for score, is_x, num_shots in shots:
        if binary:
            label = {1: "Hit", 0: "Miss"}.get(score, score)
        else:
            label = "X" if is_x else score
        data.append({"Score": label, "Shots": num_shots,
                     "Points": (score or 0) * (num_shots or 0)})
    total_shots = sum(d["Shots"] or 0 for d in data)
    total = {"Score": "Total", "Shots": total_shots, "Points": sum(d["Points"] for d in data)}
    columns = [{"name": "Result" if binary else "Score", "id": "Score"}, {"name": "Shots", "id": "Shots"}]
    if not binary:
        columns.append({"name": "Points", "id": "Points"})
        # share of shots at or above each score
        running = 0
        for d in data:
            running += d["Shots"] or 0
            d["Cumulative %"] = running / total_shots if total_shots else 0
        columns.append({"name": "At or Above", "id": "Cumulative %", "type": "numeric",
                        "format": {"specifier": ".0%"}})
    return DataTable(
        columns=columns, data=data + [total],
        style_table={"maxWidth": "420px"},
        style_cell={"textAlign": "center", "padding": "6px"},
        style_header=SHOT_HEADER_STYLE,
        style_data_conditional=[{"if": {"row_index": len(data)}, "fontWeight": "bold",
                                 "backgroundColor": "rgb(240, 240, 240)"}],
    )


SOURCE_LABELS = {
    "trap": "trap_shot", "double_trap": "double_trap_shot",
    "skeet": "skeet_shot", "firearm": "firearm_shot",
}
ROUND_LABELS = {"trap": "Trap round", "double_trap": "Double trap round", "skeet": "Skeet round"}


def render_end_shots(end):
    record = get_end_shots(end["End ID"], end.get("_target_id"))
    heading = html.H6(f"End #{end['End ID']} – {end.get('Target') or 'no target'}", className="mt-3")
    if record is None:
        return [heading, dbc.Alert("Could not load the shots for this end.", color="danger")]
    source, rnd, shots = record["source"], record["round"], record["shots"]
    note = html.Small(f"From {SOURCE_LABELS[source]}.", className="text-muted d-block mt-1")

    if source == "firearm":
        if not shots:
            return [heading, html.P("No shots recorded in firearm_shot.", className="text-muted")]
        return [heading, render_firearm_shots(shots, end.get("_target_type")), note]

    parts = [heading]
    if rnd is None:
        parts.append(html.P(f"No {source}_round row links to this end.", className="text-muted"))
    else:
        info = [f"{ROUND_LABELS[source]} #{rnd['id']}"]
        if rnd.get("discipline"):
            info.append(rnd["discipline"])
        if source == "skeet" and rnd.get("sequence") != rnd.get("discipline"):
            info.append(f"{rnd.get('sequence') or '—'} sequence")
        if rnd.get("starting_station") is not None:
            info.append(f"started at station {rnd['starting_station']}")
        if rnd.get("num_break") is not None:
            info.append(f"{rnd['num_break']} breaks")
        parts.append(html.P(" · ".join(info), className="mb-2"))
        if shots:
            render = render_skeet_shots if source == "skeet" else render_station_shots
            parts += [render(rnd, shots), note]
        else:
            parts.append(html.P(f"No shot-by-shot record in {SOURCE_LABELS[source]}.",
                                className="text-muted"))
    if record["fallback"]:
        parts += [
            html.P("firearm_shot has a tally for this end:", className="mt-3 mb-1"),
            render_firearm_shots(record["fallback"], end.get("_target_type")),
        ]
    return parts


def get_ammunition_data():
    try:
        session = Session()
        rows = session.execute(text("""
            select
                a.id as ammunition_id, coalesce(a.short_name, a.name) as ammunition_name, mfr.name as manufacturer,
                c.id as cartridge_id, c.name as cartridge_name, c.shot_size, c.shot_load_oz, c.shot_load_g, c.shot_material,
                a.muzzle_velocity_fps, a.weight_grain
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
                "Muzzle Velocity (fps)": r[9],
                "Weight (grain)": r[10],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"Error querying ammunition data: {e}")
        return []


def get_cartridges_data():
    try:
        session = Session()
        rows = session.execute(text("""
            select
                id, name, strike_type, shot_size, shot_material, shot_load_oz, shot_load_g,
                diameter_in_base, diameter_mm_base, diameter_in_bullet, diameter_mm_bullet,
                length_in_case, length_mm_case
            from firearm_cartridge
        """)).fetchall()
        session.close()
        return [
            {
                "ID": r[0],
                "Name": r[1],
                "Strike Type": r[2],
                "Shot Size": r[3],
                "Shot Material": r[4],
                "Load (oz)": r[5],
                "Load (g)": r[6],
                "Base Dia (in)": r[7],
                "Base Dia (mm)": r[8],
                "Bullet Dia (in)": r[9],
                "Bullet Dia (mm)": r[10],
                "Case Length (in)": r[11],
                "Case Length (mm)": r[12],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"Error querying cartridges data: {e}")
        return []


# ── Stats helpers ───────────────────────────────────────────────────────────────

def get_shots_by_model():
    try:
        session = Session()
        query = text("""
            select m.name as manufacturer, coalesce(model.short_name, model.name) as model, sum(e.quantity) as num_shots
            from firearm_end e, firearm_model model, firearm_manufacturer m
            where e.firearm_model_id = model.id
            and model.firearm_manufacturer_id = m.id
            and e.quantity is not null
            group by m.name, coalesce(model.short_name, model.name)
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
            select coalesce(a.short_name, a.name) as ammunition, max(m.name) as manufacturer, max(c.name) as cartridge, a.casing, a.tip, a.muzzle_velocity_fps, a.weight_grain, max(c.shot_size) as shot_size, max(c.shot_load_oz) as shot_load_oz, max(c.shot_load_g) as shot_load_g, sum(e.quantity) as num_shots
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
                "Shot Size": r[7],
                "Load (oz)": r[8],
                "Load (g)": r[9],
                "Num Shots": int(r[10]) if r[10] else 0,
            }
            for r in result
        ]
    except Exception as e:
        print(f"Error querying shots by ammunition: {e}")
        return []


SHOTS_BY_AMMUNITION_COLUMNS = [
    "Ammunition", "Manufacturer", "Cartridge", "Casing", "Tip",
    "Muzzle Velocity (fps)", "Weight (grain)", "Shot Size", "Load (oz)",
    "Load (g)", "Num Shots",
]

CARTRIDGE_COLUMNS = [
    "ID", "Name", "Strike Type", "Shot Size", "Shot Material",
    "Load (oz)", "Load (g)", "Base Dia (in)", "Base Dia (mm)",
    "Bullet Dia (in)", "Bullet Dia (mm)", "Case Length (in)", "Case Length (mm)",
]

SHOTS_BY_CARTRIDGE_COLUMNS = [
    "Cartridge", "Shot Size", "Num Shots", "Load (oz)", "Load (g)",
]

AMMUNITION_COLUMNS = [
    "ID", "Ammunition", "Manufacturer", "Cartridge ID", "Cartridge",
    "Shot Size", "Load (oz)", "Load (g)", "Shot Material",
    "Muzzle Velocity (fps)", "Weight (grain)",
]


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
    {"label": "American (NSSA)", "value": "American"},
]

# The target order shot; an American field can shoot the International sequence
SKEET_SEQUENCE_OPTIONS = [
    {"label": "International", "value": "International"},
    {"label": "American", "value": "American"},
]

DOUBLE_TRAP_STYLE_OPTIONS = [
    {"label": "International", "value": "International"},
    {"label": "American (ATA)", "value": "American"},
]

# End form fields as (component id, blank value), in the order add_end receives them
_END_FIELDS = [
    ("fe-model", None), ("fe-ammo-type", "ammo"), ("fe-ammo", None), ("fe-cartridge", None),
    ("fe-quantity", None), ("fe-dist-unit", "yd"), ("fe-distance", None),
    ("fe-target", None), ("fe-shots-scored", None), ("fe-pts-stab", None), ("fe-support-hands", None),
    ("fe-sight", None), ("fe-stance", None), ("fe-remarks", None),
    ("fe-is-trap", False), ("fe-trap-dist-unit", "yd"), ("fe-trap-distance", None), ("fe-trap-style", None),
    ("fe-trap-num-break", None), ("fe-trap-start-station", None),
    ("fe-trap-choke1", None), ("fe-trap-choke2", None), ("fe-trap-by-station", False),
    *[(f"fe-station-{i}", None) for i in range(1, 6)], ("fe-trap-remarks", None),
    ("fe-is-skeet", False), ("fe-skeet-discipline", None), ("fe-skeet-sequence", None),
    ("fe-skeet-num-break", None),
    ("fe-skeet-choke1", None), ("fe-skeet-choke2", None), ("fe-skeet-low-gun-start", False),
    ("fe-skeet-remarks", None), ("fe-skeet-by-shot", False),
    ("fe-is-double-trap", False), ("fe-dt-dist-unit", "yd"), ("fe-dt-distance", None), ("fe-dt-style", None),
    ("fe-dt-num-break", None), ("fe-dt-start-station", None),
    ("fe-dt-choke1", None), ("fe-dt-choke2", None), ("fe-dt-by-station", False),
    *[(f"fe-dt-station-{i}", None) for i in range(1, 6)], ("fe-dt-remarks", None),
]

_RESET_END = tuple(blank for _, blank in _END_FIELDS)
_KEEP_END = (dash.no_update,) * len(_END_FIELDS)

# Per-end results that are cleared after each end; every other field carries over to the next end
_CLEAR_AFTER_END = {
    "fe-remarks",
    "fe-trap-num-break", *[f"fe-station-{i}" for i in range(1, 6)], "fe-trap-remarks",
    "fe-skeet-num-break", "fe-skeet-remarks",
    "fe-dt-num-break", *[f"fe-dt-station-{i}" for i in range(1, 6)], "fe-dt-remarks",
}

_END_FIELD_OUTPUTS = [Output(fid, "value", allow_duplicate=True) for fid, _ in _END_FIELDS]


# ── Layout ──────────────────────────────────────────────────────────────────────

# A function, so Dash rebuilds the layout on every page load and the dropdowns
# pick up rows added to the database since the app started.
def layout():
    return dbc.Container(
        [
            dbc.Row(dbc.Col(html.H2("Firearms"), width=12), className="mb-4"),

            # ── Table of contents ─────────────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    dbc.Card(dbc.CardBody([
                        html.H5("On this page", className="card-title"),
                        html.Ul(
                            [
                                html.Li(html.A(label, href=f"#{anchor}", className="text-decoration-none"))
                                for label, anchor in [
                                    ("Add Firearm Visit", "section-add-visit"),
                                    ("Add End", "section-add-end"),
                                    ("Visits", "section-visits"),
                                    ("Shots by Model", "section-shots-by-model"),
                                    ("Ammunition", "section-ammunition"),
                                    ("Shots by Ammunition", "section-shots-by-ammunition"),
                                    ("Cartridges", "section-cartridges"),
                                    ("Shots by Cartridge", "section-shots-by-cartridge"),
                                ]
                            ],
                            className="mb-0",
                        ),
                    ])),
                    width=12,
                ),
                className="mb-4",
            ),

            # ── Visit form ────────────────────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    dbc.Card(dbc.CardBody([
                        html.H4("Add Firearm Visit", className="card-title", id="section-add-visit"),

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
                    html.H4("Add End", className="card-title", id="section-add-end"),
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

                    # Remarks
                    dbc.Row(
                        dbc.Col([
                            html.Label("Remarks (optional)"),
                            dbc.Textarea(
                                id="fe-remarks",
                                placeholder="Free-form notes about this end",
                                style={"height": "80px"},
                            ),
                        ], md=8),
                        className="mb-3",
                    ),

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
                                    html.Label("Choke 1 (optional)"),
                                    dcc.Dropdown(
                                        id="fe-trap-choke1",
                                        options=get_shotgun_chokes(),
                                        placeholder="Select choke",
                                    ),
                                ], md=5),
                                dbc.Col([
                                    html.Label("Choke 2 (optional)"),
                                    dcc.Dropdown(
                                        id="fe-trap-choke2",
                                        options=get_shotgun_chokes(),
                                        placeholder="Select choke",
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
                            dbc.Row(
                                dbc.Col([
                                    html.Label("Remarks (optional)"),
                                    dbc.Textarea(
                                        id="fe-trap-remarks",
                                        placeholder="Free-form notes about this trap round",
                                        style={"height": "80px"},
                                    ),
                                ], md=10),
                                className="mb-3 mt-3",
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
                                    html.Label("Sequence (defaults to discipline)"),
                                    dcc.Dropdown(
                                        id="fe-skeet-sequence",
                                        options=SKEET_SEQUENCE_OPTIONS,
                                        placeholder="Same as discipline",
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
                            dbc.Row(
                                dbc.Col([
                                    html.Label("Remarks (optional)"),
                                    dbc.Textarea(
                                        id="fe-skeet-remarks",
                                        placeholder="Free-form notes about this skeet round",
                                        style={"height": "80px"},
                                    ),
                                ], md=10),
                                className="mb-3",
                            ),
                            dbc.Row(
                                dbc.Col([
                                    html.Label("Record shot-by-shot?"),
                                    dbc.RadioItems(
                                        id="fe-skeet-by-shot",
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
                                id="fe-skeet-shots-collapse",
                                is_open=False,
                                children=[
                                    html.Small(id="fe-skeet-shots-hint", className="text-muted"),
                                    DataTable(
                                        id="fe-skeet-shots-table",
                                        columns=[],
                                        data=[],
                                        editable=True,
                                        style_table={"overflowX": "auto"},
                                        style_cell=SHOT_CELL_STYLE,
                                        style_header=SHOT_HEADER_STYLE,
                                    ),
                                ],
                            ),
                        ]), className="bg-light"),
                    ),

                    # Double trap round toggle
                    dbc.Row(
                        dbc.Col([
                            html.Label("Is this a Double Trap Round?"),
                            dbc.RadioItems(
                                id="fe-is-double-trap",
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

                    # Double trap round details (collapsible)
                    dbc.Collapse(
                        id="fe-double-trap-collapse",
                        is_open=False,
                        children=dbc.Card(dbc.CardBody([
                            html.H6("Double Trap Round Details"),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Distance Unit"),
                                    dbc.RadioItems(
                                        id="fe-dt-dist-unit",
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
                                    dbc.Input(id="fe-dt-distance", type="number", min=0),
                                ], md=2),
                                dbc.Col([
                                    html.Label("Style"),
                                    dcc.Dropdown(
                                        id="fe-dt-style",
                                        options=DOUBLE_TRAP_STYLE_OPTIONS,
                                        placeholder="Select style",
                                    ),
                                ], md=3),
                                dbc.Col([
                                    html.Label("Num Breaks (optional)"),
                                    dbc.Input(id="fe-dt-num-break", type="number", min=0),
                                ], md=2),
                                dbc.Col([
                                    html.Label("Starting Station (optional)"),
                                    dbc.Input(id="fe-dt-start-station", type="number", min=1, max=5),
                                ], md=2),
                            ], className="mb-3"),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Choke 1 (optional)"),
                                    dcc.Dropdown(
                                        id="fe-dt-choke1",
                                        options=get_shotgun_chokes(),
                                        placeholder="Select choke",
                                    ),
                                ], md=5),
                                dbc.Col([
                                    html.Label("Choke 2 (optional)"),
                                    dcc.Dropdown(
                                        id="fe-dt-choke2",
                                        options=get_shotgun_chokes(),
                                        placeholder="Select choke",
                                    ),
                                ], md=5),
                            ], className="mb-3"),
                            dbc.Row(
                                dbc.Col([
                                    html.Label("Breaks by station?"),
                                    dbc.RadioItems(
                                        id="fe-dt-by-station",
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
                                id="fe-dt-station-collapse",
                                is_open=False,
                                children=dbc.Row([
                                    dbc.Col([
                                        html.Label(f"Station {i}"),
                                        dbc.Input(
                                            id=f"fe-dt-station-{i}",
                                            type="number",
                                            min=0,
                                            placeholder="Breaks",
                                        ),
                                    ], md=2)
                                    for i in range(1, 6)
                                ]),
                            ),
                            dbc.Row(
                                dbc.Col([
                                    html.Label("Remarks (optional)"),
                                    dbc.Textarea(
                                        id="fe-dt-remarks",
                                        placeholder="Free-form notes about this double trap round",
                                        style={"height": "80px"},
                                    ),
                                ], md=10),
                                className="mb-3 mt-3",
                            ),
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
                        html.H4("Visits", className="card-title", id="section-visits"),
                        html.P("Select a visit to see its ends.", className="text-muted small"),
                        html.Div(id="visits-table"),
                        DataTable(
                            id="visits-datatable",
                            columns=[],
                            data=[],
                            row_selectable="single",
                            selected_rows=[],
                            sort_action="native",
                            filter_action="native",
                            page_action="native",
                            page_size=10,
                            style_table={"overflowX": "auto"},
                            style_cell={"textAlign": "left", "padding": "10px"},
                            style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
                            style_data_conditional=[
                                {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"},
                                {"if": {"state": "selected"}, "backgroundColor": "rgb(220, 235, 255)",
                                 "border": "1px solid rgb(120, 160, 220)"},
                            ],
                        ),
                        html.Div(
                            [
                                html.Label("Columns to Display"),
                                dcc.Dropdown(
                                    id="visit-ends-columns",
                                    options=[{"label": c, "value": c} for c in VISIT_END_COLUMNS],
                                    value=VISIT_END_DEFAULT_COLUMNS,
                                    multi=True,
                                    placeholder="Select columns",
                                ),
                            ],
                            id="visit-ends-columns-wrapper",
                            className="mt-3",
                            style={"display": "none"},
                        ),
                        html.Div(id="visit-ends-detail", className="mt-3"),
                        DataTable(
                            id="visit-ends-datatable",
                            columns=[],
                            data=[],
                            row_selectable="single",
                            selected_rows=[],
                            sort_action="native",
                            page_action="native",
                            page_size=30,
                            style_table={"display": "none"},
                            style_cell={"textAlign": "left", "padding": "8px"},
                            style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
                            style_data_conditional=[
                                {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"},
                                {"if": {"state": "selected"}, "backgroundColor": "rgb(220, 235, 255)",
                                 "border": "1px solid rgb(120, 160, 220)"},
                            ],
                        ),
                        html.Div(id="visit-end-shots"),
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
                        html.H4("Shots by Model", className="card-title", id="section-shots-by-model"),
                        html.Div(id="shots-by-model-table"),
                    ])),
                    width=12,
                ),
                className="mb-4",
            ),

            dbc.Row(
                dbc.Col(
                    dbc.Card(dbc.CardBody([
                        html.H4("Ammunition", className="card-title", id="section-ammunition"),
                        html.Label("Columns to Display"),
                        dcc.Dropdown(
                            id="ammunition-columns",
                            options=[{"label": col, "value": col} for col in AMMUNITION_COLUMNS],
                            value=AMMUNITION_COLUMNS,
                            multi=True,
                            placeholder="Select columns",
                            className="mb-3",
                        ),
                        html.Div(id="ammunition-table"),
                    ])),
                    width=12,
                ),
                className="mb-4",
            ),

            dbc.Row(
                dbc.Col(
                    dbc.Card(dbc.CardBody([
                        html.H4("Shots by Ammunition", className="card-title", id="section-shots-by-ammunition"),
                        html.Label("Columns to Display"),
                        dcc.Dropdown(
                            id="shots-by-ammunition-columns",
                            options=[{"label": col, "value": col} for col in SHOTS_BY_AMMUNITION_COLUMNS],
                            value=SHOTS_BY_AMMUNITION_COLUMNS,
                            multi=True,
                            placeholder="Select columns",
                            className="mb-3",
                        ),
                        html.Div(id="shots-by-ammunition-table"),
                    ])),
                    width=12,
                ),
                className="mb-4",
            ),

            dbc.Row(
                dbc.Col(
                    dbc.Card(dbc.CardBody([
                        html.H4("Cartridges", className="card-title", id="section-cartridges"),
                        html.Label("Columns to Display"),
                        dcc.Dropdown(
                            id="cartridges-columns",
                            options=[{"label": col, "value": col} for col in CARTRIDGE_COLUMNS],
                            value=CARTRIDGE_COLUMNS,
                            multi=True,
                            placeholder="Select columns",
                            className="mb-3",
                        ),
                        html.Div(id="cartridges-table"),
                    ])),
                    width=12,
                ),
                className="mb-4",
            ),

            dbc.Row(
                dbc.Col(
                    dbc.Card(dbc.CardBody([
                        html.H4("Shots by Cartridge", className="card-title", id="section-shots-by-cartridge"),
                        html.Label("Columns to Display"),
                        dcc.Dropdown(
                            id="shots-by-cartridge-columns",
                            options=[{"label": col, "value": col} for col in SHOTS_BY_CARTRIDGE_COLUMNS],
                            value=SHOTS_BY_CARTRIDGE_COLUMNS,
                            multi=True,
                            placeholder="Select columns",
                            className="mb-3",
                        ),
                        html.Div(id="shots-by-cartridge-table"),
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
    *_END_FIELD_OUTPUTS,
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
        return (False, None, None, None, [], render_ends_table([])) + _RESET_END

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
        return (True, visit.id, alert, badge, [], render_ends_table([])) + _RESET_END

    except Exception as e:
        postgres_session.rollback()
        return (
            False, None,
            dbc.Alert(f"Error creating visit: {e}", color="danger", dismissable=True),
            None, [], render_ends_table([]),
        ) + _KEEP_END


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
    Output("fe-double-trap-collapse", "is_open"),
    Output("fe-is-trap", "value"),
    Output("fe-is-skeet", "value"),
    Output("fe-is-double-trap", "value"),
    Input("fe-is-trap", "value"),
    Input("fe-is-skeet", "value"),
    Input("fe-is-double-trap", "value"),
)
def toggle_trap_skeet(is_trap, is_skeet, is_double_trap):
    # An end can only be one of: trap, skeet, double trap.
    if ctx.triggered_id == "fe-is-trap" and is_trap:
        is_skeet = is_double_trap = False
    elif ctx.triggered_id == "fe-is-skeet" and is_skeet:
        is_trap = is_double_trap = False
    elif ctx.triggered_id == "fe-is-double-trap" and is_double_trap:
        is_trap = is_skeet = False
    return (
        bool(is_trap), bool(is_skeet), bool(is_double_trap),
        is_trap, is_skeet, is_double_trap,
    )


@callback(
    Output("fe-station-collapse", "is_open"),
    Input("fe-trap-by-station", "value"),
)
def toggle_stations(by_station):
    return bool(by_station)


@callback(
    Output("fe-dt-station-collapse", "is_open"),
    Input("fe-dt-by-station", "value"),
)
def toggle_dt_stations(by_station):
    return bool(by_station)


@callback(
    Output("fe-skeet-shots-collapse", "is_open"),
    Output("fe-skeet-shots-hint", "children"),
    Output("fe-skeet-shots-table", "columns"),
    Output("fe-skeet-shots-table", "data"),
    Output("fe-skeet-shots-table", "style_data_conditional"),
    Input("fe-skeet-by-shot", "value"),
    Input("fe-skeet-discipline", "value"),
    Input("fe-skeet-sequence", "value"),
    State("fe-skeet-shots-table", "columns"),
)
def update_skeet_shots_table(by_shot, discipline, sequence_name, current_columns):
    sequence = get_sequence(sequence_name or discipline)
    if sequence is None:
        hint = "Select a discipline to load the targets."
        return bool(by_shot), hint, [], [], []

    hint = f"{sequence_name or discipline} sequence. Every target starts at 1 (hit); set misses to 0."
    columns = shot_columns(sequence)
    # keep what has been entered unless the target sequence actually changed
    if columns == current_columns:
        return bool(by_shot), hint, no_update, no_update, no_update
    return bool(by_shot), hint, columns, [blank_shot_row(sequence)], miss_highlight(sequence)


@callback(
    Output("fe-alert", "children"),
    Output("fe-ends-store", "data"),
    Output("fe-ends-table", "children"),
    *_END_FIELD_OUTPUTS,
    Output("fe-skeet-shots-table", "data", allow_duplicate=True),
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
    State("fe-remarks", "value"),
    State("fe-is-trap", "value"),
    State("fe-trap-dist-unit", "value"),
    State("fe-trap-distance", "value"),
    State("fe-trap-style", "value"),
    State("fe-trap-num-break", "value"),
    State("fe-trap-start-station", "value"),
    State("fe-trap-choke1", "value"),
    State("fe-trap-choke2", "value"),
    State("fe-trap-by-station", "value"),
    State("fe-station-1", "value"),
    State("fe-station-2", "value"),
    State("fe-station-3", "value"),
    State("fe-station-4", "value"),
    State("fe-station-5", "value"),
    State("fe-trap-remarks", "value"),
    State("fe-is-skeet", "value"),
    State("fe-skeet-discipline", "value"),
    State("fe-skeet-sequence", "value"),
    State("fe-skeet-num-break", "value"),
    State("fe-skeet-choke1", "value"),
    State("fe-skeet-choke2", "value"),
    State("fe-skeet-low-gun-start", "value"),
    State("fe-skeet-remarks", "value"),
    State("fe-skeet-by-shot", "value"),
    State("fe-is-double-trap", "value"),
    State("fe-dt-dist-unit", "value"),
    State("fe-dt-distance", "value"),
    State("fe-dt-style", "value"),
    State("fe-dt-num-break", "value"),
    State("fe-dt-start-station", "value"),
    State("fe-dt-choke1", "value"),
    State("fe-dt-choke2", "value"),
    State("fe-dt-by-station", "value"),
    State("fe-dt-station-1", "value"),
    State("fe-dt-station-2", "value"),
    State("fe-dt-station-3", "value"),
    State("fe-dt-station-4", "value"),
    State("fe-dt-station-5", "value"),
    State("fe-dt-remarks", "value"),
    State("fe-skeet-shots-table", "data"),
    State("fe-ends-store", "data"),
    prevent_initial_call=True,
)
def add_end(
    _,
    visit_id, model_id, ammo_type, ammo_id, cartridge_id,
    quantity, dist_unit, distance,
    target_id, shots_scored, pts_stab, support_hands,
    sight_id, stance, remarks,
    is_trap, trap_dist_unit, trap_distance, trap_style,
    trap_num_break, trap_start_station, trap_choke1, trap_choke2, trap_by_station,
    s1, s2, s3, s4, s5, trap_remarks,
    is_skeet, skeet_discipline, skeet_sequence, skeet_num_break, skeet_choke1, skeet_choke2, skeet_low_gun_start,
    skeet_remarks, skeet_by_shot,
    is_double_trap, dt_dist_unit, dt_distance, dt_style,
    dt_num_break, dt_start_station, dt_choke1, dt_choke2, dt_by_station,
    dt1, dt2, dt3, dt4, dt5, dt_remarks,
    skeet_shots_data,
    ends_store,
):
    ends_store = ends_store or []

    def warn(msg):
        return (
            dbc.Alert(msg, color="warning"),
            ends_store,
            render_ends_table(ends_store),
        ) + _KEEP_END + (no_update,)

    if not visit_id:
        return warn("No visit created yet.")
    if not model_id:
        return warn("Firearm model is required.")
    if sum(bool(x) for x in (is_trap, is_skeet, is_double_trap)) > 1:
        return warn("An end can only be one of: trap, skeet, double trap.")
    if is_skeet and not skeet_discipline:
        return warn("Skeet discipline is required.")

    skeet_sequence_targets = get_sequence(skeet_sequence or skeet_discipline) if is_skeet else None
    skeet_results = None
    if is_skeet and skeet_by_shot:
        if skeet_sequence_targets is None or not skeet_shots_data:
            return warn("No target sequence is loaded for the shot-by-shot record.")
        skeet_results, bad = parse_shot_cells(skeet_sequence_targets, skeet_shots_data[0])
        if bad:
            return warn("Every shot must be 1 (hit) or 0 (miss). Check: " + ", ".join(bad))
        if skeet_num_break is not None and int(skeet_num_break) != sum(skeet_results):
            return warn(
                f"Num Breaks is {int(skeet_num_break)} but the shot-by-shot record "
                f"has {sum(skeet_results)}. Correct one of them, or clear Num Breaks."
            )
        skeet_num_break = sum(skeet_results)

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
            remarks=(remarks or "").strip() or None,
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
                shotgun_choke_id1=int(trap_choke1) if trap_choke1 else None,
                shotgun_choke_id2=int(trap_choke2) if trap_choke2 else None,
                remarks=(trap_remarks or "").strip() or None,
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
                sequence=skeet_sequence or skeet_discipline,
                num_break=int(skeet_num_break) if skeet_num_break is not None else None,
                shotgun_choke_id1=int(skeet_choke1) if skeet_choke1 else None,
                shotgun_choke_id2=int(skeet_choke2) if skeet_choke2 else None,
                low_gun_start=bool(skeet_low_gun_start),
                remarks=(skeet_remarks or "").strip() or None,
            )
            postgres_session.add(skeet_obj)
            postgres_session.flush()

            if skeet_results is not None:
                shot_rows, _ = build_shot_rows(skeet_sequence_targets, skeet_results)
                for shot_row in shot_rows:
                    postgres_session.add(SkeetShot(skeet_round_id=skeet_obj.id, **shot_row))

        if is_double_trap:
            dt_dist_yard = dt_dist_m = None
            if dt_distance is not None:
                if dt_dist_unit == "yd":
                    dt_dist_yard = float(dt_distance)
                    dt_dist_m = dt_dist_yard * 0.9144
                else:
                    dt_dist_m = float(dt_distance)
                    dt_dist_yard = dt_dist_m * 1.09361

            dt_obj = DoubleTrapRound(
                firearm_end_id=end_obj.id,
                distance_yard=dt_dist_yard,
                distance_m=dt_dist_m,
                discipline=dt_style or None,
                num_break=int(dt_num_break) if dt_num_break is not None else None,
                starting_station=int(dt_start_station) if dt_start_station is not None else None,
                shotgun_choke_id1=int(dt_choke1) if dt_choke1 else None,
                shotgun_choke_id2=int(dt_choke2) if dt_choke2 else None,
                remarks=(dt_remarks or "").strip() or None,
            )
            postgres_session.add(dt_obj)
            postgres_session.flush()

            if dt_by_station:
                for station_num, breaks in enumerate([dt1, dt2, dt3, dt4, dt5], start=1):
                    if breaks is not None:
                        postgres_session.add(DoubleTrapShot(
                            double_trap_round_id=dt_obj.id,
                            station=station_num,
                            num_break=int(breaks),
                        ))

        postgres_session.commit()

        new_row = {
            "End ID": end_obj.id,
            "Qty": quantity if quantity is not None else "",
            "Dist (m)": round(distance_m, 1) if distance_m is not None else "",
            "Trap": "Yes" if is_trap else "No",
            "Skeet": "Yes" if is_skeet else "No",
            "Double Trap": "Yes" if is_double_trap else "No",
        }
        new_store = ends_store + [new_row]
        # Pre-populate the next end with this end's setup
        carried = tuple(
            blank if fid in _CLEAR_AFTER_END else ctx.states[f"{fid}.value"]
            for fid, blank in _END_FIELDS
        )
        # the shot-by-shot record belongs to this end, so the next one starts fresh
        next_shots = [blank_shot_row(skeet_sequence_targets)] if skeet_sequence_targets else no_update
        return (
            dbc.Alert(f"End #{end_obj.id} added.", color="success", dismissable=True),
            new_store,
            render_ends_table(new_store),
        ) + carried + (next_shots,)

    except Exception as e:
        postgres_session.rollback()
        return (
            dbc.Alert(f"Error adding end: {e}", color="danger", dismissable=True),
            ends_store,
            render_ends_table(ends_store),
        ) + _KEEP_END + (no_update,)


# ── Existing stat callbacks ──────────────────────────────────────────────────────

@dash.callback(
    dash.Output("visits-table", "children"),
    dash.Output("visits-datatable", "columns"),
    dash.Output("visits-datatable", "data"),
    dash.Input("visits-table", "id"),
)
def update_visits_table(_):
    data = get_visits_data()
    if not data:
        return html.P("No visits recorded."), [], []
    columns = [{"name": c, "id": c} for c in data[0]]
    return None, columns, data


@dash.callback(
    dash.Output("visit-ends-detail", "children"),
    dash.Output("visit-ends-columns-wrapper", "style"),
    dash.Output("visit-ends-datatable", "columns"),
    dash.Output("visit-ends-datatable", "data"),
    dash.Output("visit-ends-datatable", "selected_rows"),
    dash.Output("visit-ends-datatable", "style_table"),
    dash.Input("visits-datatable", "selected_rows"),
    dash.Input("visit-ends-columns", "value"),
    dash.State("visits-datatable", "data"),
    dash.State("visit-ends-datatable", "selected_rows"),
    dash.State("visit-ends-datatable", "data"),
)
def show_visit_ends(selected_rows, selected_columns, visits, end_rows, old_ends):
    hidden, shown = {"display": "none"}, {}
    no_table = ([], [], [], hidden)
    if not selected_rows or not visits:
        return (None, hidden) + no_table
    visit = visits[selected_rows[0]]
    ends = get_visit_ends(visit["Visit ID"])
    # changing the columns redraws the table; keep the selected end if it is still there
    kept = []
    if ctx.triggered_id == "visit-ends-columns" and end_rows and old_ends and ends:
        old_id = old_ends[end_rows[0]]["End ID"] if end_rows[0] < len(old_ends) else None
        kept = [i for i, e in enumerate(ends) if e["End ID"] == old_id]
    heading = html.H5(f"Visit #{visit['Visit ID']} – {visit['Date']} at {visit['Range']}")
    if ends is None:
        return ([heading, dbc.Alert("Could not load the ends for this visit.", color="danger")],
                hidden) + no_table
    if not ends:
        return [heading, html.P("This visit has no ends.", className="text-muted")], hidden, *no_table
    total = sum(e["Shots"] or 0 for e in ends)
    columns = [c for c in VISIT_END_COLUMNS if c in (selected_columns or VISIT_END_COLUMNS)]
    detail = [
        heading,
        html.P(f"{len(ends)} end{'s' if len(ends) != 1 else ''}, {total} shots. "
               "Select an end to see its shots.", className="text-muted"),
    ]
    return (detail, shown, [{"name": c, "id": c} for c in columns], ends, kept,
            {"overflowX": "auto"})


@dash.callback(
    dash.Output("visit-end-shots", "children"),
    dash.Input("visit-ends-datatable", "selected_rows"),
    dash.State("visit-ends-datatable", "data"),
)
def show_end_shots(end_rows, ends):
    # a new visit or column change resets selected_rows, which clears or redraws this
    if not end_rows or not ends:
        return None
    if end_rows[0] >= len(ends):
        return None
    return render_end_shots(ends[end_rows[0]])


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
    dash.Input("shots-by-cartridge-columns", "value"),
)
def update_shots_by_cartridge(selected_columns):
    data = get_shots_by_cartridge()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    display_cols = [c for c in df.columns if not selected_columns or c in selected_columns]
    return dbc.Table.from_dataframe(df[display_cols], striped=True, bordered=True, hover=True)


@dash.callback(
    dash.Output("shots-by-ammunition-table", "children"),
    dash.Input("shots-by-ammunition-columns", "value"),
)
def update_shots_by_ammunition(selected_columns):
    data = get_shots_by_ammunition()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    display_cols = [c for c in df.columns if not selected_columns or c in selected_columns]
    return dbc.Table.from_dataframe(df[display_cols], striped=True, bordered=True, hover=True)


@dash.callback(
    dash.Output("cartridges-table", "children"),
    dash.Input("cartridges-columns", "value"),
)
def update_cartridges_table(selected_columns):
    data = get_cartridges_data()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    display_cols = [c for c in df.columns if not selected_columns or c in selected_columns]
    df = df[display_cols]
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


@dash.callback(
    dash.Output("ammunition-table", "children"),
    dash.Input("ammunition-columns", "value"),
)
def update_ammunition_table(selected_columns):
    data = get_ammunition_data()
    if not data:
        return html.P("No data available")
    df = pd.DataFrame(data)
    display_cols = [c for c in df.columns if not selected_columns or c in selected_columns]
    df = df[display_cols]
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
