import dash
from dash import dcc, html, callback, Input, Output, State, ctx
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import text

from models import Session, postgres_session
from models.firearm import (
    FirearmManufacturer, FirearmCartridge, FirearmAmmunition, FirearmModel,
)

dash.register_page(__name__, path="/firearm-data")


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
    return _options("select id, name from firearm_manufacturer order by name")


def get_cartridges():
    return _options("select id, name from firearm_cartridge order by name")


def get_actions():
    return _options("select id, name from firearm_action order by name")


def get_restrictions():
    return _options(
        "select id, restriction_type from firearm_restriction order by restriction_type"
    )


def _table(sql):
    """Paginated, sortable, filterable table of every row returned by `sql`."""
    try:
        session = Session()
        rows = session.execute(text(sql)).fetchall()
        cols = list(rows[0]._mapping.keys()) if rows else []
        session.close()
        if not rows:
            return html.P("No rows yet.", className="text-muted")
        df = pd.DataFrame([dict(r._mapping) for r in rows], columns=cols)
        return DataTable(
            columns=[{"name": c, "id": c} for c in cols],
            data=df.to_dict("records"),
            sort_action="native",
            filter_action="native",
            page_action="native",
            page_size=10,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "6px"},
            style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"}
            ],
        )
    except Exception as e:
        return html.P(f"Error: {e}", className="text-danger")


def all_manufacturers():
    return _table(
        "select id, name, country_iso, website "
        "from firearm_manufacturer order by id desc"
    )


def all_cartridges():
    return _table("""
        select id, name, strike_type, shot_size, shot_material,
               shot_load_oz, shot_load_g, length_mm_case, length_in_case,
               diameter_in_base, diameter_mm_base, diameter_mm_bullet,
               diameter_in_bullet, diameter_in_land, diameter_mm_land
        from firearm_cartridge order by id desc
    """)


def all_ammunition():
    return _table("""
        select a.id, coalesce(a.short_name, a.name) as name, m.name as manufacturer,
               c.id as cartridge_id, c.name as cartridge,
               c.shot_size, c.shot_load_oz, c.shot_load_g, c.shot_material,
               a.casing, a.tip, a.muzzle_velocity_fps, a.weight_grain
        from firearm_ammunition a
        left join firearm_manufacturer m on a.firearm_manufacturer_id = m.id
        left join firearm_cartridge c on a.firearm_cartridge_id = c.id
        order by a.id desc
    """)


