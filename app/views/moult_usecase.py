from __future__ import annotations

import pandas as pd
import streamlit as st
import altair as alt

from util.col_mapping import mapping
from util.datasets import dataset_selector_ui, load_dataset
from util.dates import prepare_dataframe_for_display
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


def _filter_by_date_range_multi_year(
    df: pd.DataFrame, year_range: list[int], start_month: int, end_month: int
) -> pd.DataFrame:
    """Filter dataframe by date range across multiple years."""
    work = df.copy()

    # Ensure we have year and month columns
    if "year" not in work.columns and "date" in work.columns:
        parsed = pd.to_datetime(work["date"], errors="coerce")
        work["year"] = parsed.dt.year
        work["month"] = parsed.dt.month

    # Filter by year range
    work = work[pd.to_numeric(work.get("year"), errors="coerce").isin(year_range)]

    # Filter by month range
    month_series = pd.to_numeric(work.get("month"), errors="coerce")
    if start_month <= end_month:
        # Normal range (e.g., March to August)
        work = work[(month_series >= start_month) & (month_series <= end_month)]
    else:
        # Wrap-around range (e.g., November to February)
        work = work[(month_series >= start_month) | (month_series <= end_month)]

    return work


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
    year_range: list[int],
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

    # Filter by year range
    work = work[pd.to_numeric(work.get("year"), errors="coerce").isin(year_range)]

    # Apply the user-defined filter
    if filter_type == "Zeitraum":
        work = _filter_by_date_range_multi_year(work, year_range, start_month, end_month)
    elif filter_type == "Status":
        work = _filter_by_status(work, status_filter)

    # Get unique rings (the moulting birds)
    rings = work.get("ring", "").astype(str).str.strip()
    unique_rings = rings[rings != ""].unique()

    return work, unique_rings


