from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from data import load_data
from util.col_mapping import mapping
from util.storage import STORAGE_DIR, load_views, load_view
from util.dates import format_date_columns_for_display


DATASETS_DIR = STORAGE_DIR / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip()
    return safe.replace(" ", "_")


def _dataset_paths(name: str) -> tuple[Path, Path]:
    base = DATASETS_DIR / _safe_filename(name)
    return base.with_suffix(".json"), base.with_suffix(".csv")


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


def _list_datasets() -> list[str]:
    return sorted([p.stem for p in DATASETS_DIR.glob("*.json")])


def _load_dataset(name: str) -> tuple[dict[str, Any], pd.DataFrame] | tuple[None, None]:
    meta_path, data_path = _dataset_paths(name)
    if not meta_path.exists() or not data_path.exists():
        return None, None
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    # Backward/compat: if base_view was stringified, try to parse
    if isinstance(meta.get("base_view"), str):
        try:
            meta["base_view"] = json.loads(meta["base_view"])  # type: ignore[arg-type]
        except Exception:
            meta["base_view"] = {}
    df = pd.read_csv(data_path, sep=";", dtype=str, keep_default_na=True, na_values=["", "NA", "NaN"])
    return meta, df


def _save_dataset(
    name: str, description: str, base_view: dict[str, Any], df_full: pd.DataFrame, included_mask: pd.Series
) -> None:
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    meta = {
        "name": name,
        "description": description,
        "created_at": created_at,
        "base_view": {
            "name": base_view.get("name"),
            "columns": base_view.get("columns", []),
            "filters": base_view.get("filters", []),
        },
        "row_count": int(len(df_full)),
        "included_count": int(included_mask.sum()),
    }

    meta_path, data_path = _dataset_paths(name)
    # Save metadata as JSON
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Save full data with include flag; keep internal column names
    to_save = df_full.copy()
    to_save.insert(0, "included", included_mask.astype(bool).astype(int))
    to_save.to_csv(data_path, sep=";", index=False)


