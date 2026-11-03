import dash
from dash import html, dcc, callback, Input, Output, State
from dash.dash_table import DataTable
import dash_bootstrap_components as dbc
from datetime import date
from sqlalchemy import text

from models import Session, postgres_session, get_est_now_clean
from models.books import (
    Book, BookAuthor, BookEditor, BookLanguage, BookPublisher, BookSeries, BookTranslator,
)

dash.register_page(__name__, path="/books")

# Order names the same way the CLI's display helpers do
NAME_COLLATE = 'collate "zh-Hans-CN-x-icu"'


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _is_cjk(s):
    return any("㐀" <= ch <= "鿿" or "豈" <= ch <= "﫿" for ch in s or "")


def person_name(first, middle, last):
    """Display name: family name first for CJK names (张欣), given name first otherwise."""
    if _is_cjk(first) or _is_cjk(last):
        return f"{last or ''}{first or ''}"
    return " ".join(p for p in (first, middle, last) if p)


def partial_date(year, month, day):
    """YYYY, YYYY-MM or YYYY-MM-DD from optional parts."""
    if not year:
        return ""
    parts = [f"{year:04d}"]
    if month:
        parts.append(f"{month:02d}")
        if day:
            parts.append(f"{day:02d}")
    return "-".join(parts)


def _entered(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def optional_text(value):
    value = (value or "").strip()
    return value or None


def optional_int(value, label, low=None, high=None):
    """None for a blank input, otherwise a whole number within [low, high]."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if not number.is_integer():
        raise ValueError(f"{label} must be a whole number.")
    number = int(number)
    if low is not None and high is not None and not low <= number <= high:
        raise ValueError(f"{label} must be between {low} and {high}.")
    if low is not None and number < low:
        raise ValueError(f"{label} must be at least {low}.")
    if high is not None and number > high:
        raise ValueError(f"{label} must be at most {high}.")
    return number


def date_parts(prefix, year, month, day):
    year = optional_int(year, f"{prefix} year", 1, 9999)
    month = optional_int(month, f"{prefix} month", 1, 12)
    day = optional_int(day, f"{prefix} day", 1, 31)
    if month and not year:
        raise ValueError(f"{prefix} month needs a year.")
    if day and not month:
        raise ValueError(f"{prefix} day needs a month.")
    return year, month, day


def success(message):
    return dbc.Alert(message, color="success", dismissable=True)


def failure(message):
    return dbc.Alert(message, color="danger", dismissable=True)


def db_error(action, e):
    """Alert for a database error, showing the driver's message rather than the full SQL."""
    detail = str(getattr(e, "orig", None) or e).strip().splitlines()[0]
    return failure(f"Error adding {action}: {detail}")


# ── Queries ─────────────────────────────────────────────────────────────────────

PEOPLE = {
    # kind: (table, association table, association column)
    "author": ("book_author", "book_to_book_author", "book_author_id"),
    "translator": ("book_translator", "book_to_book_translator", "book_translator_id"),
    "editor": ("book_editor", "book_to_book_editor", "book_editor_id"),
}


def load_book_data():
    """Every book table, read in one session."""
    session = Session()
    try:
        q = lambda sql: session.execute(text(sql)).fetchall()
        data = {
            "author": q(f"""
                select id, first_name, middle_name, last_name, birthday_year, birthday_month, birthday_day,
                       death_date_year, death_date_month, death_date_day, nationality, datetime_entered
                from book_author
                order by last_name {NAME_COLLATE}, first_name {NAME_COLLATE}
            """),
            "translator": q(f"""
                select id, first_name, middle_name, last_name, datetime_entered
                from book_translator
                order by last_name {NAME_COLLATE}, first_name {NAME_COLLATE}
            """),
            "editor": q(f"""
                select id, first_name, middle_name, last_name, datetime_entered
                from book_editor
                order by last_name {NAME_COLLATE}, first_name {NAME_COLLATE}
            """),
            "publisher": q(f"select id, name, datetime_entered from book_publisher order by name {NAME_COLLATE}"),
            "series": q(f"""
                select s.id, s.name, s.total_books, s.publisher_id, p.name as publisher, s.datetime_entered
                from book_series s
                left join book_publisher p on s.publisher_id = p.id
                order by s.name {NAME_COLLATE}
            """),
            "language": q("select id, name, code from book_language order by name"),
            "format": q("select id, name from book_format order by id"),
            "book": q("""
                select id, title, subtitle, isbn, isbn13, publication_year, publication_month, publication_day,
                       page_count, date_read, series_order, edition, publisher_id, series_id, format_id,
                       datetime_entered
                from book
                order by id desc
            """),
        }
        links = {}
        for kind, (_table, assoc, column) in PEOPLE.items():
            links[kind] = q(f"select book_id, {column} from {assoc}")
        links["language"] = q("select book_id, book_language_id from book_to_book_language")
        data["links"] = links
        return data
    finally:
        session.close()


def _books_per(link_rows):
    """target id -> number of books linked to it."""
    counts = {}
    for _book_id, target_id in link_rows:
        counts[target_id] = counts.get(target_id, 0) + 1
    return counts


def _names_per_book(link_rows, names):
    """book id -> '; '-joined names, in the order the names are sorted."""
    order = {target_id: i for i, target_id in enumerate(names)}
    grouped = {}
    for book_id, target_id in link_rows:
        grouped.setdefault(book_id, []).append(target_id)
    return {
        book_id: "; ".join(names[t] for t in sorted(ids, key=lambda t: order.get(t, 0)) if t in names)
        for book_id, ids in grouped.items()
    }


def build_tables(data):
    """Rows for every table section on the page."""
    names = {
        kind: {r.id: person_name(r.first_name, r.middle_name, r.last_name) for r in data[kind]}
        for kind in PEOPLE
    }
    names["language"] = {r.id: r.name for r in data["language"]}
    publishers = {r.id: r.name for r in data["publisher"]}
    series = {r.id: r.name for r in data["series"]}
    formats = {r.id: r.name for r in data["format"]}
    links = data["links"]
    per_book = {kind: _names_per_book(links[kind], names[kind]) for kind in links}

    books = [
        {
            "ID": b.id,
            "Title": b.title,
            "Subtitle": b.subtitle or "",
            "Authors": per_book["author"].get(b.id, ""),
            "Translators": per_book["translator"].get(b.id, ""),
            "Editors": per_book["editor"].get(b.id, ""),
            "Languages": per_book["language"].get(b.id, ""),
            "Publisher": publishers.get(b.publisher_id, ""),
            "Series": series.get(b.series_id, ""),
            "Series Order": b.series_order,
            "Format": formats.get(b.format_id, ""),
            "Edition": b.edition,
            "Pages": b.page_count,
            "Published": partial_date(b.publication_year, b.publication_month, b.publication_day),
            "Date Read": b.date_read.strftime("%Y-%m-%d") if b.date_read else "",
            "ISBN": b.isbn or "",
            "ISBN13": b.isbn13 or "",
            "Entered": _entered(b.datetime_entered),
        }
        for b in data["book"]
    ]

    def people_rows(kind):
        counts = _books_per(links[kind])
        rows = []
        for r in data[kind]:
            row = {
                "ID": r.id,
                "Name": names[kind][r.id],
                "First Name": r.first_name,
                "Middle Name": r.middle_name or "",
                "Last Name": r.last_name or "",
            }
            if kind == "author":
                row["Born"] = partial_date(r.birthday_year, r.birthday_month, r.birthday_day)
                row["Died"] = partial_date(r.death_date_year, r.death_date_month, r.death_date_day)
                row["Nationality"] = r.nationality or ""
            row["Books"] = counts.get(r.id, 0)
            row["Entered"] = _entered(r.datetime_entered)
            rows.append(row)
        return rows

    books_by_publisher = {}
    books_by_series = {}
    books_by_format = {}
    for b in data["book"]:
        books_by_publisher[b.publisher_id] = books_by_publisher.get(b.publisher_id, 0) + 1
        books_by_series[b.series_id] = books_by_series.get(b.series_id, 0) + 1
        books_by_format[b.format_id] = books_by_format.get(b.format_id, 0) + 1
    language_counts = _books_per(links["language"])

    return {
        "book": books,
        "author": people_rows("author"),
        "translator": people_rows("translator"),
        "editor": people_rows("editor"),
        "publisher": [
            {"ID": r.id, "Name": r.name, "Books": books_by_publisher.get(r.id, 0), "Entered": _entered(r.datetime_entered)}
            for r in data["publisher"]
        ],
        "series": [
            {
                "ID": r.id, "Name": r.name, "Publisher": r.publisher or "", "Total Books": r.total_books,
                "Books Entered": books_by_series.get(r.id, 0), "Entered": _entered(r.datetime_entered),
            }
            for r in data["series"]
        ],
        "language": [
            {"ID": r.id, "Name": r.name, "Code": r.code or "", "Books": language_counts.get(r.id, 0)}
            for r in data["language"]
        ],
        "format": [
            {"ID": r.id, "Name": r.name, "Books": books_by_format.get(r.id, 0)}
            for r in data["format"]
        ],
    }


def build_options(data):
    """Dropdown options for every picker on the page."""
    def people(kind):
        return [
            {"label": f"{person_name(r.first_name, r.middle_name, r.last_name)} (#{r.id})", "value": r.id}
            for r in data[kind]
        ]
    return {
        "author": people("author"),
        "translator": people("translator"),
        "editor": people("editor"),
        "publisher": [{"label": f"{r.name} (#{r.id})", "value": r.id} for r in data["publisher"]],
        "series": [
            {"label": f"{r.name} — {r.publisher}" if r.publisher else r.name, "value": r.id}
            for r in data["series"]
        ],
        "language": [{"label": r.name, "value": r.id} for r in data["language"]],
        "format": [{"label": r.name, "value": r.id} for r in data["format"]],
    }


# ── Layout helpers ──────────────────────────────────────────────────────────────

def field(label, component, md=4):
    return dbc.Col([html.Label(label), component], md=md, className="mb-3")


def text_input(id_, placeholder=None, max_length=None):
    return dbc.Input(id=id_, type="text", placeholder=placeholder, maxLength=max_length)


def number_input(id_, low=None, high=None, placeholder=None):
    return dbc.Input(id=id_, type="number", min=low, max=high, step=1, placeholder=placeholder)


def dropdown(id_, placeholder, multi=False):
    return dcc.Dropdown(id=id_, options=[], multi=multi, placeholder=placeholder)


def date_part_fields(prefix, label):
    return [
        field(f"{label} Year", number_input(f"{prefix}-year", 1, 9999, "YYYY"), md=2),
        field(f"{label} Month", number_input(f"{prefix}-month", 1, 12, "MM"), md=2),
        field(f"{label} Day", number_input(f"{prefix}-day", 1, 31, "DD"), md=2),
    ]


def person_fields(prefix, last_name_hint="optional"):
    return dbc.Row([
        field("First Name", text_input(f"{prefix}-first", max_length=100)),
        field("Middle Name (optional)", text_input(f"{prefix}-middle", max_length=100)),
        field(f"Last Name ({last_name_hint})", text_input(f"{prefix}-last", max_length=100)),
    ])


def column_defs(columns):
    return [{"name": c, "id": c, "type": "numeric" if c in NUMERIC_COLUMNS else "text"} for c in columns]


def data_table(id_, columns, page_size=10):
    return DataTable(
        id=id_,
        columns=column_defs(columns),
        data=[],
        sort_action="native",
        filter_action="native",
        page_action="native",
        page_size=page_size,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "8px", "whiteSpace": "normal", "height": "auto"},
        style_header={"backgroundColor": "rgb(230, 230, 230)", "fontWeight": "bold"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "rgb(248, 248, 248)"}],
    )


