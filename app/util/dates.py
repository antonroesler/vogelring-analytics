from __future__ import annotations

from typing import Iterable

import pandas as pd

try:
    # Optional: mapping is only used to detect display names
    from .col_mapping import mapping as _col_mapping  # type: ignore
except Exception:  # pragma: no cover - defensive import in case of circulars
    _col_mapping = {}


DATE_INTERNAL_COLUMNS: list[str] = [
    "date",
    "ringing_date",
]

DATE_DISPLAY_COLUMNS: list[str] = [_col_mapping.get(internal, internal) for internal in DATE_INTERNAL_COLUMNS]

DATE_DISPLAY_FORMAT = "%d.%m.%Y"


def _format_date_series(series: pd.Series, fmt: str = DATE_DISPLAY_FORMAT) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    formatted = parsed.dt.strftime(fmt)
    # Ensure missing values render as empty strings
    return formatted.fillna("")


def format_date_columns_for_display(
    df: pd.DataFrame,
    *,
    date_columns: Iterable[str] | None = None,
    include_display_names: bool = True,
    fmt: str = DATE_DISPLAY_FORMAT,
) -> pd.DataFrame:
    """Return a copy of df with known date columns formatted as DD.MM.YYYY strings.

    - If date_columns is provided, only those columns (if present) are formatted.
    - Otherwise, the function will format any of the known internal or display date columns
      present in the dataframe.
    - Never mutates the input dataframe.
    """
    df_out = df.copy()

    if date_columns is not None:
        targets = [c for c in date_columns if c in df_out.columns]
    else:
        candidates = set(DATE_INTERNAL_COLUMNS)
        if include_display_names:
            candidates.update(DATE_DISPLAY_COLUMNS)
        targets = [c for c in candidates if c in df_out.columns]

    for col in targets:
        try:
            df_out[col] = _format_date_series(df_out[col], fmt)
        except Exception:
            # Be tolerant; skip columns that can't be parsed for any reason
            pass

    return df_out


def add_vogelring_link_column(df: pd.DataFrame, source_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add a URL column ("Eintrag") for vogelring.com/entries/<id> when 'id' exists.

    The result is suitable for Streamlit's LinkColumn via column_config. We return
    plain URL strings (not HTML) so Streamlit can render clickable links. The
    function aligns rows by index and requires that ``df`` and ``source_df``
    have equal length and compatible indices.

    Args:
        df: The dataframe prepared for display (may not include 'id').
        source_df: The source dataframe that contains the 'id' column.

    Returns:
        A copy of ``df`` with a rightmost column 'Eintrag' containing URL strings.
    """
    df_out = df.copy()

    id_source = source_df if source_df is not None else df_out

    if "id" not in id_source.columns:
        return df_out

    if len(id_source) != len(df_out):
        return df_out

    urls: list[str] = []
    for idx in df_out.index:
        try:
            entry_id = id_source.loc[idx, "id"]
            if pd.notna(entry_id) and str(entry_id).strip():
                urls.append(f"https://vogelring.com/entries/{entry_id}")
            else:
                urls.append("")
        except (KeyError, IndexError):
            urls.append("")

    df_out["Eintrag"] = urls

    return df_out


def prepare_dataframe_for_display(
    df: pd.DataFrame,
    source_df: pd.DataFrame | None = None,
    *,
    date_columns: Iterable[str] | None = None,
    include_display_names: bool = True,
    fmt: str = DATE_DISPLAY_FORMAT,
) -> pd.DataFrame:
    """Prepare dataframe for display by formatting dates and adding vogelring link column.

    This is a convenience function that combines date formatting and link column addition.
    """
    # First format dates
    df_out = format_date_columns_for_display(
        df, date_columns=date_columns, include_display_names=include_display_names, fmt=fmt
    )

    # Then add link column
    df_out = add_vogelring_link_column(df_out, source_df)

    return df_out
