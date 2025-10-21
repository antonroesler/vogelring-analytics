from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from data import load_data, unique_nonempty
from util.col_mapping import mapping, reverse_mapping
from util.dates import add_vogelring_link_column
from util.datasets import (
    list_dataset_names,
    load_dataset_config,
    save_dataset_config,
    delete_dataset,
    duplicate_dataset,
)


DEFAULT_COLUMNS: list[str] = ["ring", "reading", "species", "place", "date", "status"]


def _internal_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c in mapping]


def _to_display_columns(columns: list[str]) -> list[str]:
    return [mapping.get(c, c) for c in columns]


def _apply_filters(df: pd.DataFrame, filters: list[dict[str, Any]] | None) -> pd.DataFrame:
    if not filters:
        return df
    result = df.copy()
    for f in filters:
        ftype = f.get("type")
        col = f.get("column")
        if col not in result.columns:
            continue
        if ftype == "equals":
            value = f.get("value", "")
            if str(value).isnumeric():
                result = result[result[col] == float(value)]
            else:
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


def _filter_builder_ui(df: pd.DataFrame) -> list[dict[str, Any]]:
    st.session_state.setdefault("ds_filters", [])

    st.write("Aktive Filter:")
    if len(st.session_state.ds_filters) == 0:
        st.caption("Keine Filter hinzugefügt.")
    else:
        for idx, f in enumerate(st.session_state.ds_filters):
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
                if st.button("Entfernen", key=f"remove_ds_filter_{idx}"):
                    st.session_state.ds_filters.pop(idx)
                    st.rerun()
        if st.button("Alle Filter entfernen", key="clear_all_ds_filters"):
            st.session_state.ds_filters = []
            st.rerun()

    with st.expander("Filter hinzufügen", expanded=False):
        available_columns = _internal_columns(df)
        column_display = st.selectbox(
            "Spalte",
            options=_to_display_columns(available_columns),
            index=0,
            key="ds_new_filter_column_display",
        )
        column_internal = reverse_mapping[column_display]

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
            "year",
            "month",
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
                start = st.date_input("Von", value=None, key="ds_new_filter_date_start")
            with col_b:
                end = st.date_input("Bis", value=None, key="ds_new_filter_date_end")
            if st.button("Filter hinzufügen", key="ds_add_filter_date"):
                st.session_state.ds_filters.append(
                    {
                        "type": "date_range",
                        "column": column_internal,
                        "start": str(start) if start else None,
                        "end": str(end) if end else None,
                    }
                )
                st.rerun()
        elif is_numeric:
            mode = st.radio("Filtertyp", options=["Bereich", "Gleich"], horizontal=True, key="ds_num_mode")
            if mode == "Bereich":
                col_a, col_b = st.columns(2)
                with col_a:
                    min_v = st.text_input("Min", key="ds_new_filter_min")
                with col_b:
                    max_v = st.text_input("Max", key="ds_new_filter_max")
                if st.button("Filter hinzufügen", key="ds_add_filter_number"):
                    st.session_state.ds_filters.append(
                        {
                            "type": "number_range",
                            "column": column_internal,
                            "min": min_v,
                            "max": max_v,
                        }
                    )
                    st.rerun()
            else:
                val = st.text_input("Wert", key="ds_new_filter_number_equals")
                if st.button("Filter hinzufügen", key="ds_add_filter_number_equals"):
                    st.session_state.ds_filters.append({"type": "equals", "column": column_internal, "value": val})
                    st.rerun()
        elif is_boolean:
            val = st.selectbox("Wert", options=["Ja", "Nein"], index=0, key="ds_bool_equals_val")
            if st.button("Filter hinzufügen", key="ds_add_filter_bool_equals"):
                st.session_state.ds_filters.append(
                    {"type": "equals", "column": column_internal, "value": (val == "Ja")}
                )
                st.rerun()
        elif is_categorical:
            mode = st.radio("Filtertyp", options=["Gleich", "Mehrfach", "Enthält"], horizontal=True, key="ds_cat_mode")
            values = unique_nonempty(df, column_internal)
            if mode == "Gleich":
                value = st.selectbox("Wert", options=values, key="ds_new_filter_equals_val")
                if st.button("Filter hinzufügen", key="ds_add_filter_equals"):
                    st.session_state.ds_filters.append({"type": "equals", "column": column_internal, "value": value})
                    st.rerun()
            elif mode == "Mehrfach":
                chosen = st.multiselect("Werte", options=values, key="ds_new_filter_multi")
                if st.button("Filter hinzufügen", key="ds_add_filter_multi"):
                    st.session_state.ds_filters.append({"type": "multi", "column": column_internal, "values": chosen})
                    st.rerun()
            else:
                text = st.text_input("Enthält", key="ds_new_filter_contains")
                if st.button("Filter hinzufügen", key="ds_add_filter_contains"):
                    st.session_state.ds_filters.append({"type": "contains", "column": column_internal, "value": text})
                    st.rerun()
        else:
            mode = st.radio("Filtertyp", options=["Gleich", "Enthält"], horizontal=True, key="ds_text_mode")
            if mode == "Gleich":
                val = st.text_input("Wert", key="ds_new_filter_text_equals")
                if st.button("Filter hinzufügen", key="ds_add_filter_text_equals"):
                    st.session_state.ds_filters.append({"type": "equals", "column": column_internal, "value": val})
                    st.rerun()
            else:
                text = st.text_input("Enthält", key="ds_new_filter_contains_generic")
                if st.button("Filter hinzufügen", key="ds_add_filter_contains_generic"):
                    st.session_state.ds_filters.append({"type": "contains", "column": column_internal, "value": text})
                    st.rerun()

    return st.session_state.ds_filters


