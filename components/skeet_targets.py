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


def blank_shot_row(sequence):
    """One table row for a fresh round: every target starts as a hit."""
    return {cell_id(i): 1 for i in range(1, len(sequence) + 1)}


def parse_shot_cells(sequence, row):
    """Read a table row into 1/0 results.

    Returns (results, bad), where `bad` describes every cell that is not 0 or 1.
    """
    results = []
    bad = []
    for i, (label, *_rest) in enumerate(sequence, start=1):
        try:
            value = int(row.get(cell_id(i)))
        except (TypeError, ValueError):
            bad.append(f"{label} (position {i})")
            continue
        if value not in (0, 1):
            bad.append(f"{label} (position {i})")
            continue
        results.append(value)
    return results, bad


def build_shot_rows(sequence, results):
    """Turn 1/0 results into skeet_shot column values.

    Returns (rows, option_note); `option_note` describes the option shot, if the
    sequence has one.
    """
    rows = []
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

        rows.append({
            "shot_order": i,
            "target_number": target_number,
            "station": station,
            "house": house,
            "single_double": single_double,
            "pair_order": pair_order,
            "is_option": is_option,
            "broken": bool(results[i - 1]),
        })
    return rows, option_note


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
