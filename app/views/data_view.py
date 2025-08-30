from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from util.storage import load_views, save_view, delete_view, load_view
from util.col_mapping import reverse_mapping, mapping
from util.dates import prepare_dataframe_for_display
from data import load_data, unique_nonempty


def _internal_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c in mapping]


def _to_display_columns(columns: list[str]) -> list[str]:
    return [mapping.get(c, c) for c in columns]


def _to_internal_columns(display_columns: list[str]) -> list[str]:
    return [reverse_mapping.get(c, c) for c in display_columns]


def _apply_filters(df: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    result = df.copy()
    for f in filters or []:
        ftype = f.get("type")
        col = f.get("column")
        if col not in result.columns:
            continue
        if ftype == "equals":
            value = f.get("value", "")
            result = result[result[col] == value]
        elif ftype == "multi":
            values = f.get("values", [])
            if len(values) > 0:
                result = result[result[col].isin(values)]
        elif ftype == "contains":
            value = str(f.get("value", ""))
            if value:
                result = result[result[col].astype(str).str.contains(value, case=False, na=False)]
        elif ftype == "date_range":
            start = pd.to_datetime(f.get("start")) if f.get("start") else None
            end = pd.to_datetime(f.get("end")) if f.get("end") else None
            series = pd.to_datetime(result[col], errors="coerce")
            if start is not None:
                result = result[series >= start]
            if end is not None:
                result = result[series <= end]
        elif ftype == "number_range":
            min_v = f.get("min")
            max_v = f.get("max")
            series = pd.to_numeric(result[col], errors="coerce")
            if min_v is not None and min_v != "":
                try:
                    result = result[series >= float(min_v)]
                except Exception:
                    pass
            if max_v is not None and max_v != "":
                try:
                    result = result[series <= float(max_v)]
                except Exception:
                    pass
    return result


def _display_dataframe(df: pd.DataFrame, selected_columns: list[str] | None = None) -> None:
    cols = selected_columns or _internal_columns(df)
    df_show = df[cols].rename(columns=mapping)
    df_show = prepare_dataframe_for_display(df_show, source_df=df)

    link_cfg: dict[str, Any] = {}
    try:
        # Prefer LinkColumn if available
        LinkColumn = getattr(st.column_config, "LinkColumn", None)
        if LinkColumn is not None:
            link_cfg = {
                "Eintrag": LinkColumn("Eintrag", help="Öffnen in neuem Tab", width="small", display_text="Öffnen"),
            }
        else:
            URLColumn = getattr(st.column_config, "URLColumn", None)
            if URLColumn is not None:
                link_cfg = {
                    "Eintrag": URLColumn("Eintrag", help="Öffnen in neuem Tab", width="small"),
                }
    except Exception:
        link_cfg = {}

    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        column_config=link_cfg or None,
    )


def _columns_selector_ui(df: pd.DataFrame, col_count: int = 4) -> list[str]:
    available_internal = _internal_columns(df)
    # Pair internal with display for stable sorting/search
    pairs = [(col, mapping.get(col, col)) for col in available_internal]
    pairs.sort(key=lambda x: x[1])

    with st.expander("Spalten auswählen", expanded=True):
        top_cols = st.columns([3, 1])
        with top_cols[0]:
            query = st.text_input("Spalten filtern", placeholder="z. B. Datum, Ort", key="col_search_query")
        with top_cols[1]:
            select_all = st.checkbox("Alle auswählen", value=True, key="col_select_all")

        if query:
            q = query.strip().lower()
            pairs_to_render = [p for p in pairs if q in p[1].lower()]
        else:
            pairs_to_render = pairs

        grid = st.columns(col_count)
        for idx, (internal, label) in enumerate(pairs_to_render):
            key = f"colchk_{internal}"
            default_checked = st.session_state.get(key, select_all)
            with grid[idx % col_count]:
                st.checkbox(label, value=default_checked, key=key)

        # Collect selection
        selected_internal: list[str] = []
        for internal, _label in pairs:
            if st.session_state.get(f"colchk_{internal}", False):
                selected_internal.append(internal)

        # Compact selection summary
        st.caption(f"Ausgewählt: {len(selected_internal)}/{len(pairs)} Spalten")
        return selected_internal


