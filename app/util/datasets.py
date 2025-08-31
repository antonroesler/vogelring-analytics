from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from .storage import STORAGE_DIR


DATASETS_DIR = STORAGE_DIR / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)


def list_dataset_names() -> list[str]:
    return sorted([p.stem for p in DATASETS_DIR.glob("*.json")])


def dataset_paths(name: str) -> tuple[Path, Path]:
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip().replace(" ", "_")
    base = DATASETS_DIR / safe
    return base.with_suffix(".json"), base.with_suffix(".csv")


def load_dataset(name: str) -> tuple[dict[str, Any], pd.DataFrame] | tuple[None, None]:
    meta_path, data_path = dataset_paths(name)
    if not meta_path.exists() or not data_path.exists():
        return None, None
    with open(meta_path, "r", encoding="utf-8") as f:
        import json

        meta = json.load(f)
    df = pd.read_csv(data_path, sep=";", dtype=str, keep_default_na=True, na_values=["", "NA", "NaN"])
    return meta, df


def dataset_selector_ui(label: str = "Datensatz wählen", key: str = "dataset_select") -> str | None:
    names = list_dataset_names()
    if not names:
        st.info("Bitte zuerst unter 'Datensätze' einen Datensatz erstellen.")
        return None
    choice = st.selectbox(label, options=["— Bitte wählen —"] + names, index=0, key=key)
    if choice == "— Bitte wählen —":
        return None
    return choice
