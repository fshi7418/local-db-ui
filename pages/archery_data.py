import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

from models import Session, postgres_session
from models.archery import (
    ArcheryManufacturer, ArcheryArrow, ArcheryReleaseAid, ArcheryArrowRest, ArcheryLimb,
)

dash.register_page(__name__, path="/archery-data")


# ── Reference data helpers ──────────────────────────────────────────────────────

def _options(sql):
    """Run `sql` (must return id, label) and build dropdown options."""
    try:
        session = Session()
        rows = session.execute(text(sql)).fetchall()
        session.close()
        return [{"label": row[1], "value": row[0]} for row in rows]
    except Exception as e:
        print(f"Error querying options: {e}")
        return []


def get_manufacturers():
    return _options("select id, name from archery_manufacturer order by name")


def get_bow_types():
    return _options("select id, name from archery_bow_type order by name")


def _distinct(sql):
    """Run `sql` (must return one text column) and build datalist options."""
    try:
        session = Session()
        rows = session.execute(text(sql)).fetchall()
        session.close()
        return [html.Option(value=row[0]) for row in rows if row[0]]
    except Exception as e:
        print(f"Error querying distinct values: {e}")
        return []


def _table(sql):
    try:
        session = Session()
        rows = session.execute(text(sql)).fetchall()
        cols = list(rows[0]._mapping.keys()) if rows else []
        session.close()
        if not rows:
            return html.P("No rows yet.", className="text-muted")
        df = pd.DataFrame([dict(r._mapping) for r in rows], columns=cols)
        return dbc.Table.from_dataframe(
            df, striped=True, bordered=True, hover=True, size="sm"
        )
    except Exception as e:
        return html.P(f"Error: {e}", className="text-danger")


# ── Most-used accessories (by number of archery rounds) ──────────────────────────

# Appended to every most-used query; `rd` is archery_round.
_USAGE_COLS = "count(rd.id) as rounds, sum(rd.num_shots) as shots, max(rd.date) as last_used"
_USAGE_ORDER = "order by count(rd.id) desc, max(rd.date) desc limit 10"

MOST_USED = [
    ("Ranges", f"""
        select x.id, x.name, x.country_iso, x.address_province, x.address_city, x.outdoor,
               {_USAGE_COLS}
        from archery_round rd join archery_range x on rd.archery_range_id = x.id
        group by x.id {_USAGE_ORDER}
    """),
    ("Scoring Rules", f"""
        select x.id, x.name, x.description, {_USAGE_COLS}
        from archery_round rd join archery_scoring_rule x on rd.archery_scoring_rule_id = x.id
        group by x.id {_USAGE_ORDER}
    """),
    ("Targets", f"""
        select x.id, x.type, x.full_size_cm, x.actual_size_cm, x.minimum_score, {_USAGE_COLS}
        from archery_round rd join archery_target x on rd.archery_target_id = x.id
        group by x.id {_USAGE_ORDER}
    """),
    ("Risers", f"""
        select x.id, t.name as bow_type, m.name as manufacturer, x.name, x.length_in, x.rh_lh,
               x.letoff_pct, {_USAGE_COLS}
        from archery_round rd join archery_riser x on rd.archery_riser_id = x.id
        left join archery_manufacturer m on x.archery_manufacturer_id = m.id
        left join archery_bow_type t on x.archery_bow_type_id = t.id
        group by x.id, t.name, m.name {_USAGE_ORDER}
    """),
    ("Limbs", f"""
        select x.id, t.name as bow_type, m.name as manufacturer, x.name, x.total_length_in,
               x.draw_weight_lb_min, x.draw_weight_lb_max, {_USAGE_COLS}
        from archery_round rd join archery_limb x on rd.archery_limb_id = x.id
        left join archery_manufacturer m on x.archery_manufacturer_id = m.id
        left join archery_bow_type t on x.archery_bow_type_id = t.id
        group by x.id, t.name, m.name {_USAGE_ORDER}
    """),
    ("Arrows", f"""
        select x.id, m.name as manufacturer, x.name, x.shaft_length_in, x.spine, x.size_mm,
               x.fletching, {_USAGE_COLS}
        from archery_round rd join archery_arrow x on rd.archery_arrow_id = x.id
        left join archery_manufacturer m on x.archery_manufacturer_id = m.id
        group by x.id, m.name {_USAGE_ORDER}
    """),
    ("Arrow Rests", f"""
        select x.id, m.name as manufacturer, x.name, x.arrow_rest_type, x.description,
               {_USAGE_COLS}
        from archery_round rd join archery_arrow_rest x on rd.archery_arrow_rest_id = x.id
        left join archery_manufacturer m on x.archery_manufacturer_id = m.id
        group by x.id, m.name {_USAGE_ORDER}
    """),
    ("Sights", f"""
        select x.id, m.name as manufacturer, x.name, x.magnification, {_USAGE_COLS}
        from archery_round rd join archery_sight x on rd.archery_sight_id = x.id
        left join archery_manufacturer m on x.archery_manufacturer_id = m.id
        group by x.id, m.name {_USAGE_ORDER}
    """),
    ("Release Aids", f"""
        select x.id, m.name as manufacturer, x.name, {_USAGE_COLS}
        from archery_round rd join archery_release_aid x on rd.archery_release_aid_id = x.id
        left join archery_manufacturer m on x.archery_manufacturer_id = m.id
        group by x.id, m.name {_USAGE_ORDER}
    """),
]