NUMERIC_COLUMNS = {
    "ID", "Series Order", "Edition", "Pages", "Books", "Total Books", "Books Entered",
}

TABLE_SECTIONS = [
    # (key, title, columns, page size)
    ("book", "Books", [
        "ID", "Title", "Subtitle", "Authors", "Translators", "Editors", "Languages", "Publisher",
        "Series", "Series Order", "Format", "Edition", "Pages", "Published", "Date Read",
        "ISBN", "ISBN13", "Entered",
    ], 20),
    ("author", "Authors", [
        "ID", "Name", "First Name", "Middle Name", "Last Name", "Born", "Died", "Nationality", "Books", "Entered",
    ], 10),
    ("publisher", "Publishers", ["ID", "Name", "Books", "Entered"], 10),
    ("series", "Series", ["ID", "Name", "Publisher", "Total Books", "Books Entered", "Entered"], 10),
    ("translator", "Translators", ["ID", "Name", "First Name", "Middle Name", "Last Name", "Books", "Entered"], 10),
    ("editor", "Editors", ["ID", "Name", "First Name", "Middle Name", "Last Name", "Books", "Entered"], 10),
    ("language", "Languages", ["ID", "Name", "Code", "Books"], 10),
    ("format", "Formats", ["ID", "Name", "Books"], 10),
]

