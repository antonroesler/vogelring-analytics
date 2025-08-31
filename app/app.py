from __future__ import annotations

import streamlit as st
from views.data_view import render_data_view
from views.data_sets import render_data_sets


st.set_page_config(page_title="Vogelring Analytics", layout="wide")


def main() -> None:
    # App title in the main content area (sidebar keeps navigation on top)
    st.title("Vogelring Analytics")

    # Use Streamlit's native navigation instead of radio buttons
    data_view_page = st.Page(render_data_view, title="Daten Ansichten", icon="📊")
    data_sets_page = st.Page(render_data_sets, title="Datensätze", icon="🗂️")

    pg = st.navigation([data_view_page, data_sets_page])
    pg.run()


if __name__ == "__main__":
    main()
