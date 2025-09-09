from __future__ import annotations

from typing import Any

import math
import pandas as pd
import pydeck as pdk
import streamlit as st

from util.col_mapping import mapping
from util.datasets import dataset_selector_ui, load_dataset
from util.plotting import (
    get_plottable_categorical_columns,
    get_plottable_numeric_columns,
)


def _valid_lat_lon(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    # Ensure numeric
    for c in ["lat", "lon"]:
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce")
    mask = work["lat"].notna() & work["lon"].notna()
    return work.loc[mask]


def _infer_categorical_columns(df: pd.DataFrame, max_unique: int = 30) -> list[str]:
    return get_plottable_categorical_columns(df, max_unique=max_unique)


def _infer_numeric_columns(df: pd.DataFrame) -> list[str]:
    return get_plottable_numeric_columns(df)


def _palette_categorical(n: int) -> list[list[int]]:
    # A set of distinct, colorblind-friendly colors (repeats if needed)
    base = [
        [31, 119, 180],  # blue
        [255, 127, 14],  # orange
        [44, 160, 44],  # green
        [214, 39, 40],  # red
        [148, 103, 189],  # purple
        [140, 86, 75],  # brown
        [227, 119, 194],  # pink
        [127, 127, 127],  # gray
        [188, 189, 34],  # olive
        [23, 190, 207],  # cyan
    ]
    colors: list[list[int]] = []
    for i in range(n):
        colors.append(base[i % len(base)])
    return colors


def _palette_viridis(value_0_1: float) -> list[int]:
    # Lightweight approximation of viridis (no external deps)
    # Define a few key stops and interpolate linearly
    stops = [
        (0.0, (68, 1, 84)),
        (0.25, (59, 82, 139)),
        (0.5, (33, 145, 140)),
        (0.75, (94, 201, 97)),
        (1.0, (253, 231, 37)),
    ]
    v = min(max(value_0_1, 0.0), 1.0)
    for i in range(len(stops) - 1):
        v0, c0 = stops[i]
        v1, c1 = stops[i + 1]
        if v0 <= v <= v1:
            t = (v - v0) / (v1 - v0) if v1 > v0 else 0.0
            r = int(c0[0] + t * (c1[0] - c0[0]))
            g = int(c0[1] + t * (c1[1] - c0[1]))
            b = int(c0[2] + t * (c1[2] - c0[2]))
            return [r, g, b]
    return list(stops[-1][1])


def _compute_view_state(df: pd.DataFrame) -> pdk.ViewState:
    lat = pd.to_numeric(df["lat"], errors="coerce")
    lon = pd.to_numeric(df["lon"], errors="coerce")
    lat_mean = float(lat.mean()) if lat.notna().any() else 50.1
    lon_mean = float(lon.mean()) if lon.notna().any() else 8.7
    # Approximate zoom from spread
    lat_range = float(lat.max() - lat.min()) if lat.notna().any() else 0.1
    lon_range = float(lon.max() - lon.min()) if lon.notna().any() else 0.1
    spread = max(lat_range, lon_range)
    zoom = 11.0
    if spread > 20:
        zoom = 3.5
    elif spread > 5:
        zoom = 6.0
    elif spread > 1:
        zoom = 8.0
    elif spread > 0.2:
        zoom = 10.0
    return pdk.ViewState(latitude=lat_mean, longitude=lon_mean, zoom=zoom)


def render_map_usecase() -> None:
    st.header("Karte")

    selected = dataset_selector_ui()
    if not selected:
        return

    meta, df = load_dataset(selected)
    if meta is None or df is None:
        st.error("Datensatz konnte nicht geladen werden.")
        return

    # Filter to included rows by default
    include_hidden = st.checkbox("Auch ausgeblendete Zeilen anzeigen", value=False, key="map_show_hidden")
    if "included" in df.columns and not include_hidden:
        mask = pd.Series(df["included"]).astype(str).isin(["1", "True", "true", "TRUE"])
        df = df.loc[mask]

    df = _valid_lat_lon(df)
    if len(df) == 0:
        st.info("Keine Koordinaten (lat/lon) im ausgewählten Datensatz vorhanden.")
        return

    st.subheader("Darstellung")
    ctrl_cols = st.columns([3, 2])
    with ctrl_cols[0]:
        mode = st.radio("Farbmodus", options=["Keine", "Kategorie", "Numerisch"], horizontal=True, key="map_color_mode")
    with ctrl_cols[1]:
        radius = st.slider("Punkt-Radius (Meter)", min_value=5, max_value=200, value=60, step=5, key="map_point_radius")

    colors: list[list[int]] | None = None
    legend_data: list[tuple[str, list[int]]] | None = None

    if mode == "Kategorie":
        cat_cols = _infer_categorical_columns(df)
        if not cat_cols:
            st.info("Keine geeigneten kategorialen Spalten gefunden.")
        else:
            col = st.selectbox("Spalte (Kategorie)", options=[mapping.get(c, c) for c in cat_cols], index=0)
            internal = {mapping.get(c, c): c for c in cat_cols}[col]
            vals = df[internal].astype(str).fillna("")
            categories = sorted(vals.unique().tolist())
            palette = _palette_categorical(len(categories))
            color_map: dict[str, list[int]] = {cat: palette[i] for i, cat in enumerate(categories)}
            colors = [color_map.get(v, [127, 127, 127]) + [160] for v in vals]
            legend_data = [(cat if cat != "" else "(leer)", color_map[cat]) for cat in categories]

    elif mode == "Numerisch":
        num_cols = _infer_numeric_columns(df)
        if not num_cols:
            st.info("Keine geeigneten numerischen Spalten gefunden.")
        else:
            col = st.selectbox("Spalte (Numerisch)", options=[mapping.get(c, c) for c in num_cols], index=0)
            internal = {mapping.get(c, c): c for c in num_cols}[col]
            series = pd.to_numeric(df[internal], errors="coerce")
            vmin = float(series.min()) if series.notna().any() else 0.0
            vmax = float(series.max()) if series.notna().any() else 1.0
            if vmin == vmax:
                vmax = vmin + 1.0
            # Optional: user override range
            rng_cols = st.columns(2)
            with rng_cols[0]:
                user_min = st.number_input("Min", value=vmin)
            with rng_cols[1]:
                user_max = st.number_input("Max", value=vmax)
            vmin, vmax = float(user_min), float(user_max)
            denom = vmax - vmin if vmax > vmin else 1.0
            norm = series.map(lambda x: (float(x) - vmin) / denom if pd.notna(x) else math.nan)
            cols = []
            for nv in norm:
                if pd.isna(nv):
                    cols.append([180, 180, 180, 80])
                else:
                    r, g, b = _palette_viridis(min(max(nv, 0.0), 1.0))
                    cols.append([r, g, b, 160])
            colors = cols

            # Numeric legend (min -> max gradient). Render as small color bar.
            st.caption("Legende")
            legend_vals = pd.DataFrame(
                {
                    "x": list(range(100)),
                    "c": [i / 99 for i in range(100)],
                }
            )
            legend_vals["r"] = legend_vals["c"].map(lambda v: _palette_viridis(v)[0])
            legend_vals["g"] = legend_vals["c"].map(lambda v: _palette_viridis(v)[1])
            legend_vals["b"] = legend_vals["c"].map(lambda v: _palette_viridis(v)[2])
            # Use image layer for legend via HTML
            # Fallback: display min/max only
            st.write(f"{vmin:.2f}  ")
            st.write(f"{vmax:.2f}")

    # Build Layer
    plot_df = df.copy()
    if colors is None:
        # default neutral fill
        colors = [[30, 144, 255, 140]] * len(plot_df)
    plot_df["__color__"] = colors

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=plot_df,
        get_position="[lon, lat]",
        get_fill_color="__color__",
        get_radius=radius,
        pickable=True,
        stroked=False,
    )

    tooltip = {
        "text": "{species}\n{place}\n{date}",
    }

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=_compute_view_state(plot_df),
        tooltip=tooltip,
        map_style=pdk.map_styles.LIGHT,
    )
    st.pydeck_chart(deck, use_container_width=True)

    # Render legend for categorical mode
    if mode == "Kategorie" and legend_data:
        st.caption("Legende")
        # Simple two-column legend grid
        for name, rgb in legend_data:
            a, b = st.columns([1, 9])
            with a:
                st.color_picker(
                    " ",
                    value="#%02x%02x%02x" % (rgb[0], rgb[1], rgb[2]),
                    key=f"lg_{name}",
                    label_visibility="collapsed",
                    disabled=True,
                )
            with b:
                st.write(name)


def _two_month_bin(month: int) -> str:
    pairs = [
        (1, "Jan–Feb"),
        (3, "Mär–Apr"),
        (5, "Mai–Jun"),
        (7, "Jul–Aug"),
        (9, "Sep–Okt"),
        (11, "Nov–Dez"),
    ]
    for start, label in pairs:
        if start <= month <= start + 1:
            return label
    return "?"