def _columns_selector_ui(df: pd.DataFrame, col_count: int = 4) -> list[str]:
    available_internal = _internal_columns(df)
    pairs = [(col, mapping.get(col, col)) for col in available_internal]
    pairs.sort(key=lambda x: x[1])

    # Initialize ds_columns if not set
    if "ds_columns" not in st.session_state:
        st.session_state.ds_columns = DEFAULT_COLUMNS.copy()

    with st.expander("Spalten auswählen", expanded=True):
        top_cols = st.columns([3, 1])
        with top_cols[0]:
            query = st.text_input("Spalten filtern", placeholder="z. B. Datum, Ort", key="ds_col_search_query")
        with top_cols[1]:
            if st.checkbox("Alle auswählen", key="ds_col_select_all"):
                if st.session_state.ds_col_select_all:
                    st.session_state.ds_columns = available_internal.copy()
                else:
                    st.session_state.ds_columns = []

        pairs_to_render = [p for p in pairs if (query or "").strip().lower() in p[1].lower()] if query else pairs
        grid = st.columns(col_count)

        current_selection = st.session_state.ds_columns

        for idx, (internal, label) in enumerate(pairs_to_render):
            key = f"ds_colchk_{internal}"
            with grid[idx % col_count]:
                # Checkbox value is based on current ds_columns list
                is_checked = st.checkbox(label, value=(internal in current_selection), key=key)

                # Update ds_columns based on checkbox state
                if is_checked and internal not in st.session_state.ds_columns:
                    st.session_state.ds_columns.append(internal)
                elif not is_checked and internal in st.session_state.ds_columns:
                    st.session_state.ds_columns.remove(internal)

        st.caption(f"Ausgewählt: {len(st.session_state.ds_columns)}/{len(pairs)} Spalten")
        return st.session_state.ds_columns


def _ensure_builder_state() -> None:
    st.session_state.setdefault("ds_name", "")
    st.session_state.setdefault("ds_description", "")
    st.session_state.setdefault("ds_filters", [])
    st.session_state.setdefault("ds_columns", [])
    st.session_state.setdefault("ds_excluded_ids", set())


def _load_into_builder(name: str) -> None:
    cfg = load_dataset_config(name) or {}
    st.session_state.ds_name = cfg.get("name", name)
    st.session_state.ds_description = cfg.get("description", "")
    st.session_state.ds_filters = cfg.get("filters", [])
    st.session_state.ds_columns = cfg.get("columns", [])
    st.session_state.ds_excluded_ids = set(str(x) for x in cfg.get("excluded_ids", []))