# Tables with a column picker, and the columns shown until the user picks others
DEFAULT_COLUMNS = {
    "book": ["ID", "Title", "Subtitle", "Authors", "Publisher", "Published", "Entered"],
    "author": ["ID", "Name", "Books", "Entered"],
}

TOC = [("section-add-book", "Add a Book"), ("section-add-related", "Add Authors, Publishers and More")] + [
    (f"section-{key}", title) for key, title, _cols, _size in TABLE_SECTIONS
]


# ── Layout ──────────────────────────────────────────────────────────────────────

add_book_card = dbc.Card(dbc.CardBody([
    html.H4("Add a Book", className="card-title"),
    html.P(
        "Title, at least one author and at least one language are required. Missing an "
        "author, publisher, series, translator or editor? Add it in the next section and it "
        "shows up in these lists straight away.",
        className="text-muted",
    ),
    dbc.Row([
        field("Title", text_input("book-title", max_length=300), md=6),
        field("Subtitle (optional)", text_input("book-subtitle", max_length=300), md=6),
    ]),
    dbc.Row([
        field("Authors", dropdown("book-authors", "Select one or more authors", multi=True), md=6),
        field("Languages", dropdown("book-languages", "Select one or more languages", multi=True), md=6),
    ]),
    dbc.Row([
        field("Translators (optional)", dropdown("book-translators", "Select translators", multi=True), md=6),
        field("Editors (optional)", dropdown("book-editors", "Select editors", multi=True), md=6),
    ]),
    dbc.Row([
        field("Publisher", dropdown("book-publisher", "Select a publisher")),
        field("Format", dropdown("book-format", "Select a format")),
        field("Edition (optional)", number_input("book-edition", 1)),
    ]),
    dbc.Row([
        field("Series (optional)", dropdown("book-series", "Select a series"), md=8),
        field("Series Order (optional)", number_input("book-series-order", 0)),
    ]),
    dbc.Row([
        *date_part_fields("book-pub", "Publication"),
        field("Page Count (optional)", number_input("book-page-count", 1), md=3),
        field("Date Read (optional)", dcc.DatePickerSingle(
            id="book-date-read", display_format="YYYY-MM-DD", clearable=True,
        ), md=3),
    ]),
    dbc.Row([
        field("ISBN (optional)", text_input("book-isbn", max_length=20), md=6),
        field("ISBN13 (optional)", text_input("book-isbn13", max_length=15), md=6),
    ]),
    dbc.Button("Add Book", id="book-submit", color="primary", size="lg", className="w-100"),
    html.Div(id="book-alert", className="mt-3"),
]), className="mb-4")