def _analyze_rest_of_year(
    df: pd.DataFrame,
    moulting_rings: list[str],
    year_range: list[int],
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
        - moulting_place_df: Only sightings at moulting location
    """
    # Get all sightings of the moulting birds in the year range
    work = df[
        (df.get("ring", "").astype(str).str.strip().isin(moulting_rings))
        & (pd.to_numeric(df.get("year"), errors="coerce").isin(year_range))
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
    moulting_place = work[work.get("place", "").astype(str).str.strip() == moulting_place].copy()

    return all_rest_year, different_places, moulting_place


def _create_place_distribution_chart(df: pd.DataFrame) -> tuple[alt.Chart, pd.DataFrame]:
    """Create an interactive bar chart showing distribution of sightings by place.

    Returns:
        tuple: (chart, place_counts_df) - chart and the underlying data for selection
    """
    place_counts = (
        df.groupby("place")
        .agg({"ring": "nunique", "id": "count"})
        .rename(columns={"ring": "unique_rings", "id": "total_sightings"})
        .reset_index()
        .sort_values("unique_rings", ascending=False)
        .head(10)  # Top 10 places
    )

    # Create a selection that chooses based on click
    click = alt.selection_point(fields=["place"])

    chart = (
        alt.Chart(place_counts)
        .mark_bar(cursor="pointer")
        .add_params(click)
        .encode(
            x=alt.X("unique_rings:Q", title="Anzahl eindeutiger Ringe"),
            y=alt.Y(
                "place:N",
                title="Ort",
                sort="-x",
                axis=alt.Axis(labelLimit=300, labelOverlap="greedy"),
            ),
            color=alt.condition(
                click,
                alt.Color("unique_rings:Q", scale=alt.Scale(scheme="viridis"), title="Ringe"),
                alt.value("lightgray"),
            ),
            stroke=alt.condition(click, alt.value("black"), alt.value("transparent")),
            strokeWidth=alt.condition(click, alt.value(2), alt.value(0)),
            tooltip=[
                alt.Tooltip("place:N", title="Ort"),
                alt.Tooltip("unique_rings:Q", title="Eindeutige Ringe"),
                alt.Tooltip("total_sightings:Q", title="Gesamte Beobachtungen"),
            ],
        )
        .properties(
            title="Verteilung der Mausernden Vögel nach Orten",
            width="container",
            height=128 + 32 * len(place_counts),
        )
    )

    return chart, place_counts


def _create_temporal_distribution_chart(df: pd.DataFrame) -> alt.Chart:
    """Create a chart showing temporal distribution throughout the year."""

    # Ensure we have month column
    work = df.copy()
    if "month" not in work.columns and "date" in work.columns:
        parsed = pd.to_datetime(work["date"], errors="coerce")
        work["month"] = parsed.dt.month

    work["month_name"] = pd.to_numeric(work.get("month"), errors="coerce").map(_month_to_bin)

    # Get top 5 places by unique rings
    place_counts = work.groupby("place")["ring"].nunique().sort_values(ascending=False)
    top_5_places = place_counts.head(5).index.tolist()

    # Group places: top 5 + "Andere"
    work["place_grouped"] = work["place"].apply(lambda x: x if x in top_5_places else "Andere")

    # Create monthly counts by place
    monthly_place_counts = (
        work.groupby(["month_name", "place_grouped"])
        .agg({"ring": "nunique"})
        .rename(columns={"ring": "unique_rings"})
        .reset_index()
    )

    # Ensure all months and places are present
    all_months = pd.DataFrame({"month_name": _get_month_bins()})
    all_places = pd.DataFrame({"place_grouped": top_5_places + ["Andere"]})
    month_place_grid = all_months.assign(key=1).merge(all_places.assign(key=1), on="key").drop("key", axis=1)
    monthly_place_counts = month_place_grid.merge(
        monthly_place_counts, how="left", on=["month_name", "place_grouped"]
    ).fillna(0)

    # Create sort order: "Andere" = 0 (bottom), then top 5 places in descending order (1-5)
    place_order_map = {"Andere": 0}
    for i, place in enumerate(top_5_places):
        place_order_map[place] = i + 1

    monthly_place_counts["sort_order"] = monthly_place_counts["place_grouped"].map(place_order_map)

    chart = (
        alt.Chart(monthly_place_counts)
        .mark_bar()
        .encode(
            x=alt.X("month_name:N", title="Monat", sort=_get_month_bins()),
            y=alt.Y("unique_rings:Q", title="Anzahl eindeutiger Ringe"),
            color=alt.Color("place_grouped:N", title="Ort", scale=alt.Scale(scheme="category10")),
            order=alt.Order("sort_order:O"),
            tooltip=[
                alt.Tooltip("month_name:N", title="Monat"),
                alt.Tooltip("place_grouped:N", title="Ort"),
                alt.Tooltip("unique_rings:Q", title="Eindeutige Ringe"),
            ],
        )
        .properties(title="Zeitliche Verteilung der Beobachtungen (Rest des Jahres)", width="container", height=300)
    )

    return chart


def _create_movement_summary_table(
    moulting_df: pd.DataFrame,
    all_rest_year_df: pd.DataFrame,
    different_places_df: pd.DataFrame,
    moulting_place: str,
    moulting_place_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create a summary table of bird movements."""
    total_moulting_rings = moulting_df.get("ring", "").astype(str).str.strip().nunique()

    # Get unique rings for each category
    all_rest_year_rings = set(all_rest_year_df.get("ring", "").astype(str).str.strip().unique())
    different_places_rings = set(different_places_df.get("ring", "").astype(str).str.strip().unique())
    moulting_place_rings = set(moulting_place_df.get("ring", "").astype(str).str.strip().unique())

    st.write(f"X: {all_rest_year_rings - (different_places_rings | moulting_place_rings)}")

    # Birds seen anywhere in the rest of the year (including same place)
    seen_rest_of_year = len(all_rest_year_rings)

    seen_moulting_place_during_rest_of_year = len(moulting_place_rings)

    # Birds only seen at moulting place (not seen during rest of year)
    only_seen_during_moulting_period = total_moulting_rings - seen_rest_of_year

    # Birds seen at different places during rest of year
    different_places_count = len(different_places_rings)

    only_seen_at_moulting_place_during_rest_of_year = len(moulting_place_rings - different_places_rings)

    summary = pd.DataFrame(
        {
            "Kategorie": [
                "Gesamt (Mausernde Vögel)",
                "Im Rest des Zeitraums gesehen",
                "Nur während Mauserzeit gesehen",
                "Am Mauserort gesehen (Rest des Zeitraums)",
                "Ausschließlich am Mauserort gesehen (Rest des Zeitraums)",
                "Auch an anderen Orten gesehen (Rest des Zeitraums)",
            ],
            "Anzahl Ringe": [
                total_moulting_rings,
                seen_rest_of_year,
                only_seen_during_moulting_period,
                seen_moulting_place_during_rest_of_year,
                only_seen_at_moulting_place_during_rest_of_year,
                different_places_count,
            ],
            "Prozent": [
                100.0,
                (seen_rest_of_year / total_moulting_rings * 100) if total_moulting_rings > 0 else 0,
                (only_seen_during_moulting_period / total_moulting_rings * 100) if total_moulting_rings > 0 else 0,
                (seen_moulting_place_during_rest_of_year / total_moulting_rings * 100)
                if total_moulting_rings > 0
                else 0,
                (only_seen_at_moulting_place_during_rest_of_year / total_moulting_rings * 100)
                if total_moulting_rings > 0
                else 0,
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
        year_mode = st.radio(
            "Zeitraum", ["Einzelnes Jahr", "Bereich", "Alle Jahre"], horizontal=True, key="moult_year_mode"
        )

    if year_mode == "Einzelnes Jahr":
        with col2:
            year = st.selectbox("Jahr", options=years, index=len(years) - 1, key="moult_year")
        year_range = [year]
    elif year_mode == "Bereich":
        col2a, col2b = st.columns(2)
        with col2a:
            start_year = st.selectbox("Von Jahr", options=years, index=0, key="moult_start_year")
        with col2b:
            end_year = st.selectbox("Bis Jahr", options=years, index=len(years) - 1, key="moult_end_year")
        year_range = list(range(start_year, end_year + 1))
    else:  # Alle Jahre
        year_range = years

    # Species selection
    species_options = unique_nonempty(df, "species")
    if not species_options:
        st.error("Keine Arten in den Daten gefunden.")
        return

    with col2:
        species = st.selectbox("Art", options=species_options, key="moult_species")

    # Place selection - sorted by frequency in the dataset
    place_counts = (
        df.assign(place=df.get("place", "").astype(str).str.strip())
        .loc[lambda d: d["place"] != ""]
        .groupby("place")["place"]
        .count()
        .sort_values(ascending=False)
    )
    place_options = place_counts.index.tolist()

    if not place_options:
        st.error("Keine Orte in den Daten gefunden.")
        return

    place = st.selectbox(
        "Mauserort",
        options=place_options,
        key="moult_place",
        help="Orte sind nach Häufigkeit der Beobachtungen sortiert",
    )

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

        st.info(f"Zeitraum: {start_month_name} bis {end_month_name} ({min(year_range)}-{max(year_range)})")

    elif filter_type == "Status":
        status_options = ["Alle"] + unique_nonempty(df, "status")
        status_filter = st.selectbox("Status", options=status_options, key="moult_status")

        if status_filter != "Alle":
            st.info(f"Status: {status_filter} ({min(year_range)}-{max(year_range)})")

    # Analysis button
    if st.button("Analyse starten", type="primary"):
        with st.spinner("Analysiere Daten..."):
            # Find moulting birds
            moulting_df, moulting_rings = _find_moulting_birds(
                df, year_range, place, species, filter_type, start_month, end_month, status_filter
            )

            if len(moulting_rings) == 0:
                st.warning("Keine Vögel gefunden, die den Kriterien entsprechen.")
                # Clear any existing results
                if "moult_analysis_results" in st.session_state:
                    del st.session_state.moult_analysis_results
                return

            # Analyze rest of year
            all_rest_year_df, different_places_df, moulting_place_df = _analyze_rest_of_year(
                df, list(moulting_rings), year_range, filter_type, place, start_month, end_month
            )

            # Store results in session state
            st.session_state.moult_analysis_results = {
                "moulting_df": moulting_df,
                "all_rest_year_df": all_rest_year_df,
                "different_places_df": different_places_df,
                "moulting_place_df": moulting_place_df,
                "moulting_place": place,
                "num_moulting_rings": len(moulting_rings),
            }

    # Display analysis results if they exist in session state
    if "moult_analysis_results" in st.session_state:
        results = st.session_state.moult_analysis_results
        moulting_df = results["moulting_df"]
        all_rest_year_df = results["all_rest_year_df"]
        different_places_df = results["different_places_df"]
        moulting_place_df = results["moulting_place_df"]
        stored_place = results["moulting_place"]
        num_moulting_rings = results["num_moulting_rings"]

        st.success(f"**{num_moulting_rings} eindeutige Ringe** gefunden, die den Kriterien entsprechen.")

        st.subheader("3. Ergebnisse")

        # Summary table
        st.markdown("**Zusammenfassung:**")
        summary_table = _create_movement_summary_table(
            moulting_df, all_rest_year_df, different_places_df, stored_place, moulting_place_df
        )

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
                place_chart, place_counts_df = _create_place_distribution_chart(different_places_df)

                # Display the interactive chart
                event = st.altair_chart(place_chart, use_container_width=True, on_select="rerun")

                # Handle chart selection - try different possible selection formats
                selected_places = None
                if event.selection:
                    # Try different ways the selection might be structured
                    if "place" in event.selection:
                        selected_places = event.selection["place"]
                    elif len(event.selection) > 0:
                        # Sometimes the selection might be structured differently
                        for key, value in event.selection.items():
                            if isinstance(value, list) and len(value) > 0:
                                # Check if this contains place information
                                if isinstance(value[0], dict) and "place" in value[0]:
                                    selected_places = [item["place"] for item in value]

                if selected_places and len(selected_places) > 0:
                    st.markdown("**Detaillierte Beobachtungen für ausgewählte Orte:**")

                    # Filter the original data for selected places
                    selected_sightings = different_places_df[
                        different_places_df.get("place", "").astype(str).str.strip().isin(selected_places)
                    ]

                    if len(selected_sightings) > 0:
                        # Show summary
                        unique_rings = selected_sightings.get("ring", "").astype(str).str.strip().nunique()
                        total_sightings = len(selected_sightings)
                        st.info(
                            f"**{unique_rings} eindeutige Ringe** in **{total_sightings} Beobachtungen** an den ausgewählten Orten"
                        )

                        # Show detailed table
                        display_cols = ["ring", "date", "place", "area", "status", "melder"]
                        available_cols = [c for c in display_cols if c in selected_sightings.columns]

                        if available_cols:
                            detail_df = selected_sightings[available_cols].rename(columns=mapping)
                            # Use utility function to format dates and add links
                            detail_df = prepare_dataframe_for_display(detail_df, selected_sightings)
                            # Sort by date for better readability
                            if "Datum" in detail_df.columns:
                                detail_df = detail_df.sort_values("Datum")

                            # Configure column display for links
                            link_cfg = {}
                            try:
                                LinkColumn = getattr(st.column_config, "LinkColumn", None)
                                if LinkColumn is not None:
                                    link_cfg["Eintrag"] = LinkColumn(
                                        "Eintrag", help="Öffnen in neuem Tab", width="small", display_text="Öffnen"
                                    )
                            except Exception:
                                pass

                            st.dataframe(
                                detail_df, use_container_width=True, hide_index=True, column_config=link_cfg or None
                            )
                    else:
                        st.warning("Keine Daten für die ausgewählten Orte gefunden.")
                else:
                    st.info(
                        "💡 Klicken Sie auf einen Balken im Diagramm, um die detaillierten Beobachtungen für diesen Ort zu sehen."
                    )
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
                    # Use utility function to format dates and add links
                    detail_df = prepare_dataframe_for_display(detail_df, all_rest_year_df)

                    # Configure column display for links
                    link_cfg = {}
                    try:
                        LinkColumn = getattr(st.column_config, "LinkColumn", None)
                        if LinkColumn is not None:
                            link_cfg["Eintrag"] = LinkColumn(
                                "Eintrag", help="Öffnen in neuem Tab", width="small", display_text="Öffnen"
                            )
                    except Exception:
                        pass

                    st.dataframe(detail_df, use_container_width=True, hide_index=True, column_config=link_cfg or None)
                else:
                    st.info("Keine detaillierten Daten verfügbar.")

            # Show different places data separately
            if len(different_places_df) > 0:
                with st.expander("Beobachtungen an anderen Orten"):
                    display_cols = ["ring", "date", "place", "area", "status", "melder"]
                    available_cols = [c for c in display_cols if c in different_places_df.columns]

                    if available_cols:
                        detail_df = different_places_df[available_cols].rename(columns=mapping)
                        # Use utility function to format dates and add links
                        detail_df = prepare_dataframe_for_display(detail_df, different_places_df)

                        # Configure column display for links
                        link_cfg = {}
                        try:
                            LinkColumn = getattr(st.column_config, "LinkColumn", None)
                            if LinkColumn is not None:
                                link_cfg["Eintrag"] = LinkColumn(
                                    "Eintrag", help="Öffnen in neuem Tab", width="small", display_text="Öffnen"
                                )
                        except Exception:
                            pass

                        st.dataframe(
                            detail_df, use_container_width=True, hide_index=True, column_config=link_cfg or None
                        )
        else:
            st.info("Keine Beobachtungen der mausernden Vögel außerhalb des definierten Zeitraums/Status gefunden.")
