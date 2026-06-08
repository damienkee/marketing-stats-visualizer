from __future__ import annotations

from pathlib import Path

import streamlit as st

st.set_page_config(page_title="How This App Works", layout="wide")

st.title("How This App Works")
st.caption("High-level architecture, libraries used, and key code excerpts.")

ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
ANALYTICS_FILE = ROOT / "src" / "analytics.py"


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def snippet_by_lines(path: Path, start: int, end: int) -> str:
    lines = read_lines(path)
    safe_start = max(start, 1)
    safe_end = min(end, len(lines))
    block = lines[safe_start - 1 : safe_end]
    return "\n".join(block)


st.subheader("Libraries used")

st.markdown(
    """
- **Streamlit** powers the user interface (sidebar controls, charts, tables, and multi-page navigation).
- **Pandas** cleans and transforms CSV rows, including date/time parsing and aggregations.
- **Plotly Express / Graph Objects** renders interactive charts and the postcode hotspot map.
- **Pathlib** handles local file paths for sample data and code lookup.
"""
)

col1, col2 = st.columns(2)
with col1:
    st.markdown("**UI + chart libraries in app.py**")
    st.code(snippet_by_lines(APP_FILE, 1, 12), language="python")
with col2:
    st.markdown("**Core data model in analytics.py**")
    st.code(snippet_by_lines(ANALYTICS_FILE, 1, 20), language="python")

st.subheader("Data flow")
st.markdown(
    """
1. CSV is loaded (uploaded file or default sample).
2. Columns are normalized and transformed in `prepare_data`.
3. The app derives chart-ready datasets (marketing trend, ticket mix, postcode totals).
4. Plotly charts and tables are rendered with user-selected filters.
"""
)

st.markdown("**CSV load + preprocessing setup**")
st.code(snippet_by_lines(APP_FILE, 18, 58), language="python")

st.markdown("**prepare_data: datetime + source/ticket normalization**")
st.code(snippet_by_lines(ANALYTICS_FILE, 80, 140), language="python")

st.subheader("Marketing and ticket analytics")
st.markdown(
    """
- Marketing response series can be viewed as lines or stacked columns.
- Ticket types are summarized in a pie chart after filtering.
- "Other" responses are separated and summarized in a readable table.
"""
)

st.markdown("**Marketing and ticket visual sections**")
st.code(snippet_by_lines(APP_FILE, 130, 245), language="python")

st.subheader("Postcode hotspot map")
st.markdown(
    """
The map uses postcode totals from analytics and joins them to a lookup table containing latitude/longitude.
Bubble size represents volume, and ticket counts are overlaid as text labels.
"""
)

st.markdown("**Postcode aggregation helper**")
st.code(snippet_by_lines(ANALYTICS_FILE, 165, 182), language="python")

st.markdown("**Map rendering section**")
st.code(snippet_by_lines(APP_FILE, 246, 330), language="python")

st.divider()
st.link_button("Back to dashboard", "/")