def render_data_sets() -> None:
    st.header("Datensätze")

    df_all = load_data()
    _ensure_builder_state()

    with st.sidebar:
        st.subheader("Datensatz verwalten")
        names = list_dataset_names()
        selected = st.selectbox("Laden", options=["— Neu —"] + names, index=0, key="ds_select_existing")
        if selected != "— Neu —":
            if st.button("Auswählen", key="ds_load_btn"):
                _load_into_builder(selected)
                st.session_state.ds_selected_existing = selected
                st.rerun()
            if st.button("Löschen", key="ds_delete_btn"):
                delete_dataset(selected)
                st.success("Datensatz gelöscht.")
                st.rerun()
        else:
            st.session_state.pop("ds_selected_existing", None)
            # Reset to default columns when creating new dataset
            st.session_state.ds_columns = DEFAULT_COLUMNS.copy()

        st.markdown("---")
        st.caption("Kopie erstellen")
        new_name = st.text_input("Kopiername", key="ds_duplicate_name")
        if st.button("Als Kopie speichern", key="ds_duplicate_btn"):
            if not new_name:
                st.error("Bitte einen Namen für die Kopie angeben.")
            else:
                source_name = st.session_state.get("ds_selected_existing", st.session_state.ds_name)
                if not source_name:
                    st.error("Kein Quell-Datensatz ausgewählt.")
                else:
                    duplicate_dataset(source_name, new_name, new_description=st.session_state.ds_description)
                    st.success("Kopie gespeichert.")
                    st.rerun()

    st.subheader("1) Metadaten")
    st.session_state.ds_name = st.text_input("Name", value=st.session_state.ds_name, key="ds_name_input")
    st.session_state.ds_description = st.text_area(
        "Beschreibung", value=st.session_state.ds_description, height=60, key="ds_desc_input"
    )

    st.subheader("2) Spalten")
    selected_columns = _columns_selector_ui(df_all)
    st.session_state.ds_columns = selected_columns

    st.subheader("3) Filter")
    filters = _filter_builder_ui(df_all)

    working = _apply_filters(df_all, filters).reset_index(drop=True)
    id_field = "id"
    if id_field not in working.columns:
        st.warning("Spalte 'id' fehlt. Zeilenauswahl wird deaktiviert.")
    ids_series = working.get(id_field, pd.Series([""] * len(working)))
    excluded_ids: set[str] = set(st.session_state.ds_excluded_ids)
    included_flags = [str(i) not in excluded_ids for i in ids_series]

    st.subheader("4) Zeilen auswählen")
    view_columns = [c for c in (st.session_state.ds_columns or _internal_columns(working)) if c in working.columns]
    disp = working[view_columns].rename(columns=mapping)
    # Keep datetime dtype for proper sorting; only add link column
    disp = add_vogelring_link_column(disp, working)
    disp.insert(0, "Aufnehmen", included_flags)

    link_cfg: dict[str, Any] = {}
    try:
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

    # Add datetime column config for display formatting while keeping dtype for sorting
    try:
        DatetimeColumn = getattr(st.column_config, "DatetimeColumn", None)
        if DatetimeColumn is not None:
            date_cfg: dict[str, Any] = {}
            if mapping.get("date") in disp.columns:
                date_cfg[mapping["date"]] = DatetimeColumn(mapping["date"], format="DD.MM.YYYY")
            if mapping.get("ringing_date") in disp.columns:
                date_cfg[mapping["ringing_date"]] = DatetimeColumn(mapping["ringing_date"], format="DD.MM.YYYY")
            link_cfg = {**link_cfg, **date_cfg}
    except Exception:
        pass

    edited = st.data_editor(
        disp,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="ds_editor_current",
        column_config=link_cfg or None,
    )

    if id_field in working.columns:
        updated_flags = edited["Aufnehmen"].astype(bool).tolist()
        new_excluded: set[str] = set()
        for flag, row_id in zip(updated_flags, ids_series.tolist()):
            if not flag:
                new_excluded.add(str(row_id))
        st.session_state.ds_excluded_ids = new_excluded

    st.caption(f"Ausgewählt: {int(edited['Aufnehmen'].astype(bool).sum())} von {len(working)} Zeilen")

    col_a, col_b, _ = st.columns([2, 2, 6])
    with col_a:
        if st.button("Alle auswählen"):
            st.session_state.ds_excluded_ids = set()
            st.rerun()
    with col_b:
        if st.button("Alle abwählen") and id_field in working.columns:
            st.session_state.ds_excluded_ids = set(str(x) for x in ids_series.tolist())
            st.rerun()

    st.subheader("Speichern")

    # Button layout - side by side with proper spacing
    col1, col2 = st.columns(2)
    with col1:
        show_preview = st.button("Vorschau anzeigen", use_container_width=True)
    with col2:
        save_dataset = st.button("Datensatz speichern", type="primary", use_container_width=True)

    # Preview display - uses full width when shown
    if show_preview:
        st.subheader("Vorschau")
        prev_mask = edited["Aufnehmen"].astype(bool).values
        prev_df = working.loc[prev_mask, view_columns].rename(columns=mapping)
        prev_df = add_vogelring_link_column(prev_df, working.loc[prev_mask])
        # Use same column config to format date columns
        st.dataframe(prev_df, use_container_width=True, hide_index=True, column_config=link_cfg or None)

    # Save functionality
    if save_dataset:
        if not st.session_state.ds_name:
            st.error("Bitte einen Namen angeben.")
        else:
            cfg = {
                "name": st.session_state.ds_name,
                "description": st.session_state.ds_description,
                "columns": st.session_state.ds_columns,
                "filters": st.session_state.ds_filters,
                "excluded_ids": list(st.session_state.ds_excluded_ids),
                "id_field": "id",
            }
            save_dataset_config(cfg)
            st.success("Datensatz gespeichert.")
            st.session_state.ds_selected_existing = st.session_state.ds_name
            st.rerun()
