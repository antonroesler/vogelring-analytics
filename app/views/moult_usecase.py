from __future__ import annotations

import pandas as pd
import streamlit as st
import altair as alt

from util.col_mapping import mapping
from util.datasets import dataset_selector_ui, load_dataset
from data import unique_nonempty


def _get_years_from_df(df: pd.DataFrame) -> list[int]:
    """Extract available years from the dataset."""
    if "year" not in df.columns and "date" in df.columns:
        parsed = pd.to_datetime(df["date"], errors="coerce")
        years = parsed.dt.year.dropna().unique()
    else:
        years = pd.to_numeric(df.get("year"), errors="coerce").dropna().unique()

    return sorted([int(y) for y in years if not pd.isna(y)])


def _get_month_bins() -> list[str]:
    """Get ordered month bins for the year."""
    return ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _month_to_bin(month: int) -> str:
    """Convert month number to German month name."""
    bins = _get_month_bins()
    if 1 <= month <= 12:
        return bins[month - 1]
    return "Unbekannt"


def _filter_by_date_range(df: pd.DataFrame, year: int, start_month: int, end_month: int) -> pd.DataFrame:
    """Filter dataframe by date range within a specific year."""
    work = df.copy()

    # Ensure we have year and month columns
    if "year" not in work.columns and "date" in work.columns:
        parsed = pd.to_datetime(work["date"], errors="coerce")
        work["year"] = parsed.dt.year
        work["month"] = parsed.dt.month

    # Filter by year
    work = work[pd.to_numeric(work.get("year"), errors="coerce") == year]

    # Filter by month range
    month_series = pd.to_numeric(work.get("month"), errors="coerce")
    if start_month <= end_month:
        # Normal range (e.g., March to August)
        work = work[(month_series >= start_month) & (month_series <= end_month)]
    else:
        # Wrap-around range (e.g., November to February)
        work = work[(month_series >= start_month) | (month_series <= end_month)]

    return work


def _filter_by_status(df: pd.DataFrame, status_filter: str) -> pd.DataFrame:
    """Filter dataframe by status."""
    if not status_filter or status_filter == "Alle":
        return df
    return df[df.get("status", "").astype(str).str.strip() == status_filter]


def _find_moulting_birds(
    df: pd.DataFrame,
    year: int,
    place: str,
    species: str,
    filter_type: str,
    start_month: int = 1,
    end_month: int = 12,
    status_filter: str = "",
) -> pd.DataFrame:
    """Find birds that match the moulting criteria."""
    work = df.copy()

    # Filter by species and place
    work = work[
        (work.get("species", "").astype(str).str.strip() == species)
        & (work.get("place", "").astype(str).str.strip() == place)
    ]

    # Apply the user-defined filter
    if filter_type == "Zeitraum":
        work = _filter_by_date_range(work, year, start_month, end_month)
    elif filter_type == "Status":
        work = work[pd.to_numeric(work.get("year"), errors="coerce") == year]
        work = _filter_by_status(work, status_filter)

    # Get unique rings (the moulting birds)
    rings = work.get("ring", "").astype(str).str.strip()
    unique_rings = rings[rings != ""].unique()

    return work, unique_rings