def most_used_tables():
    children = []
    for title, sql in MOST_USED:
        children += [html.H5(title, className="mt-3"), _table(sql)]
    return children


# ── Recently added (for the add tabs) ────────────────────────────────────────────

def recent_manufacturers():
    return _table("select id, name from archery_manufacturer order by id desc limit 10")


def recent_arrows():
    return _table("""
        select a.id, m.name as manufacturer, a.name, a.shaft_length_in, a.spine, a.size_mm,
               a.fletching
        from archery_arrow a
        left join archery_manufacturer m on a.archery_manufacturer_id = m.id
        order by a.id desc limit 10
    """)


def recent_release_aids():
    return _table("""
        select r.id, m.name as manufacturer, r.name
        from archery_release_aid r
        left join archery_manufacturer m on r.archery_manufacturer_id = m.id
        order by r.id desc limit 10
    """)


def recent_arrow_rests():
    return _table("""
        select r.id, m.name as manufacturer, r.name, r.arrow_rest_type, r.description
        from archery_arrow_rest r
        left join archery_manufacturer m on r.archery_manufacturer_id = m.id
        order by r.id desc limit 10
    """)


def recent_limbs():
    return _table("""
        select l.id, t.name as bow_type, m.name as manufacturer, l.name, l.total_length_in,
               l.draw_weight_lb_min, l.draw_weight_lb_max
        from archery_limb l
        left join archery_manufacturer m on l.archery_manufacturer_id = m.id
        left join archery_bow_type t on l.archery_bow_type_id = t.id
        order by l.id desc limit 10
    """)


# ── Small helpers ───────────────────────────────────────────────────────────────

def _f(x):
    """Float or None."""
    return float(x) if x not in (None, "") else None


def _i(x):
    """Int or None."""
    return int(x) if x not in (None, "") else None


def _s(x):
    """Stripped string or None."""
    return x.strip() if isinstance(x, str) and x.strip() else None


def ok(msg):
    return dbc.Alert(msg, color="success", dismissable=True)


def err(msg):
    return dbc.Alert(msg, color="danger", dismissable=True)


def warn(msg):
    return dbc.Alert(msg, color="warning", dismissable=True)


# ── Layout ──────────────────────────────────────────────────────────────────────

def _text_col(label, id_, placeholder="", md=4, type_="text", **kwargs):
    return dbc.Col([
        html.Label(label),
        dbc.Input(id=id_, placeholder=placeholder, type=type_, **kwargs),
    ], md=md)


def _dropdown_col(label, id_, placeholder, md=4):
    return dbc.Col([
        html.Label(label),
        dcc.Dropdown(id=id_, placeholder=placeholder),
    ], md=md)


def _recent_section(prefix):
    return [
        html.Div(id=f"{prefix}-alert", className="mt-3"),
        html.Hr(),
        html.H6("Recently added"),
        html.Div(id=f"{prefix}-recent"),
    ]


most_used_tab = dbc.Card(dbc.CardBody([
    html.H4("Most Used", className="card-title"),
    html.P(
        "Top 10 of each accessory by number of archery rounds, with the IDs used when "
        "entering a round.",
        className="text-muted",
    ),
    html.Div(id="ad-most-used"),
]))


manufacturer_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Manufacturer", className="card-title"),
    dbc.Row(_text_col("Name *", "amf-name", "e.g. Hoyt"), className="mb-3"),
    dbc.Button("Add Manufacturer", id="amf-add-btn", color="primary"),
    *_recent_section("amf"),
]))