def related_item(title, item_id, body, button_id, alert_id):
    return dbc.AccordionItem(
        [*body, dbc.Button(f"Add {title}", id=button_id, color="primary"), html.Div(id=alert_id, className="mt-3")],
        title=f"Add {title}",
        item_id=item_id,
    )


add_related = dbc.Accordion(
    [
        related_item("Author", "author", [
            person_fields("author"),
            dbc.Row(date_part_fields("author-birth", "Birth")),
            dbc.Row(date_part_fields("author-death", "Death")),
            dbc.Row(field(
                "Nationality (optional, ISO 3166-1 alpha-2, e.g. US, CN)",
                text_input("author-nationality", "US", max_length=2),
            )),
        ], "author-submit", "author-alert"),
        related_item("Publisher", "publisher", [
            dbc.Row(field("Publisher Name", text_input("publisher-name", max_length=200), md=6)),
        ], "publisher-submit", "publisher-alert"),
        related_item("Series", "series", [
            dbc.Row([
                field("Series Name", text_input("series-name", max_length=200), md=6),
                field("Number of Books (optional)", number_input("series-total", 1), md=2),
                field("Publisher (optional)", dropdown("series-publisher", "Select a publisher")),
            ]),
        ], "series-submit", "series-alert"),
        related_item("Translator", "translator", [person_fields("translator")], "translator-submit", "translator-alert"),
        related_item("Editor", "editor", [person_fields("editor")], "editor-submit", "editor-alert"),
    ],
    start_collapsed=True,
    always_open=True,
    className="mb-4",
)


