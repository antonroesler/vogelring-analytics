from __future__ import annotations

from pathlib import Path
from typing import Any

import json
import pandas as pd
import streamlit as st

from .storage import STORAGE_DIR
from data import load_data


DATASETS_DIR = STORAGE_DIR / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip().replace(" ", "_")


def _dataset_config_path(name: str) -> Path:
    return (DATASETS_DIR / _safe_name(name)).with_suffix(".json")


def list_dataset_names() -> list[str]:
    return sorted([p.stem for p in DATASETS_DIR.glob("*.json")])


def load_dataset_config(name: str) -> dict[str, Any] | None:
    path = _dataset_config_path(name)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_dataset_config(config: dict[str, Any]) -> None:
    if not config.get("name"):
        raise ValueError("Dataset config requires a 'name'.")
    path = _dataset_config_path(config["name"])  # type: ignore[index]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def delete_dataset(name: str) -> None:
    path = _dataset_config_path(name)
    if path.exists():
        path.unlink()


def duplicate_dataset(base_name: str, new_name: str, *, new_description: str | None = None) -> dict[str, Any] | None:
    base = load_dataset_config(base_name)
    if base is None:
        return None
    new_cfg = {
        **{k: v for k, v in base.items() if k not in {"name", "created_at", "updated_at"}},
        "name": new_name,
    }
    if new_description is not None:
        new_cfg["description"] = new_description
    save_dataset_config(new_cfg)
    return new_cfg


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


def _compute_included_column(df: pd.DataFrame, id_field: str, excluded_ids: set[str]) -> pd.Series:
    if id_field not in df.columns:
        # If no id is present, everything is considered included
        return pd.Series([1] * len(df), index=df.index)
    ids = df[id_field].astype(str).fillna("")
    return ids.map(lambda x: 0 if x in excluded_ids else 1)


def load_dataset(name: str) -> tuple[dict[str, Any], pd.DataFrame] | tuple[None, None]:
    """Load a dataset dynamically from sightings.csv using its config.

    Returns meta and a dataframe with an 'included' column (1/0) marking row inclusion
    according to the dataset's excluded_ids. The dataframe rows reflect current
    sightings.csv filtered by the dataset's filters.
    """
    # Prefer new dynamic config
    cfg = load_dataset_config(name)
    if cfg is not None and ("filters" in cfg or "excluded_ids" in cfg or "columns" in cfg):
        df = load_data()
        df = _apply_filters(df, cfg.get("filters", []))
        id_field = cfg.get("id_field", "id")
        excluded_ids: set[str] = set(str(x) for x in cfg.get("excluded_ids", []))
        included_series = _compute_included_column(df, id_field, excluded_ids)
        # Add 'included' column for UI/usecases compatibility
        df_out = df.copy()
        df_out.insert(0, "included", included_series.astype(int).values)
        meta = {
            "name": cfg.get("name", name),
            "description": cfg.get("description", ""),
            "created_at": cfg.get("created_at", ""),
            "updated_at": cfg.get("updated_at", ""),
            "columns": cfg.get("columns", []),
            "filters": cfg.get("filters", []),
            "excluded_ids": list(excluded_ids),
            "id_field": id_field,
        }
        return meta, df_out

    # Backward compatibility: legacy datasets (meta + csv with 'included')
    # Keep existing behavior for old files if present
    meta_path = _dataset_config_path(name)
    csv_path = (DATASETS_DIR / _safe_name(name)).with_suffix(".csv")
    if meta_path.exists() and csv_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                legacy_meta = json.load(f)
            df = pd.read_csv(csv_path, sep=";", dtype=str, keep_default_na=True, na_values=["", "NA", "NaN"])
            return legacy_meta, df
        except Exception:
            return None, None

    return None, None


def dataset_selector_ui(label: str = "Datensatz wählen", key: str = "dataset_select") -> str | None:
    names = list_dataset_names()
    if not names:
        st.info("Bitte zuerst unter 'Datensätze' einen Datensatz erstellen.")
        return None
    choice = st.selectbox(label, options=["— Bitte wählen —"] + names, index=0, key=key)
    if choice == "— Bitte wählen —":
        return None
    return choice
