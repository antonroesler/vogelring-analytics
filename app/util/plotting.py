from __future__ import annotations

from typing import Iterable

import pandas as pd

from .col_mapping import mapping


# Columns that should NOT be selectable by users for axes/color encodings.
# These may be used internally (e.g., map coordinates) but not exposed as plottable attributes.
NON_PLOTTABLE_INTERNAL: set[str] = {
    "id",
    "excel_id",
    "comment",
    "ringing_ring_scheme",
    "is_exact_location",
    "lat",
    "lon",
    "ringing_lat",
    "ringing_lon",
}


def filter_plottable_columns(columns: Iterable[str]) -> list[str]:
    return [c for c in columns if c not in NON_PLOTTABLE_INTERNAL and c in mapping]


def get_plottable_categorical_columns(df: pd.DataFrame, *, max_unique: int = 30) -> list[str]:
    cols = filter_plottable_columns(df.columns)
    categorical: list[str] = []
    for c in cols:
        # treat as categorical if limited unique values
        uniq = df[c].dropna().astype(str).str.strip()
        nunique = uniq.nunique()
        if 1 <= nunique <= max_unique:
            categorical.append(c)
    categorical.sort(key=lambda c: mapping.get(c, c))
    return categorical


def get_plottable_numeric_columns(df: pd.DataFrame) -> list[str]:
    cols = filter_plottable_columns(df.columns)
    numeric: list[str] = []
    preferred = {
        "year",
        "month",
        "breed_size",
        "family_size",
        "small_group_size",
        "large_group_size",
    }
    for c in cols:
        series = pd.to_numeric(df[c], errors="coerce")
        if series.notna().any():
            numeric.append(c)
    numeric.sort(key=lambda c: (c not in preferred, mapping.get(c, c)))
    return numeric
