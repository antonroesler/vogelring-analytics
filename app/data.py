from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from db import get_db_session
from sqlalchemy import event, text


def _resolve_data_path() -> Path:
    # Check for environment variable first (for Docker/production)
    env_path = os.getenv("SIGHTINGS_FILE_PATH")
    if env_path:
        return Path(env_path)

    # Fallback to default location (for local development)
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
    """Load data from database if available, fallback to CSV"""
    try:
        with get_db_session() as db:
            # Join sightings with ringing data to match CSV structure
            query = text("""
                SELECT s.*, 
                       r.ring_scheme as ringing_ring_scheme,
                       r.species as ringing_species, 
                       r.date as ringing_date,
                       r.place as ringing_place,
                       r.lat as ringing_lat,
                       r.lon as ringing_lon,
                       r.ringer as ringing_ringer,
                       r.sex as ringing_sex,
                       r.age as ringing_age,
                       r.status as ringing_status
                FROM sightings s
                LEFT JOIN ringings r ON s.ring = r.ring
            """)
            result = db.execute(query)
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

            # Apply same type conversions as CSV version
            for date_col in ["date", "ringing_date"]:
                if date_col in df.columns:
                    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

            for bool_col in ["melded", "is_exact_location"]:
                if bool_col in df.columns:
                    df[bool_col] = df[bool_col].map(_parse_boolean)

            for float_col in ["lat", "lon", "ringing_lat", "ringing_lon"]:
                if float_col in df.columns:
                    df[float_col] = pd.to_numeric(df[float_col], errors="coerce")

            # Convert UUID and integer columns to strings/proper types
            for col in df.columns:
                if df[col].dtype == "object":
                    # Convert UUIDs to strings
                    df[col] = df[col].astype(str)
                elif str(df[col].dtype).startswith("Int"):
                    # Convert nullable integers to regular integers
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

            # Keep text columns as strings and handle NaN
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

    except Exception as e:
        st.warning(f"Database connection failed, falling back to CSV: {e}")
        return load_data_from_csv()


@st.cache_data(show_spinner=False)
def load_data_from_csv() -> pd.DataFrame:
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