def _filter_builder_ui(df: pd.DataFrame) -> list[dict[str, Any]]:
    if "new_view_filters" not in st.session_state:
        st.session_state.new_view_filters = []

    st.write("Aktive Filter:")
    if len(st.session_state.new_view_filters) == 0:
        st.caption("Keine Filter hinzugefügt.")
    else:
        for idx, f in enumerate(st.session_state.new_view_filters):
            col_label = mapping.get(f.get("column", ""), f.get("column", ""))
            type_label = {
                "equals": "Gleich",
                "multi": "Mehrfach",
                "contains": "Enthält",
                "date_range": "Datum-Bereich",
                "number_range": "Zahlen-Bereich",
            }.get(f.get("type", ""), f.get("type", ""))
            desc = type_label
            if f.get("type") == "multi":
                desc = f"{desc}: {', '.join(f.get('values', []))}"
            elif f.get("type") == "equals":
                desc = f"{desc}: {f.get('value', '')}"
            elif f.get("type") == "contains":
                desc = f"{desc}: {f.get('value', '')}"
            elif f.get("type") == "date_range":
                desc = f"{desc}: {f.get('start', '')} – {f.get('end', '')}"
            elif f.get("type") == "number_range":
                desc = f"{desc}: {f.get('min', '')} – {f.get('max', '')}"
            cols = st.columns([3, 4, 1])
            with cols[0]:
                st.write(col_label)
            with cols[1]:
                st.write(desc)
            with cols[2]:
                if st.button("Entfernen", key=f"remove_filter_{idx}"):
                    st.session_state.new_view_filters.pop(idx)
                    st.rerun()
        if st.button("Alle Filter entfernen", key="clear_all_filters"):
            st.session_state.new_view_filters = []
            st.rerun()

    with st.expander("Filter hinzufügen", expanded=False):
        # Column selection (display labels)
        available_columns = _internal_columns(df)
        column_display = st.selectbox(
            "Spalte",
            options=_to_display_columns(available_columns),
            index=0,
            key="new_filter_column_display",
        )
        column_internal = reverse_mapping[column_display]

        # Infer control type
        is_date = column_internal in {"date", "ringing_date"}
        is_numeric = column_internal in {
            "lat",
            "lon",
            "ringing_lat",
            "ringing_lon",
            "breed_size",
            "family_size",
            "small_group_size",
            "large_group_size",
        }
        is_boolean = column_internal in {"melded", "is_exact_location"}
        is_categorical = column_internal in {
            "species",
            "place",
            "area",
            "sex",
            "age",
            "status",
            "habitat",
            "field_fruit",
            "melder",
            "ring",
            "partner",
            "ringing_ring_scheme",
            "ringing_species",
            "ringing_place",
            "ringing_ringer",
            "ringing_sex",
            "ringing_age",
            "ringing_status",
        }

        if is_date:
            col_a, col_b = st.columns(2)
            with col_a:
                start = st.date_input("Von", value=None, key="new_filter_date_start")
            with col_b:
                end = st.date_input("Bis", value=None, key="new_filter_date_end")
            if st.button("Filter hinzufügen", key="add_filter_date"):
                st.session_state.new_view_filters.append(
                    {
                        "type": "date_range",
                        "column": column_internal,
                        "start": str(start) if start else None,
                        "end": str(end) if end else None,
                    }
                )
                st.rerun()
        elif is_numeric:
            mode = st.radio("Filtertyp", options=["Bereich", "Gleich"], horizontal=True, key="num_mode")
            if mode == "Bereich":
                col_a, col_b = st.columns(2)
                with col_a:
                    min_v = st.text_input("Min", key="new_filter_min")
                with col_b:
                    max_v = st.text_input("Max", key="new_filter_max")
                if st.button("Filter hinzufügen", key="add_filter_number"):
                    st.session_state.new_view_filters.append(
                        {
                            "type": "number_range",
                            "column": column_internal,
                            "min": min_v,
                            "max": max_v,
                        }
                    )
                    st.rerun()
            else:
                val = st.text_input("Wert", key="new_filter_number_equals")
                if st.button("Filter hinzufügen", key="add_filter_number_equals"):
                    st.session_state.new_view_filters.append(
                        {"type": "equals", "column": column_internal, "value": val}
                    )
                    st.rerun()
        elif is_boolean:
            val = st.selectbox("Wert", options=["Ja", "Nein"], index=0, key="bool_equals_val")
            if st.button("Filter hinzufügen", key="add_filter_bool_equals"):
                st.session_state.new_view_filters.append(
                    {"type": "equals", "column": column_internal, "value": (val == "Ja")}
                )
                st.rerun()
        elif is_categorical:
            mode = st.radio("Filtertyp", options=["Gleich", "Mehrfach", "Enthält"], horizontal=True, key="cat_mode")
            values = unique_nonempty(df, column_internal)
            if mode == "Gleich":
                value = st.selectbox("Wert", options=values, key="new_filter_equals_val")
                if st.button("Filter hinzufügen", key="add_filter_equals"):
                    st.session_state.new_view_filters.append(
                        {"type": "equals", "column": column_internal, "value": value}
                    )
                    st.rerun()
            elif mode == "Mehrfach":
                chosen = st.multiselect("Werte", options=values, key="new_filter_multi")
                if st.button("Filter hinzufügen", key="add_filter_multi"):
                    st.session_state.new_view_filters.append(
                        {"type": "multi", "column": column_internal, "values": chosen}
                    )
                    st.rerun()
            else:
                text = st.text_input("Enthält", key="new_filter_contains")
                if st.button("Filter hinzufügen", key="add_filter_contains"):
                    st.session_state.new_view_filters.append(
                        {"type": "contains", "column": column_internal, "value": text}
                    )
                    st.rerun()
        else:
            mode = st.radio("Filtertyp", options=["Gleich", "Enthält"], horizontal=True, key="text_mode")
            if mode == "Gleich":
                val = st.text_input("Wert", key="new_filter_text_equals")
                if st.button("Filter hinzufügen", key="add_filter_text_equals"):
                    st.session_state.new_view_filters.append(
                        {"type": "equals", "column": column_internal, "value": val}
                    )
                    st.rerun()
            else:
                text = st.text_input("Enthält", key="new_filter_contains_generic")
                if st.button("Filter hinzufügen", key="add_filter_contains_generic"):
                    st.session_state.new_view_filters.append(
                        {"type": "contains", "column": column_internal, "value": text}
                    )
                    st.rerun()

    return st.session_state.new_view_filters