def render_data_sets() -> None:
    st.header("Datensätze")

    df_all = load_data()

    # Existing datasets
    st.subheader("Gespeicherte Datensätze")
    ds_names = _list_datasets()
    if not ds_names:
        st.caption("Keine Datensätze gespeichert.")
    else:
        cols = st.columns([3, 1])
        with cols[0]:
            chosen_ds = st.selectbox(
                "Datensatz laden", options=["— Bitte wählen —"] + ds_names, index=0, key="ds_select"
            )
        with cols[1]:
            if st.button("Laden") and chosen_ds and chosen_ds != "— Bitte wählen —":
                meta, df_ds = _load_dataset(chosen_ds)
                if meta is not None and df_ds is not None:
                    st.session_state.ds_loaded_name = chosen_ds
                    st.session_state.ds_loaded_meta = meta
                    st.session_state.ds_loaded_df = df_ds
                    st.rerun()

    # Full-width editor for a loaded dataset
    if st.session_state.get("ds_loaded_name"):
        meta = st.session_state.get("ds_loaded_meta", {})
        df_ds = st.session_state.get("ds_loaded_df", pd.DataFrame())
        st.markdown("---")
        st.subheader(f"Datensatz: {meta.get('name', st.session_state.ds_loaded_name)}")
        st.caption(meta.get("description", ""))
        st.caption(f"Erstellt: {meta.get('created_at', '')}")

        show_hidden = st.checkbox("Auch versteckte Zeilen anzeigen", value=False, key="ds_show_hidden")

        df_work = df_ds.copy().reset_index(drop=True)
        included_series = (
            pd.Series(df_work.get("included", 1))
            .astype(str)
            .map(lambda x: x in {"1", "True", "true", "TRUE"})
            .fillna(True)
        )

        base_view_cols = meta.get("base_view", {}).get("columns", [])
        view_cols_existing = [c for c in base_view_cols if c in df_work.columns]
        if len(view_cols_existing) == 0:
            view_cols_existing = [c for c in df_work.columns if c in mapping]

        # Only included rows by default
        subset_mask = included_series if not show_hidden else pd.Series([True] * len(df_work))
        subset_idx = subset_mask[subset_mask].index
        disp = df_work.loc[subset_idx, view_cols_existing].rename(columns=mapping)
        disp = format_date_columns_for_display(disp)
        disp.insert(0, "Aufnehmen", included_series.loc[subset_idx].tolist())

        edited = st.data_editor(
            disp,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="loaded_dataset_editor",
        )
        # Push edited flags back to dataset df
        updated_flags = pd.Series(edited["Aufnehmen"].astype(bool).tolist(), index=subset_idx)
        df_work.loc[subset_idx, "included"] = updated_flags.astype(int).values

        col_a, col_b, _ = st.columns([2, 2, 6])
        with col_a:
            if st.button("Änderungen speichern"):
                st.session_state.ds_loaded_df = df_work
                base_view = meta.get("base_view", {})
                # Persist with all original columns preserved
                _save_dataset(
                    meta.get("name", st.session_state.ds_loaded_name),
                    meta.get("description", ""),
                    base_view,
                    df_work.drop(columns=[c for c in df_work.columns if c not in df_all.columns], errors="ignore"),
                    pd.Series(df_work["included"]).astype(bool),
                )
                st.success("Datensatz aktualisiert.")
                st.rerun()
        with col_b:
            if st.button("Schließen"):
                st.session_state.pop("ds_loaded_name", None)
                st.session_state.pop("ds_loaded_meta", None)
                st.session_state.pop("ds_loaded_df", None)
                st.rerun()

    st.markdown("---")
    st.subheader("Neuen Datensatz erstellen")

    views = load_views()
    view_names = [v.get("name", "") for v in views]
    if not view_names:
        st.info("Bitte zuerst unter 'Daten Ansichten' eine Ansicht speichern.")
        return

    base_view_name = st.selectbox("Ansicht auswählen", options=view_names, index=0, key="dataset_base_view")
    base_view = load_view(base_view_name) or {}

    # Apply view to data
    filtered_df = _apply_filters(df_all, base_view.get("filters", []))
    view_columns = [c for c in base_view.get("columns", []) if c in filtered_df.columns]
    if len(view_columns) == 0:
        view_columns = [c for c in filtered_df.columns if c in mapping]

    # Build editable grid with checkbox for inclusion
    st.caption("Zeilen auswählen (ein-/ausschließen)")
    working = filtered_df.copy().reset_index(drop=True)
    # Reset inclusion state when view changes or length differs
    prev_view = st.session_state.get("dataset_prev_view_name")
    if prev_view != base_view_name:
        st.session_state.included_state = [True] * len(working)
        st.session_state.dataset_prev_view_name = base_view_name
    elif "included_state" not in st.session_state or len(st.session_state.included_state) != len(working):
        st.session_state.included_state = [True] * len(working)
    # Use data_editor with a boolean column
    display_df = working[view_columns].rename(columns=mapping)
    display_df = format_date_columns_for_display(display_df)
    display_df.insert(0, "Aufnehmen", st.session_state.included_state)
    edited = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="dataset_editor",
    )
    # Persist updated included mask in session state
    st.session_state.included_state = edited["Aufnehmen"].astype(bool).tolist()
    included_mask = pd.Series(st.session_state.included_state)

    left, mid, right = st.columns([2, 2, 6])
    with left:
        if st.button("Alle auswählen"):
            st.session_state.included_state = [True] * len(working)
            st.rerun()
    with mid:
        if st.button("Alle abwählen"):
            st.session_state.included_state = [False] * len(working)
            st.rerun()

    st.caption(f"Ausgewählt: {int(included_mask.sum())} von {len(working)} Zeilen")

    st.markdown("#### Metadaten")
    name = st.text_input("Name des Datensatzes")
    description = st.text_area("Beschreibung", height=60)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Vorschau anzeigen"):
            preview_df = working[included_mask.values]
            preview_df = preview_df[view_columns].rename(columns=mapping)
            preview_df = format_date_columns_for_display(preview_df)
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
    with col_b:
        if st.button("Datensatz speichern"):
            if not name:
                st.error("Bitte einen Namen angeben.")
            else:
                _save_dataset(name, description, base_view, working, included_mask)
                st.success("Datensatz gespeichert.")
                # reset state for next dataset
                st.session_state.included_state = [True] * len(working)
                st.rerun()