arrow_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Arrow", className="card-title"),
    dbc.Row([
        _text_col("Name *", "aar-name", "e.g. X10"),
        _dropdown_col("Manufacturer", "aar-manufacturer", "Select manufacturer"),
        _text_col("Fletching", "aar-fletching", "Vanes / Feather", md=4, list="aar-fletching-list"),
    ], className="mb-3"),
    html.Datalist(id="aar-fletching-list"),
    dbc.Row([
        _text_col("Shaft Length (in)", "aar-length", md=3, type_="number"),
        _text_col("Spine", "aar-spine", md=3, type_="number"),
        _text_col("Size (mm)", "aar-size", md=3, type_="number"),
    ], className="mb-3"),
    dbc.Button("Add Arrow", id="aar-add-btn", color="primary"),
    *_recent_section("aar"),
]))


release_aid_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Release Aid", className="card-title"),
    dbc.Row([
        _text_col("Name *", "arl-name", "e.g. Tru-Fire Hardcore"),
        _dropdown_col("Manufacturer", "arl-manufacturer", "Select manufacturer"),
    ], className="mb-3"),
    dbc.Button("Add Release Aid", id="arl-add-btn", color="primary"),
    *_recent_section("arl"),
]))


arrow_rest_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Arrow Rest", className="card-title"),
    dbc.Row([
        _text_col("Name *", "ars-name"),
        _dropdown_col("Manufacturer", "ars-manufacturer", "Select manufacturer"),
        _text_col("Type", "ars-type", "drop_away / metal_wire / …", list="ars-type-list"),
    ], className="mb-3"),
    html.Datalist(id="ars-type-list"),
    dbc.Row(
        dbc.Col([
            html.Label("Description"),
            dbc.Textarea(id="ars-description", style={"height": "80px"}),
        ], md=8),
        className="mb-3",
    ),
    dbc.Button("Add Arrow Rest", id="ars-add-btn", color="primary"),
    *_recent_section("ars"),
]))


limb_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Limb", className="card-title"),
    dbc.Row([
        _text_col("Name *", "alm-name"),
        _dropdown_col("Manufacturer", "alm-manufacturer", "Select manufacturer"),
        _dropdown_col("Bow Type", "alm-bow-type", "Select bow type"),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Total Length (in)", "alm-length", md=3, type_="number"),
        _text_col("Draw Weight Min (lb)", "alm-dw-min", md=3, type_="number"),
        _text_col("Draw Weight Max (lb)", "alm-dw-max", md=3, type_="number"),
    ], className="mb-3"),
    dbc.Button("Add Limb", id="alm-add-btn", color="primary"),
    *_recent_section("alm"),
]))


layout = dbc.Container([
    dbc.Row(dbc.Col(html.H2("Archery Data"), width=12), className="mb-2 mt-2"),
    dbc.Row(dbc.Col(html.P(
        "Look up the IDs of archery equipment and add new reference data. "
        "Add the manufacturer first, then the equipment.",
        className="text-muted",
    ), width=12)),

    dbc.Tabs([
        dbc.Tab(most_used_tab, label="Most Used", tab_id="tab-most-used"),
        dbc.Tab(manufacturer_tab, label="Manufacturer", tab_id="tab-manufacturer"),
        dbc.Tab(arrow_tab, label="Arrow", tab_id="tab-arrow"),
        dbc.Tab(release_aid_tab, label="Release Aid", tab_id="tab-release-aid"),
        dbc.Tab(arrow_rest_tab, label="Arrow Rest", tab_id="tab-arrow-rest"),
        dbc.Tab(limb_tab, label="Limb", tab_id="tab-limb"),
    ], id="ad-tabs", active_tab="tab-most-used"),

    # Bumped after every successful insert so dropdowns/tables refresh.
    dcc.Store(id="ad-refresh", data=0),
], fluid=True)


# ── Dropdown + table refresh ─────────────────────────────────────────────────────

@callback(
    Output("aar-manufacturer", "options"),
    Output("arl-manufacturer", "options"),
    Output("ars-manufacturer", "options"),
    Output("alm-manufacturer", "options"),
    Output("alm-bow-type", "options"),
    Output("aar-fletching-list", "children"),
    Output("ars-type-list", "children"),
    Output("ad-most-used", "children"),
    Output("amf-recent", "children"),
    Output("aar-recent", "children"),
    Output("arl-recent", "children"),
    Output("ars-recent", "children"),
    Output("alm-recent", "children"),
    Input("ad-tabs", "active_tab"),
    Input("ad-refresh", "data"),
)
def refresh_reference(_active_tab, _refresh):
    manufacturers = get_manufacturers()
    return (
        manufacturers, manufacturers, manufacturers, manufacturers,
        get_bow_types(),
        _distinct("select distinct fletching from archery_arrow order by 1"),
        _distinct("select distinct arrow_rest_type from archery_arrow_rest order by 1"),
        most_used_tables(),
        recent_manufacturers(), recent_arrows(), recent_release_aids(),
        recent_arrow_rests(), recent_limbs(),
    )