def table_section(key, title, columns, page_size):
    children = [html.H4(title, className="mt-4")]
    shown = columns
    if key in DEFAULT_COLUMNS:
        shown = DEFAULT_COLUMNS[key]
        children.append(html.Div([
            html.Label("Columns to Display"),
            dcc.Dropdown(
                id=f"books-columns-{key}",
                options=[{"label": c, "value": c} for c in columns],
                value=shown,
                multi=True,
                placeholder="Select columns",
            ),
        ], className="mb-2"))
    children.append(data_table(f"books-table-{key}", shown, page_size))
    return html.Div(children, id=f"section-{key}")


layout = dbc.Container(
    [
        dbc.Row(dbc.Col(html.H2("Books"), width=12), className="mb-3"),
        dbc.Card(dbc.CardBody([
            html.H6("On this page", className="card-title"),
            html.Ul(
                [html.Li(html.A(label, href=f"#{anchor}", className="text-decoration-none")) for anchor, label in TOC],
                className="mb-0",
            ),
        ]), className="mb-4"),
        html.Div(add_book_card, id="section-add-book"),
        html.Div([html.H4("Add Authors, Publishers and More"), add_related], id="section-add-related"),
        *[table_section(*section) for section in TABLE_SECTIONS],
        dcc.Store(id="books-refresh", data=0),
    ],
    fluid=True,
)


# ── Callbacks: refresh dropdowns and tables ─────────────────────────────────────

OPTION_TARGETS = [
    ("book-authors", "author"),
    ("book-languages", "language"),
    ("book-translators", "translator"),
    ("book-editors", "editor"),
    ("book-publisher", "publisher"),
    ("book-format", "format"),
    ("book-series", "series"),
    ("series-publisher", "publisher"),
]


@callback(
    *[Output(id_, "options") for id_, _kind in OPTION_TARGETS],
    *[Output(f"books-table-{key}", "data") for key, *_rest in TABLE_SECTIONS],
    Input("books-refresh", "data"),
)
def refresh_page(_trigger):
    try:
        data = load_book_data()
    except Exception as e:
        print(f"Error loading book tables: {e}")
        return [[] for _ in OPTION_TARGETS] + [[] for _ in TABLE_SECTIONS]
    options = build_options(data)
    tables = build_tables(data)
    return [options[kind] for _id, kind in OPTION_TARGETS] + [tables[key] for key, *_rest in TABLE_SECTIONS]


def _register_column_picker(key, all_columns):
    """Show the picked columns in their usual order; an empty pick shows every column."""
    @callback(
        Output(f"books-table-{key}", "columns"),
        Input(f"books-columns-{key}", "value"),
    )
    def pick_columns(selected):
        return column_defs([c for c in all_columns if not selected or c in selected])

    return pick_columns


for _key, _title, _columns, _size in TABLE_SECTIONS:
    if _key in DEFAULT_COLUMNS:
        _register_column_picker(_key, _columns)


def _commit(record):
    """Add one record and commit, rolling back on failure."""
    try:
        postgres_session.add(record)
        postgres_session.commit()
    except Exception:
        postgres_session.rollback()
        raise


# ── Callback: add a book ────────────────────────────────────────────────────────