def all_models():
    return _table("""
        select mdl.id, m.name as manufacturer, coalesce(mdl.short_name, mdl.name) as name,
               act.name as action, r.restriction_type as restriction,
               c.name as cartridge
        from firearm_model mdl
        join firearm_manufacturer m on mdl.firearm_manufacturer_id = m.id
        left join firearm_action act on mdl.firearm_action_id = act.id
        left join firearm_restriction r on mdl.firearm_restriction_id = r.id
        left join firearm_cartridge c on mdl.firearm_cartridge_id1 = c.id
        order by mdl.id desc
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

def _text_col(label, id_, placeholder="", md=4, type_="text"):
    return dbc.Col([
        html.Label(label),
        dbc.Input(id=id_, placeholder=placeholder, type=type_),
    ], md=md)


manufacturer_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Manufacturer", className="card-title"),
    dbc.Row([
        _text_col("Name *", "mf-name", "e.g. Beretta"),
        _text_col("Country ISO (2)", "mf-country-iso", "IT", md=2),
        _text_col("Website", "mf-website", "https://…"),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Address Street", "mf-street"),
        _text_col("City", "mf-city"),
        _text_col("Province", "mf-province"),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Address Country (2)", "mf-address-country", md=2),
        _text_col("Postal Code", "mf-postal", md=2),
        _text_col("Phone", "mf-phone", md=3),
        _text_col("Phone Country Code", "mf-phone-cc", md=2),
    ], className="mb-3"),
    dbc.Button("Add Manufacturer", id="mf-add-btn", color="primary"),
    html.Div(id="mf-alert", className="mt-3"),
    html.Hr(),
    html.H6("All records"),
    html.Div(id="mf-recent"),
]))


cartridge_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Cartridge", className="card-title"),
    dbc.Row([
        _text_col("Name *", "ct-name", "e.g. 12 Gauge"),
        _text_col("Strike Type", "ct-strike", "centerfire / rimfire"),
        _text_col("Shot Size", "ct-shot-size", md=2),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Case Length (in)", "ct-len-in", md=3, type_="number"),
        _text_col("Case Length (mm)", "ct-len-mm", md=3, type_="number"),
        _text_col("Shot Material", "ct-shot-material", md=3),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Base Diameter (in)", "ct-dia-in-base", md=2, type_="number"),
        _text_col("Base Diameter (mm)", "ct-dia-mm-base", md=2, type_="number"),
        _text_col("Bullet Diameter (in)", "ct-dia-in-bullet", md=2, type_="number"),
        _text_col("Bullet Diameter (mm)", "ct-dia-mm-bullet", md=2, type_="number"),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Shot Load (oz)", "ct-load-oz", md=3, type_="number"),
        _text_col("Shot Load (g)", "ct-load-g", md=3, type_="number"),
    ], className="mb-3"),
    dbc.Button("Add Cartridge", id="ct-add-btn", color="primary"),
    html.Div(id="ct-alert", className="mt-3"),
    html.Hr(),
    html.H6("All records"),
    html.Div(id="ct-recent"),
]))


ammunition_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Ammunition", className="card-title"),
    dbc.Row([
        _text_col("Name *", "am-name", "e.g. 12ga #7.5 Target"),
        dbc.Col([
            html.Label("Cartridge"),
            dcc.Dropdown(id="am-cartridge", placeholder="Select cartridge"),
        ], md=4),
        dbc.Col([
            html.Label("Manufacturer"),
            dcc.Dropdown(id="am-manufacturer", placeholder="Select manufacturer"),
        ], md=4),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Casing", "am-casing", md=3),
        _text_col("Tip", "am-tip", md=3),
        _text_col("Muzzle Velocity (fps)", "am-mv", md=3, type_="number"),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Weight (grain)", "am-weight", md=3, type_="number"),
        _text_col("Num Pellets", "am-pellets", md=3, type_="number"),
    ], className="mb-3"),
    dbc.Button("Add Ammunition", id="am-add-btn", color="primary"),
    html.Div(id="am-alert", className="mt-3"),
    html.Hr(),
    html.H6("All records"),
    html.Div(id="am-recent"),
]))


def _cartridge_slot(n, required=False):
    star = " *" if required else ""
    return dbc.Row([
        dbc.Col([
            html.Label(f"Cartridge {n}{star}"),
            dcc.Dropdown(id=f"md-cartridge-{n}", placeholder="Select cartridge"),
        ], md=4),
        dbc.Col([
            html.Label(f"Capacity {n}"),
            dbc.Input(id=f"md-capacity-{n}", type="number", min=0),
        ], md=2),
    ], className="mb-2")


model_tab = dbc.Card(dbc.CardBody([
    html.H4("Add Model", className="card-title"),
    dbc.Row([
        _text_col("Name *", "md-name", "e.g. A300 Ultima"),
        dbc.Col([
            html.Label("Manufacturer *"),
            dcc.Dropdown(id="md-manufacturer", placeholder="Select manufacturer"),
        ], md=4),
        dbc.Col([
            html.Label("Action *"),
            dcc.Dropdown(id="md-action", placeholder="Select action"),
        ], md=4),
    ], className="mb-3"),
    dbc.Row([
        dbc.Col([
            html.Label("Restriction *"),
            dcc.Dropdown(id="md-restriction", placeholder="Select restriction"),
        ], md=4),
        _text_col("Barrel Length (in)", "md-barrel-in", md=2, type_="number"),
        _text_col("Barrel Length (cm)", "md-barrel-cm", md=2, type_="number"),
        _text_col("Country ISO Origin (2)", "md-country-iso", md=2),
    ], className="mb-3"),
    dbc.Row([
        _text_col("Weight (lb)", "md-weight-lb", md=2, type_="number"),
        _text_col("Weight (kg)", "md-weight-kg", md=2, type_="number"),
        dbc.Col([
            html.Label("Rear Sight"),
            dbc.Checklist(
                id="md-rear-sight",
                options=[{"label": " Yes", "value": True}],
                value=[], switch=True,
            ),
        ], md=2),
        dbc.Col([
            html.Label("Front Sight"),
            dbc.Checklist(
                id="md-front-sight",
                options=[{"label": " Yes", "value": True}],
                value=[], switch=True,
            ),
        ], md=2),
    ], className="mb-3"),

    html.H6("Chambered Cartridges"),
    _cartridge_slot(1, required=True),
    dbc.Button(
        "More cartridges (2–7)", id="md-more-btn",
        color="link", size="sm", className="px-0",
    ),
    dbc.Collapse(
        id="md-more-collapse",
        is_open=False,
        children=[_cartridge_slot(n) for n in range(2, 8)],
    ),

    html.Hr(),
    dbc.Button("Add Model", id="md-add-btn", color="primary"),
    html.Div(id="md-alert", className="mt-3"),
    html.Hr(),
    html.H6("All records"),
    html.Div(id="md-recent"),
]))


layout = dbc.Container([
    dbc.Row(dbc.Col(html.H2("Firearm Data"), width=12), className="mb-2 mt-2"),
    dbc.Row(dbc.Col(html.P(
        "Add reference data used by the Firearms logging page. "
        "Create manufacturers and cartridges first, then ammunition and models.",
        className="text-muted",
    ), width=12)),

    dbc.Tabs([
        dbc.Tab(manufacturer_tab, label="Manufacturer", tab_id="tab-manufacturer"),
        dbc.Tab(cartridge_tab, label="Cartridge", tab_id="tab-cartridge"),
        dbc.Tab(ammunition_tab, label="Ammunition", tab_id="tab-ammunition"),
        dbc.Tab(model_tab, label="Model", tab_id="tab-model"),
    ], id="fd-tabs", active_tab="tab-manufacturer"),

    # Bumped after every successful insert so dropdowns/tables refresh.
    dcc.Store(id="fd-refresh", data=0),
], fluid=True)


# ── Dropdown + recent-table refresh ──────────────────────────────────────────────

@callback(
    Output("am-cartridge", "options"),
    Output("am-manufacturer", "options"),
    Output("md-manufacturer", "options"),
    Output("md-action", "options"),
    Output("md-restriction", "options"),
    Output("md-cartridge-1", "options"),
    Output("md-cartridge-2", "options"),
    Output("md-cartridge-3", "options"),
    Output("md-cartridge-4", "options"),
    Output("md-cartridge-5", "options"),
    Output("md-cartridge-6", "options"),
    Output("md-cartridge-7", "options"),
    Output("mf-recent", "children"),
    Output("ct-recent", "children"),
    Output("am-recent", "children"),
    Output("md-recent", "children"),
    Input("fd-tabs", "active_tab"),
    Input("fd-refresh", "data"),
)
def refresh_reference(_active_tab, _refresh):
    cartridges = get_cartridges()
    manufacturers = get_manufacturers()
    return (
        cartridges, manufacturers,
        manufacturers, get_actions(), get_restrictions(),
        cartridges, cartridges, cartridges, cartridges,
        cartridges, cartridges, cartridges,
        all_manufacturers(), all_cartridges(),
        all_ammunition(), all_models(),
    )


@callback(
    Output("md-more-collapse", "is_open"),
    Input("md-more-btn", "n_clicks"),
    State("md-more-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_more_cartridges(_n, is_open):
    return not is_open


# ── Insert callbacks ─────────────────────────────────────────────────────────────

@callback(
    Output("mf-alert", "children"),
    Output("fd-refresh", "data", allow_duplicate=True),
    Output("mf-name", "value"),
    Input("mf-add-btn", "n_clicks"),
    State("mf-name", "value"),
    State("mf-country-iso", "value"),
    State("mf-website", "value"),
    State("mf-street", "value"),
    State("mf-city", "value"),
    State("mf-province", "value"),
    State("mf-address-country", "value"),
    State("mf-postal", "value"),
    State("mf-phone", "value"),
    State("mf-phone-cc", "value"),
    State("fd-refresh", "data"),
    prevent_initial_call=True,
)
def add_manufacturer(_n, name, country_iso, website, street, city, province,
                     addr_country, postal, phone, phone_cc, refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    try:
        obj = FirearmManufacturer(
            name=_s(name),
            country_iso=_s(country_iso),
            website=_s(website),
            address_street=_s(street),
            address_city=_s(city),
            address_province=_s(province),
            address_country=_s(addr_country),
            postal_code=_s(postal),
            phone=_s(phone),
            phone_country_code=_s(phone_cc),
        )
        postgres_session.add(obj)
        postgres_session.commit()
        return ok(f"Manufacturer #{obj.id} '{obj.name}' added."), (refresh or 0) + 1, None
    except Exception as e:
        postgres_session.rollback()
        return err(f"Error: {e}"), refresh, name


@callback(
    Output("ct-alert", "children"),
    Output("fd-refresh", "data", allow_duplicate=True),
    Output("ct-name", "value"),
    Input("ct-add-btn", "n_clicks"),
    State("ct-name", "value"),
    State("ct-strike", "value"),
    State("ct-shot-size", "value"),
    State("ct-len-in", "value"),
    State("ct-len-mm", "value"),
    State("ct-shot-material", "value"),
    State("ct-dia-in-base", "value"),
    State("ct-dia-mm-base", "value"),
    State("ct-dia-in-bullet", "value"),
    State("ct-dia-mm-bullet", "value"),
    State("ct-load-oz", "value"),
    State("ct-load-g", "value"),
    State("fd-refresh", "data"),
    prevent_initial_call=True,
)
def add_cartridge(_n, name, strike, shot_size, len_in, len_mm, shot_material,
                  dia_in_base, dia_mm_base, dia_in_bullet, dia_mm_bullet,
                  load_oz, load_g, refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    try:
        obj = FirearmCartridge(
            name=_s(name),
            strike_type=_s(strike),
            shot_size=_s(shot_size),
            length_in_case=_f(len_in),
            length_mm_case=_f(len_mm),
            shot_material=_s(shot_material),
            diameter_in_base=_f(dia_in_base),
            diameter_mm_base=_f(dia_mm_base),
            diameter_in_bullet=_f(dia_in_bullet),
            diameter_mm_bullet=_f(dia_mm_bullet),
            shot_load_oz=_f(load_oz),
            shot_load_g=_f(load_g),
        )
        postgres_session.add(obj)
        postgres_session.commit()
        return ok(f"Cartridge #{obj.id} '{obj.name}' added."), (refresh or 0) + 1, None
    except Exception as e:
        postgres_session.rollback()
        return err(f"Error: {e}"), refresh, name


@callback(
    Output("am-alert", "children"),
    Output("fd-refresh", "data", allow_duplicate=True),
    Output("am-name", "value"),
    Input("am-add-btn", "n_clicks"),
    State("am-name", "value"),
    State("am-cartridge", "value"),
    State("am-manufacturer", "value"),
    State("am-casing", "value"),
    State("am-tip", "value"),
    State("am-mv", "value"),
    State("am-weight", "value"),
    State("am-pellets", "value"),
    State("fd-refresh", "data"),
    prevent_initial_call=True,
)
def add_ammunition(_n, name, cartridge_id, manufacturer_id, casing, tip,
                   mv, weight, pellets, refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    try:
        obj = FirearmAmmunition(
            name=_s(name),
            firearm_cartridge_id=_i(cartridge_id),
            firearm_manufacturer_id=_i(manufacturer_id),
            casing=_s(casing),
            tip=_s(tip),
            muzzle_velocity_fps=_f(mv),
            weight_grain=_f(weight),
            num_pellets=_i(pellets),
        )
        postgres_session.add(obj)
        postgres_session.commit()
        return ok(f"Ammunition #{obj.id} '{obj.name}' added."), (refresh or 0) + 1, None
    except Exception as e:
        postgres_session.rollback()
        return err(f"Error: {e}"), refresh, name


@callback(
    Output("md-alert", "children"),
    Output("fd-refresh", "data", allow_duplicate=True),
    Output("md-name", "value"),
    Input("md-add-btn", "n_clicks"),
    State("md-name", "value"),
    State("md-manufacturer", "value"),
    State("md-action", "value"),
    State("md-restriction", "value"),
    State("md-barrel-in", "value"),
    State("md-barrel-cm", "value"),
    State("md-country-iso", "value"),
    State("md-weight-lb", "value"),
    State("md-weight-kg", "value"),
    State("md-rear-sight", "value"),
    State("md-front-sight", "value"),
    State("md-cartridge-1", "value"),
    State("md-capacity-1", "value"),
    State("md-cartridge-2", "value"),
    State("md-capacity-2", "value"),
    State("md-cartridge-3", "value"),
    State("md-capacity-3", "value"),
    State("md-cartridge-4", "value"),
    State("md-capacity-4", "value"),
    State("md-cartridge-5", "value"),
    State("md-capacity-5", "value"),
    State("md-cartridge-6", "value"),
    State("md-capacity-6", "value"),
    State("md-cartridge-7", "value"),
    State("md-capacity-7", "value"),
    State("fd-refresh", "data"),
    prevent_initial_call=True,
)
def add_model(_n, name, manufacturer_id, action_id, restriction_id,
              barrel_in, barrel_cm, country_iso, weight_lb, weight_kg,
              rear_sight, front_sight,
              c1, cap1, c2, cap2, c3, cap3, c4, cap4, c5, cap5, c6, cap6, c7, cap7,
              refresh):
    if not _s(name):
        return warn("Name is required."), refresh, name
    if not manufacturer_id:
        return warn("Manufacturer is required."), refresh, name
    if not action_id:
        return warn("Action is required."), refresh, name
    if not restriction_id:
        return warn("Restriction is required."), refresh, name
    if not c1:
        return warn("Cartridge 1 is required."), refresh, name
    try:
        obj = FirearmModel(
            name=_s(name),
            firearm_manufacturer_id=_i(manufacturer_id),
            firearm_action_id=_i(action_id),
            firearm_restriction_id=_i(restriction_id),
            barrel_length_in=_f(barrel_in),
            barrel_length_cm=_f(barrel_cm),
            country_iso_origin=_s(country_iso),
            weight_lb=_f(weight_lb),
            weight_kg=_f(weight_kg),
            rear_sight=bool(rear_sight),
            front_sight=bool(front_sight),
            firearm_cartridge_id1=_i(c1), capacity1=_i(cap1),
            firearm_cartridge_id2=_i(c2), capacity2=_i(cap2),
            firearm_cartridge_id3=_i(c3), capacity3=_i(cap3),
            firearm_cartridge_id4=_i(c4), capacity4=_i(cap4),
            firearm_cartridge_id5=_i(c5), capacity5=_i(cap5),
            firearm_cartridge_id6=_i(c6), capacity6=_i(cap6),
            firearm_cartridge_id7=_i(c7), capacity7=_i(cap7),
        )
        postgres_session.add(obj)
        postgres_session.commit()
        return ok(f"Model #{obj.id} '{obj.name}' added."), (refresh or 0) + 1, None
    except Exception as e:
        postgres_session.rollback()
        return err(f"Error: {e}"), refresh, name