# ── Insert callbacks ─────────────────────────────────────────────────────────────

def _insert(obj, label, refresh, name):
    try:
        postgres_session.add(obj)
        postgres_session.commit()
        return ok(f"{label} #{obj.id} '{obj.name}' added."), (refresh or 0) + 1, None
    except Exception as e:
        postgres_session.rollback()
        return err(f"Error: {e}"), refresh, name


@callback(
    Output("amf-alert", "children"),
    Output("ad-refresh", "data", allow_duplicate=True),
    Output("amf-name", "value"),
    Input("amf-add-btn", "n_clicks"),
    State("amf-name", "value"),
    State("ad-refresh", "data"),
    prevent_initial_call=True,
)
def add_manufacturer(_n, name, refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    return _insert(ArcheryManufacturer(name=_s(name)), "Manufacturer", refresh, name)


@callback(
    Output("aar-alert", "children"),
    Output("ad-refresh", "data", allow_duplicate=True),
    Output("aar-name", "value"),
    Input("aar-add-btn", "n_clicks"),
    State("aar-name", "value"),
    State("aar-manufacturer", "value"),
    State("aar-fletching", "value"),
    State("aar-length", "value"),
    State("aar-spine", "value"),
    State("aar-size", "value"),
    State("ad-refresh", "data"),
    prevent_initial_call=True,
)
def add_arrow(_n, name, manufacturer_id, fletching, length, spine, size, refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    obj = ArcheryArrow(
        name=_s(name),
        archery_manufacturer_id=_i(manufacturer_id),
        fletching=_s(fletching),
        shaft_length_in=_f(length),
        spine=_i(spine),
        size_mm=_f(size),
    )
    return _insert(obj, "Arrow", refresh, name)


@callback(
    Output("arl-alert", "children"),
    Output("ad-refresh", "data", allow_duplicate=True),
    Output("arl-name", "value"),
    Input("arl-add-btn", "n_clicks"),
    State("arl-name", "value"),
    State("arl-manufacturer", "value"),
    State("ad-refresh", "data"),
    prevent_initial_call=True,
)
def add_release_aid(_n, name, manufacturer_id, refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    obj = ArcheryReleaseAid(name=_s(name), archery_manufacturer_id=_i(manufacturer_id))
    return _insert(obj, "Release aid", refresh, name)


@callback(
    Output("ars-alert", "children"),
    Output("ad-refresh", "data", allow_duplicate=True),
    Output("ars-name", "value"),
    Input("ars-add-btn", "n_clicks"),
    State("ars-name", "value"),
    State("ars-manufacturer", "value"),
    State("ars-type", "value"),
    State("ars-description", "value"),
    State("ad-refresh", "data"),
    prevent_initial_call=True,
)
def add_arrow_rest(_n, name, manufacturer_id, rest_type, description, refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    obj = ArcheryArrowRest(
        name=_s(name),
        archery_manufacturer_id=_i(manufacturer_id),
        arrow_rest_type=_s(rest_type),
        description=_s(description),
    )
    return _insert(obj, "Arrow rest", refresh, name)


@callback(
    Output("alm-alert", "children"),
    Output("ad-refresh", "data", allow_duplicate=True),
    Output("alm-name", "value"),
    Input("alm-add-btn", "n_clicks"),
    State("alm-name", "value"),
    State("alm-manufacturer", "value"),
    State("alm-bow-type", "value"),
    State("alm-length", "value"),
    State("alm-dw-min", "value"),
    State("alm-dw-max", "value"),
    State("ad-refresh", "data"),
    prevent_initial_call=True,
)
def add_limb(_n, name, manufacturer_id, bow_type_id, length, dw_min, dw_max, refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    if dw_min is not None and dw_max is not None and dw_min > dw_max:
        return warn("Draw weight min can't exceed max."), refresh, name
    obj = ArcheryLimb(
        name=_s(name),
        archery_manufacturer_id=_i(manufacturer_id),
        archery_bow_type_id=_i(bow_type_id),
        total_length_in=_f(length),
        draw_weight_lb_min=_f(dw_min),
        draw_weight_lb_max=_f(dw_max),
    )
    return _insert(obj, "Limb", refresh, name)