BOOK_FIELDS = [
    "book-title", "book-subtitle", "book-authors", "book-languages", "book-translators", "book-editors",
    "book-publisher", "book-format", "book-edition", "book-series", "book-series-order",
    "book-pub-year", "book-pub-month", "book-pub-day", "book-page-count", "book-isbn", "book-isbn13",
]


@callback(
    Output("book-alert", "children"),
    Output("books-refresh", "data", allow_duplicate=True),
    *[Output(id_, "value") for id_ in BOOK_FIELDS],
    Output("book-date-read", "date"),
    Input("book-submit", "n_clicks"),
    *[State(id_, "value") for id_ in BOOK_FIELDS],
    State("book-date-read", "date"),
    State("books-refresh", "data"),
    prevent_initial_call=True,
)
def add_book(_, title, subtitle, author_ids, language_ids, translator_ids, editor_ids,
             publisher_id, format_id, edition, series_id, series_order,
             pub_year, pub_month, pub_day, page_count, isbn, isbn13, date_read, refresh):
    keep = [dash.no_update] * (len(BOOK_FIELDS) + 1)
    try:
        title = optional_text(title)
        if not title:
            raise ValueError("Title is required.")
        if not author_ids:
            raise ValueError("Select at least one author.")
        if not language_ids:
            raise ValueError("Select at least one language.")
        pub_year, pub_month, pub_day = date_parts("Publication", pub_year, pub_month, pub_day)

        book_fields = dict(
            title=title,
            subtitle=optional_text(subtitle),
            isbn=optional_text(isbn),
            isbn13=optional_text(isbn13),
            publication_year=pub_year,
            publication_month=pub_month,
            publication_day=pub_day,
            page_count=optional_int(page_count, "Page count", 1),
            date_read=date.fromisoformat(date_read) if date_read else None,
            series_order=optional_int(series_order, "Series order", 0),
            edition=optional_int(edition, "Edition", 1),
            publisher_id=publisher_id,
            series_id=series_id,
            format_id=format_id,
            # set explicitly: the model's default was evaluated once, when the app started
            datetime_entered=get_est_now_clean(),
        )
    except ValueError as e:
        return (failure(str(e)), dash.no_update, *keep)

    def fetch(model, ids):
        return postgres_session.query(model).filter(model.id.in_(ids)).all() if ids else []

    try:
        # load the linked records before creating the book, so the book is never
        # half-built in the session while these queries run
        book = Book(
            **book_fields,
            authors=fetch(BookAuthor, author_ids),
            languages=fetch(BookLanguage, language_ids),
            translators=fetch(BookTranslator, translator_ids),
            editors=fetch(BookEditor, editor_ids),
        )
        _commit(book)
    except Exception as e:
        postgres_session.rollback()
        return (db_error("book", e), dash.no_update, *keep)

    cleared = [None] * (len(BOOK_FIELDS) + 1)
    return (success(f"Added book #{book.id}: {book.title}"), (refresh or 0) + 1, *cleared)


# ── Callbacks: add authors, publishers, series, translators and editors ─────────

AUTHOR_FIELDS = [
    "author-first", "author-middle", "author-last",
    "author-birth-year", "author-birth-month", "author-birth-day",
    "author-death-year", "author-death-month", "author-death-day",
    "author-nationality",
]


@callback(
    Output("author-alert", "children"),
    Output("books-refresh", "data", allow_duplicate=True),
    *[Output(id_, "value") for id_ in AUTHOR_FIELDS],
    Input("author-submit", "n_clicks"),
    *[State(id_, "value") for id_ in AUTHOR_FIELDS],
    State("books-refresh", "data"),
    prevent_initial_call=True,
)
def add_author(_, first, middle, last, birth_year, birth_month, birth_day,
               death_year, death_month, death_day, nationality, refresh):
    keep = [dash.no_update] * len(AUTHOR_FIELDS)
    try:
        first = optional_text(first)
        if not first:
            raise ValueError("First name is required.")
        birth = date_parts("Birth", birth_year, birth_month, birth_day)
        death = date_parts("Death", death_year, death_month, death_day)
        nationality = optional_text(nationality)
        if nationality:
            nationality = nationality.upper()
            if len(nationality) != 2 or not nationality.isalpha():
                raise ValueError("Nationality must be a two-letter ISO 3166-1 code, such as US or CN.")
        author = BookAuthor(
            first_name=first,
            middle_name=optional_text(middle),
            last_name=optional_text(last),
            birthday_year=birth[0], birthday_month=birth[1], birthday_day=birth[2],
            death_date_year=death[0], death_date_month=death[1], death_date_day=death[2],
            nationality=nationality,
            datetime_entered=get_est_now_clean(),
        )
        _commit(author)
    except ValueError as e:
        return (failure(str(e)), dash.no_update, *keep)
    except Exception as e:
        return (db_error("author", e), dash.no_update, *keep)
    name = person_name(author.first_name, author.middle_name, author.last_name)
    return (success(f"Added author #{author.id}: {name}"), (refresh or 0) + 1, *[None] * len(AUTHOR_FIELDS))


