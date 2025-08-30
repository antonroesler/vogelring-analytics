from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


def _resolve_data_path() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "sightings.csv"


def _parse_boolean(value: Any) -> bool | None:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "wahr", "1", "ja", "yes"}:
        return True
    if text in {"false", "falsch", "0", "nein", "no"}:
        return False
    return None


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    csv_path = _resolve_data_path()
    df = pd.read_csv(
        csv_path, sep=";", dtype=str, keep_default_na=True, na_values=["", "NA", "NaN"]
    )  # read all as str first

    # Normalize column names (strip spaces)
    df.columns = [c.strip() for c in df.columns]

    # Type conversions
    for date_col in ["date", "ringing_date"]:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    for bool_col in ["melded", "is_exact_location"]:
        if bool_col in df.columns:
            df[bool_col] = df[bool_col].map(_parse_boolean)

    for float_col in ["lat", "lon", "ringing_lat", "ringing_lon"]:
        if float_col in df.columns:
            df[float_col] = pd.to_numeric(df[float_col], errors="coerce")

    # Keep a copy of original string columns for searching
    for text_col in [
        "species",
        "ring",
        "reading",
        "place",
        "area",
        "sex",
        "age",
        "partner",
        "status",
        "habitat",
        "field_fruit",
        "comment",
        "melder",
        "ringing_ring_scheme",
        "ringing_species",
        "ringing_place",
        "ringing_ringer",
    ]:
        if text_col in df.columns:
            df[text_col] = df[text_col].fillna("").astype(str)

    # Convenience derived columns
    if "date" in df.columns:
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month

    return df


def unique_nonempty(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    values = df[column].dropna().astype(str).map(str.strip).loc[lambda s: s != ""].unique().tolist()
    values.sort()
    return values
