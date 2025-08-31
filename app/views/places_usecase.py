from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st
import altair as alt

from util.datasets import dataset_selector_ui, load_dataset


BIN_ORDER: list[str] = ["Jan–Feb", "Mär–Apr", "Mai–Jun", "Jul–Aug", "Sep–Okt", "Nov–Dez"]


def _two_month_bin_label(month: int) -> str:
    if 1 <= month <= 2:
        return "Jan–Feb"
    if 3 <= month <= 4:
        return "Mär–Apr"
    if 5 <= month <= 6:
        return "Mai–Jun"
    if 7 <= month <= 8:
        return "Jul–Aug"
    if 9 <= month <= 10:
        return "Sep–Okt"
    if 11 <= month <= 12:
        return "Nov–Dez"
    return "?"


def _complete_index(bins: Iterable[str], places: Iterable[str]) -> pd.DataFrame:
    prod = pd.MultiIndex.from_product([list(bins), list(places)], names=["bin", "place"]).to_frame(index=False)
    return prod


def _aggregate_counts(df: pd.DataFrame, year: int, places: list[str]) -> pd.DataFrame:
    work = df.copy()
    # Coerce year/month to numeric for comparisons
    work["year"] = pd.to_numeric(work.get("year"), errors="coerce")
    work["month"] = pd.to_numeric(work.get("month"), errors="coerce")
    work = work[work["year"] == year]
    # Guard: ring and place
    work["ring"] = work["ring"].astype(str).str.strip()
    work["place"] = work["place"].astype(str).str.strip()
    work = work[(work["ring"] != "") & (work["place"].isin(places))]

    # Ensure month exists
    if "month" not in work.columns and "date" in work.columns:
        work["month"] = pd.to_datetime(work["date"], errors="coerce").dt.month

    work["bin"] = work["month"].astype(int).map(_two_month_bin_label)

    grouped = work.groupby(["bin", "place"], dropna=False)["ring"].nunique().reset_index(name="count")

    # Complete missing combinations with 0
    complete = _complete_index(BIN_ORDER, places)
    merged = complete.merge(grouped, how="left", on=["bin", "place"]).fillna({"count": 0})
    merged["count"] = merged["count"].astype(int)

    # Order bins
    merged["bin"] = pd.Categorical(merged["bin"], categories=BIN_ORDER, ordered=True)

    return merged.sort_values(["bin", "place"]).reset_index(drop=True)


def render_places_usecase() -> None:
    st.header("Orte")
    selected = dataset_selector_ui()
    if not selected:
        return
    meta, df = load_dataset(selected)
    if meta is None or df is None:
        st.error("Datensatz konnte nicht geladen werden.")
        return

    # Filter to included rows by default
    include_hidden = st.checkbox("Auch ausgeblendete Zeilen anzeigen", value=False, key="places_show_hidden")
    if "included" in df.columns and not include_hidden:
        mask = pd.Series(df["included"]).astype(str).isin(["1", "True", "true", "TRUE"])  # type: ignore[arg-type]
        df = df.loc[mask]

    # Year selection
    # Infer year/month if absent
    if "year" not in df.columns and "date" in df.columns:
        parsed = pd.to_datetime(df["date"], errors="coerce")
        df = df.copy()
        df["year"] = parsed.dt.year
        df["month"] = parsed.dt.month

    years = sorted([int(y) for y in pd.to_numeric(df.get("year"), errors="coerce").dropna().unique().tolist()])
    if not years:
        st.info("Keine Jahresangaben in den Daten vorhanden.")
        return

    col1, col2 = st.columns([1, 3])
    with col1:
        year = st.selectbox("Jahr", options=years, index=len(years) - 1, key="places_year")

    # Places selection: sorted by frequency within the selected dataset
    place_counts = (
        df.assign(place=df.get("place", "").astype(str).str.strip())
        .loc[lambda d: d["place"] != ""]
        .groupby("place")["place"]
        .count()
        .sort_values(ascending=False)
    )
    all_places_sorted = place_counts.index.tolist()

    with col2:
        places = st.multiselect(
            "Orte (max. 5)", options=all_places_sorted, default=all_places_sorted[:3], key="places_multi"
        )

    if len(places) == 0:
        st.info("Bitte mindestens einen Ort auswählen.")
        return

    if len(places) > 5:
        st.warning("Es sind maximal fünf Orte erlaubt. Es werden die ersten fünf verwendet.")
        places = places[:5]

    agg = _aggregate_counts(df, int(year), places)

    # Build grouped bar chart
    chart = (
        alt.Chart(agg)
        .mark_bar()
        .encode(
            x=alt.X("bin:N", title="Zeitraum", sort=BIN_ORDER),
            xOffset=alt.XOffset("place:N"),
            y=alt.Y("count:Q", title="Anzahl eindeutiger Ringe"),
            color=alt.Color("place:N", title="Ort"),
            tooltip=[
                alt.Tooltip("bin:N", title="Zeitraum"),
                alt.Tooltip("place:N", title="Ort"),
                alt.Tooltip("count:Q", title="Anzahl"),
            ],
        )
    )

    st.subheader("Eindeutige Ringe pro Zeitraum und Ort")
    st.altair_chart(chart.properties(width="container", height=420), use_container_width=True)