def _views_management_ui(df: pd.DataFrame) -> None:
    st.subheader("Gespeicherte Ansichten")
    views = load_views()
    if not views:
        st.caption("Keine gespeicherten Ansichten.")
    for v in views:
        cols = st.columns([4, 3, 2])
        with cols[0]:
            st.write(f"{v.get('name', '')}")
            st.caption(v.get("description", ""))
        with cols[1]:
            st.caption("Spalten")
            st.write(", ".join(_to_display_columns(v.get("columns", []))))
        with cols[2]:
            a, b = st.columns(2)
            with a:
                if st.button("Anwenden", key=f"apply_{v.get('name', '')}"):
                    st.session_state.active_view = v.get("name")
                    st.rerun()
            with b:
                if st.button("Löschen", key=f"delete_{v.get('name', '')}"):
                    delete_view(v.get("name", ""))
                    st.experimental_rerun()

    # Apply active view preview
    active_name = st.session_state.get("active_view")
    if active_name:
        v = load_view(active_name)
        if v:
            st.markdown("---")
            st.subheader(f"Ansicht: {v.get('name')}")
            filtered = _apply_filters(df, v.get("filters", []))
            _display_dataframe(filtered, v.get("columns"))


def render_data_view() -> None:
    st.header("Daten-Tabelle")
    df = load_data()

    # KPIs
    n_sightings = len(df)
    n_species = len(unique_nonempty(df, "species"))
    n_places = len(unique_nonempty(df, "place"))
    n_rings = len(unique_nonempty(df, "ring"))
    try:
        n_melded = int(pd.Series(df["melded"]).fillna(False).astype(bool).sum())
    except Exception:
        n_melded = 0
    n_melder = len(unique_nonempty(df, "melder"))

    st.subheader("Überblick")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Anzahl Beobachtungen", n_sightings)
        st.metric("Anzahl Orte", n_places)
    with col2:
        st.metric("Anzahl Ringe", n_rings)
        st.metric("Anzahl Melder", n_melder)
    with col3:
        st.metric("Anzahl Arten", n_species)
        st.metric("Anzahl Gemeldet", n_melded)

    st.markdown("---")
    _views_management_ui(df)

    st.markdown("---")
    st.subheader("Neue Daten-Ansicht erstellen")

    # Initialize defaults for new view state
    st.session_state.setdefault("new_view_name", "")
    st.session_state.setdefault("new_view_description", "")
    st.session_state.setdefault("new_view_filters", [])

    # Load preset/template
    tmpl_cols = st.columns([3, 1])
    with tmpl_cols[0]:
        tmpl_options = ["— Keine Vorlage —"] + [v.get("name", "") for v in load_views()]
        selected_tmpl = st.selectbox("Vorlage laden", options=tmpl_options, index=0, key="preset_select")
    with tmpl_cols[1]:
        if st.button("Vorlage anwenden") and selected_tmpl != "— Keine Vorlage —":
            tmpl = load_view(selected_tmpl)
            if tmpl:
                st.session_state.new_view_name = f"{tmpl.get('name', '')} Kopie"
                st.session_state.new_view_description = tmpl.get("description", "")
                st.session_state.new_view_filters = tmpl.get("filters", [])
                tmpl_cols_internal = tmpl.get("columns", [])
                for c in _internal_columns(df):
                    st.session_state[f"colchk_{c}"] = c in tmpl_cols_internal
                st.session_state["col_select_all"] = False
                st.rerun()

    # Basic inputs
    name = st.text_input("Name der Ansicht", key="new_view_name")
    description = st.text_area("Beschreibung", height=60, key="new_view_description")

    selected_internal_cols = _columns_selector_ui(df)
    st.session_state.selected_internal_cols = selected_internal_cols

    st.markdown("#### Filter")
    _filter_builder_ui(df)

    col_a, col_b, _ = st.columns([2, 2, 4])
    with col_a:
        preview = st.button("Vorschau anwenden")
    with col_b:
        save = st.button("Ansicht speichern")

    current_filters = st.session_state.new_view_filters

    if preview:
        filtered = _apply_filters(df, current_filters)
        _display_dataframe(filtered, st.session_state.selected_internal_cols)

    if save:
        if not name:
            st.error("Bitte einen Namen für die Ansicht angeben.")
        elif len(selected_internal_cols) == 0:
            st.error("Bitte mindestens eine Spalte auswählen.")
        else:
            save_view(
                {
                    "name": name,
                    "description": description,
                    "columns": selected_internal_cols,
                    "filters": current_filters,
                }
            )
            st.success("Ansicht gespeichert.")
            st.session_state.new_view_filters = []
            st.rerun()
