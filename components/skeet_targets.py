"""Standard skeet target sequences, shared by the skeet pages.

Each entry is (label, station, house, single_double, pair_order). The order of
the list is the order the targets are shot, so a shot's 1-based position in the
list is its shot_order. Labels repeat within a round — ISSF shoots station 4
doubles twice, in both orders — so a target is identified by its position, not
its label.
"""

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

    Labels repeat within a round, so the position — not the label — is what
    identifies a column.
    """
    return f"shot-{index}"


def shot_columns(sequence):
    """DataTable column definitions for a target sequence."""
    return [
        {"name": label, "id": cell_id(i), "type": "numeric"}
        for i, (label, *_rest) in enumerate(sequence, start=1)
    ]


def miss_highlight(sequence):
    """style_data_conditional entries that flag any cell set to 0."""
    return [
        {
            "if": {"filter_query": f"{{{cell_id(i)}}} = 0", "column_id": cell_id(i)},
            "backgroundColor": "#f8d7da",
            "fontWeight": "bold",
        }
        for i in range(1, len(sequence) + 1)
    ]


SHOT_CELL_STYLE = {
    "textAlign": "center",
    "padding": "6px",
    "minWidth": "52px",
    "width": "52px",
    "maxWidth": "52px",
}

SHOT_HEADER_STYLE = {
    "backgroundColor": "rgb(230, 230, 230)",
    "fontWeight": "bold",
    "whiteSpace": "normal",
}