@callback(
    Output("publisher-alert", "children"),
    Output("books-refresh", "data", allow_duplicate=True),
    Output("publisher-name", "value"),
    Input("publisher-submit", "n_clicks"),
    State("publisher-name", "value"),
    State("books-refresh", "data"),
    prevent_initial_call=True,
)
def add_publisher(_, name, refresh):
    name = optional_text(name)
    if not name:
        return failure("Publisher name is required."), dash.no_update, dash.no_update
    publisher = BookPublisher(name=name, datetime_entered=get_est_now_clean())
    try:
        _commit(publisher)
    except Exception as e:
        return db_error("publisher", e), dash.no_update, dash.no_update
    return success(f"Added publisher #{publisher.id}: {publisher.name}"), (refresh or 0) + 1, None


@callback(
    Output("series-alert", "children"),
    Output("books-refresh", "data", allow_duplicate=True),
    Output("series-name", "value"),
    Output("series-total", "value"),
    Output("series-publisher", "value"),
    Input("series-submit", "n_clicks"),
    State("series-name", "value"),
    State("series-total", "value"),
    State("series-publisher", "value"),
    State("books-refresh", "data"),
    prevent_initial_call=True,
)
def add_series(_, name, total_books, publisher_id, refresh):
    keep = (dash.no_update,) * 4
    try:
        name = optional_text(name)
        if not name:
            raise ValueError("Series name is required.")
        series = BookSeries(
            name=name,
            total_books=optional_int(total_books, "Number of books", 1),
            publisher_id=publisher_id,
            datetime_entered=get_est_now_clean(),
        )
        _commit(series)
    except ValueError as e:
        return (failure(str(e)), *keep)
    except Exception as e:
        return (db_error("series", e), *keep)
    return success(f"Added series #{series.id}: {series.name}"), (refresh or 0) + 1, None, None, None


def _register_person_form(prefix, model, label):
    """Insert callback for the translator and editor forms, which share their fields."""
    @callback(
        Output(f"{prefix}-alert", "children"),
        Output("books-refresh", "data", allow_duplicate=True),
        Output(f"{prefix}-first", "value"),
        Output(f"{prefix}-middle", "value"),
        Output(f"{prefix}-last", "value"),
        Input(f"{prefix}-submit", "n_clicks"),
        State(f"{prefix}-first", "value"),
        State(f"{prefix}-middle", "value"),
        State(f"{prefix}-last", "value"),
        State("books-refresh", "data"),
        prevent_initial_call=True,
    )
    def add_person(_, first, middle, last, refresh):
        keep = (dash.no_update,) * 4
        first = optional_text(first)
        if not first:
            return (failure("First name is required."), *keep)
        person = model(
            first_name=first,
            middle_name=optional_text(middle),
            last_name=optional_text(last),
            datetime_entered=get_est_now_clean(),
        )
        try:
            _commit(person)
        except Exception as e:
            return (db_error(label, e), *keep)
        name = person_name(person.first_name, person.middle_name, person.last_name)
        return success(f"Added {label} #{person.id}: {name}"), (refresh or 0) + 1, None, None, None

    return add_person


add_translator = _register_person_form("translator", BookTranslator, "translator")
add_editor = _register_person_form("editor", BookEditor, "editor")
