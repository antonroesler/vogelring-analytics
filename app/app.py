from __future__ import annotations

import streamlit as st
from views.data_view import render_data_view
from views.data_sets import render_data_sets


st.set_page_config(page_title="Vogelring Analytics", layout="wide")


def _sidebar() -> str:
    st.sidebar.title("Vogelring Analytics")
    view = st.sidebar.radio(
        "Ansicht",
        options=["Daten Ansichten", "Datensätze"],
        format_func=lambda x: x,
        horizontal=False,
    )
    return view


def main() -> None:
    view = _sidebar()
    if view == "Daten Ansichten":
        render_data_view()
    elif view == "Datensätze":
        render_data_sets()


if __name__ == "__main__":
    main()