def _analyze_rest_of_year(
    df: pd.DataFrame,
    moulting_rings: list[str],
    year: int,
    filter_type: str,
    moulting_place: str,
    start_month: int = 1,
    end_month: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Analyze where the moulting birds spend the rest of the year.

    Returns:
        tuple: (all_rest_year_df, different_places_df)
        - all_rest_year_df: All sightings outside moulting period (including same place)
        - different_places_df: Only sightings at different places than moulting location
    """
    # Get all sightings of the moulting birds in the same year
    work = df[
        (df.get("ring", "").astype(str).str.strip().isin(moulting_rings))
        & (pd.to_numeric(df.get("year"), errors="coerce") == year)
    ].copy()

    # Exclude the moulting period
    if filter_type == "Zeitraum":
        # Ensure we have month column
        if "month" not in work.columns and "date" in work.columns:
            parsed = pd.to_datetime(work["date"], errors="coerce")
            work["month"] = parsed.dt.month

        month_series = pd.to_numeric(work.get("month"), errors="coerce")
        if start_month <= end_month:
            # Normal range - exclude this range
            work = work[~((month_series >= start_month) & (month_series <= end_month))]
        else:
            # Wrap-around range - exclude this range
            work = work[~((month_series >= start_month) | (month_series <= end_month))]

    # Split into same place vs different places
    all_rest_year = work.copy()
    different_places = work[work.get("place", "").astype(str).str.strip() != moulting_place].copy()

    return all_rest_year, different_places


def _create_place_distribution_chart(df: pd.DataFrame) -> alt.Chart:
    """Create a bar chart showing distribution of sightings by place."""
    place_counts = (
        df.groupby("place")
        .agg({"ring": "nunique", "id": "count"})
        .rename(columns={"ring": "unique_rings", "id": "total_sightings"})
        .reset_index()
        .sort_values("unique_rings", ascending=False)
        .head(10)  # Top 10 places
    )

    chart = (
        alt.Chart(place_counts)
        .mark_bar()
        .encode(
            x=alt.X("unique_rings:Q", title="Anzahl eindeutiger Ringe"),
            y=alt.Y("place:N", title="Ort", sort="-x"),
            color=alt.Color("unique_rings:Q", scale=alt.Scale(scheme="viridis"), title="Ringe"),
            tooltip=[
                alt.Tooltip("place:N", title="Ort"),
                alt.Tooltip("unique_rings:Q", title="Eindeutige Ringe"),
                alt.Tooltip("total_sightings:Q", title="Gesamte Beobachtungen"),
            ],
        )
        .properties(title="Verteilung der Mausernden Vögel nach Orten (Rest des Jahres)", width="container", height=300)
    )

    return chart


def _create_temporal_distribution_chart(df: pd.DataFrame) -> alt.Chart:
    """Create a chart showing temporal distribution throughout the year."""
    # Ensure we have month column
    work = df.copy()
    if "month" not in work.columns and "date" in work.columns:
        parsed = pd.to_datetime(work["date"], errors="coerce")
        work["month"] = parsed.dt.month

    work["month_name"] = pd.to_numeric(work.get("month"), errors="coerce").map(_month_to_bin)

    monthly_counts = (
        work.groupby("month_name")
        .agg({"ring": "nunique", "id": "count"})
        .rename(columns={"ring": "unique_rings", "id": "total_sightings"})
        .reset_index()
    )

    # Ensure all months are present
    all_months = pd.DataFrame({"month_name": _get_month_bins()})
    monthly_counts = all_months.merge(monthly_counts, how="left", on="month_name").fillna(0)

    chart = (
        alt.Chart(monthly_counts)
        .mark_bar()
        .encode(
            x=alt.X("month_name:N", title="Monat", sort=_get_month_bins()),
            y=alt.Y("unique_rings:Q", title="Anzahl eindeutiger Ringe"),
            color=alt.Color("unique_rings:Q", scale=alt.Scale(scheme="blues"), title="Ringe"),
            tooltip=[
                alt.Tooltip("month_name:N", title="Monat"),
                alt.Tooltip("unique_rings:Q", title="Eindeutige Ringe"),
                alt.Tooltip("total_sightings:Q", title="Gesamte Beobachtungen"),
            ],
        )
        .properties(title="Zeitliche Verteilung der Beobachtungen (Rest des Jahres)", width="container", height=300)
    )

    return chart


def _create_movement_summary_table(
    moulting_df: pd.DataFrame, all_rest_year_df: pd.DataFrame, different_places_df: pd.DataFrame, moulting_place: str
) -> pd.DataFrame:
    """Create a summary table of bird movements."""
    total_moulting_rings = moulting_df.get("ring", "").astype(str).str.strip().nunique()

    # Get unique rings for each category
    all_rest_year_rings = set(all_rest_year_df.get("ring", "").astype(str).str.strip().unique())
    different_places_rings = set(different_places_df.get("ring", "").astype(str).str.strip().unique())

    # Birds seen anywhere in the rest of the year (including same place)
    seen_rest_of_year = len(all_rest_year_rings)

    # Birds only seen at moulting place (not seen elsewhere during rest of year)
    only_moulting_place = total_moulting_rings - seen_rest_of_year

    # Birds seen at same place during rest of year
    same_place_rings = all_rest_year_rings - different_places_rings
    same_place_rest = len(same_place_rings)

    # Birds seen at different places during rest of year
    different_places_count = len(different_places_rings)

    summary = pd.DataFrame(
        {
            "Kategorie": [
                "Gesamt (Mausernde Vögel)",
                "Im Rest des Jahres gesehen",
                "Nur während Mauserzeit gesehen",
                "Am selben Ort (Rest des Jahres)",
                "An anderen Orten gesehen",
            ],
            "Anzahl Ringe": [
                total_moulting_rings,
                seen_rest_of_year,
                only_moulting_place,
                same_place_rest,
                different_places_count,
            ],
            "Prozent": [
                100.0,
                (seen_rest_of_year / total_moulting_rings * 100) if total_moulting_rings > 0 else 0,
                (only_moulting_place / total_moulting_rings * 100) if total_moulting_rings > 0 else 0,
                (same_place_rest / total_moulting_rings * 100) if total_moulting_rings > 0 else 0,
                (different_places_count / total_moulting_rings * 100) if total_moulting_rings > 0 else 0,
            ],
        }
    )

    return summary


def render_moult_usecase() -> None:
    st.header("Mauser-Analyse")
    st.markdown("""
    Diese Analyse untersucht, wo Ringvögel, die an einem bestimmten Ort mausern, 
    den Rest des Jahres verbringen.
    """)

    selected = dataset_selector_ui()
    if not selected:
        return

    meta, df = load_dataset(selected)
    if meta is None or df is None:
        st.error("Datensatz konnte nicht geladen werden.")
        return

    # Filter to included rows by default
    include_hidden = st.checkbox("Auch ausgeblendete Zeilen anzeigen", value=False, key="moult_show_hidden")
    if "included" in df.columns and not include_hidden:
        mask = pd.Series(df["included"]).astype(str).isin(["1", "True", "true", "TRUE"])
        df = df.loc[mask]

    if len(df) == 0:
        st.info("Keine Daten im ausgewählten Datensatz vorhanden.")
        return

    st.subheader("1. Parameter definieren")

    # Year selection
    years = _get_years_from_df(df)
    if not years:
        st.error("Keine Jahresangaben in den Daten gefunden.")
        return

    col1, col2 = st.columns(2)
    with col1:
        year = st.selectbox("Jahr", options=years, index=len(years) - 1, key="moult_year")

    # Species selection
    species_options = unique_nonempty(df, "species")
    if not species_options:
        st.error("Keine Arten in den Daten gefunden.")
        return

    with col2:
        species = st.selectbox("Art", options=species_options, key="moult_species")

    # Place selection
    place_options = unique_nonempty(df, "place")
    if not place_options:
        st.error("Keine Orte in den Daten gefunden.")
        return

    place = st.selectbox("Mauserort", options=place_options, key="moult_place")

    st.subheader("2. Mausernde Vögel definieren")
    st.markdown("Definieren Sie, welche Vögel als 'mausernde Vögel' gelten sollen:")

    filter_type = st.radio(
        "Filtertyp",
        options=["Zeitraum", "Status"],
        horizontal=True,
        key="moult_filter_type",
        help="Zeitraum: Vögel, die in einem bestimmten Zeitraum gesehen wurden\nStatus: Vögel mit einem bestimmten Status",
    )

    start_month = end_month = 1
    status_filter = ""

    if filter_type == "Zeitraum":
        st.markdown("**Zeitraum auswählen:**")
        month_names = _get_month_bins()
        col1, col2 = st.columns(2)
        with col1:
            start_month_name = st.selectbox(
                "Von Monat", options=month_names, index=5, key="moult_start_month"
            )  # Default June
            start_month = month_names.index(start_month_name) + 1
        with col2:
            end_month_name = st.selectbox(
                "Bis Monat", options=month_names, index=7, key="moult_end_month"
            )  # Default August
            end_month = month_names.index(end_month_name) + 1

        st.info(f"Zeitraum: {start_month_name} bis {end_month_name} {year}")

    elif filter_type == "Status":
        status_options = ["Alle"] + unique_nonempty(df, "status")
        status_filter = st.selectbox("Status", options=status_options, key="moult_status")

        if status_filter != "Alle":
            st.info(f"Status: {status_filter} im Jahr {year}")

    # Analysis button
    if st.button("Analyse starten", type="primary"):
        with st.spinner("Analysiere Daten..."):
            # Find moulting birds
            moulting_df, moulting_rings = _find_moulting_birds(
                df, year, place, species, filter_type, start_month, end_month, status_filter
            )

            if len(moulting_rings) == 0:
                st.warning("Keine Vögel gefunden, die den Kriterien entsprechen.")
                return

            st.success(f"**{len(moulting_rings)} eindeutige Ringe** gefunden, die den Kriterien entsprechen.")

            # Analyze rest of year
            all_rest_year_df, different_places_df = _analyze_rest_of_year(
                df, list(moulting_rings), year, filter_type, place, start_month, end_month
            )

            st.subheader("3. Ergebnisse")

            # Summary table
            st.markdown("**Zusammenfassung:**")
            summary_table = _create_movement_summary_table(moulting_df, all_rest_year_df, different_places_df, place)

            # Format the table nicely
            summary_styled = summary_table.copy()
            summary_styled["Prozent"] = summary_styled["Prozent"].round(1).astype(str) + "%"

            st.dataframe(
                summary_styled,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Kategorie": st.column_config.TextColumn("Kategorie", width="large"),
                    "Anzahl Ringe": st.column_config.NumberColumn("Anzahl Ringe", width="medium"),
                    "Prozent": st.column_config.TextColumn("Prozent", width="small"),
                },
            )

            if len(all_rest_year_df) > 0:
                st.subheader("4. Detailanalyse")

                # Place distribution chart - show only different places
                if len(different_places_df) > 0:
                    st.markdown("**Wo verbringen die Vögel den Rest des Jahres? (Andere Orte als Mauserort)**")
                    place_chart = _create_place_distribution_chart(different_places_df)
                    st.altair_chart(place_chart, use_container_width=True)
                else:
                    st.info(
                        "Alle mausernden Vögel wurden nur am Mauserort oder gar nicht außerhalb der Mauserzeit gesehen."
                    )

                # Temporal distribution chart - show all rest of year data
                st.markdown("**Wann werden die Vögel den Rest des Jahres gesehen?**")
                temporal_chart = _create_temporal_distribution_chart(all_rest_year_df)
                st.altair_chart(temporal_chart, use_container_width=True)

                # Detailed data table
                with st.expander("Detaillierte Beobachtungen anzeigen (alle Orte)"):
                    display_cols = ["ring", "date", "place", "area", "status", "melder"]
                    available_cols = [c for c in display_cols if c in all_rest_year_df.columns]

                    if available_cols:
                        detail_df = all_rest_year_df[available_cols].rename(columns=mapping)
                        st.dataframe(detail_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("Keine detaillierten Daten verfügbar.")

                # Show different places data separately
                if len(different_places_df) > 0:
                    with st.expander("Beobachtungen an anderen Orten"):
                        display_cols = ["ring", "date", "place", "area", "status", "melder"]
                        available_cols = [c for c in display_cols if c in different_places_df.columns]

                        if available_cols:
                            detail_df = different_places_df[available_cols].rename(columns=mapping)
                            st.dataframe(detail_df, use_container_width=True, hide_index=True)
            else:
                st.info("Keine Beobachtungen der mausernden Vögel außerhalb des definierten Zeitraums/Status gefunden.")
