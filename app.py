from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics import ColumnConfig, get_source_series, get_ticket_type_series, prepare_data

st.set_page_config(page_title="Marketing Statistics Visualizer", layout="wide")

st.title("Marketing Statistics Visualizer")
st.caption("Analyze booking trends and ticket demand from a local CSV file.")

DEFAULT_CSV = Path(__file__).parent / "sample_data" / "bookings_sample.csv"


@st.cache_data(show_spinner=False)
def load_dataframe(uploaded_file_bytes: bytes | None) -> pd.DataFrame:
    if uploaded_file_bytes is not None:
        return pd.read_csv(BytesIO(uploaded_file_bytes))
    return pd.read_csv(DEFAULT_CSV)


def checkbox_filter(options: list[str], key_prefix: str, label: str) -> list[str]:
    st.markdown(label)
    if not options:
        return []

    selected: list[str] = []
    cols = st.columns(3)
    for idx, option in enumerate(options):
        col = cols[idx % 3]
        checked = col.checkbox(option, value=True, key=f"{key_prefix}_{idx}")
        if checked:
            selected.append(option)
    return selected


st.sidebar.header("Data Source")
uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])

if uploaded is None:
    st.sidebar.info(f"Using sample file: {DEFAULT_CSV.name}")

uploaded_bytes = uploaded.getvalue() if uploaded is not None else None

try:
    raw_df = load_dataframe(uploaded_bytes)
except Exception as exc:  # pragma: no cover
    st.error(f"Could not read CSV file: {exc}")
    st.stop()

if raw_df.empty:
    st.warning("The CSV file is empty.")
    st.stop()

raw_df.columns = [str(column).strip() for column in raw_df.columns]

st.sidebar.header("Column Mapping")
all_columns = list(raw_df.columns)

DEFAULT_NUMBER_TICKETS = "Number Of Tickets"
DEFAULT_DATE = "Date Booked (UTC+10)"
DEFAULT_TIME = "Time Booked"
DEFAULT_SOURCE = "Booking Data: How Did You Find Out About Our Show?"
DEFAULT_OTHER_SPECIFY = "Booking Data: Sub 1: Please Specify"
DEFAULT_TICKET_TYPE = "Ticket Type"

suggested_date = DEFAULT_DATE if DEFAULT_DATE in all_columns else next((c for c in all_columns if "date" in c.lower()), all_columns[0])
suggested_time = DEFAULT_TIME if DEFAULT_TIME in all_columns else next((c for c in all_columns if "time" in c.lower()), all_columns[0])
suggested_source = DEFAULT_SOURCE if DEFAULT_SOURCE in all_columns else next(
    (c for c in all_columns if "find" in c.lower() or "source" in c.lower() or "hear" in c.lower()), all_columns[0]
)
suggested_other_specify = DEFAULT_OTHER_SPECIFY if DEFAULT_OTHER_SPECIFY in all_columns else None
suggested_number_tickets = DEFAULT_NUMBER_TICKETS if DEFAULT_NUMBER_TICKETS in all_columns else None
suggested_ticket = DEFAULT_TICKET_TYPE if DEFAULT_TICKET_TYPE in all_columns else next((c for c in all_columns if "ticket" in c.lower() or "type" in c.lower()), all_columns[0])
has_ticket_like_column = any("ticket" in c.lower() or "type" in c.lower() for c in all_columns)

date_col = st.sidebar.selectbox(
    "Booking date column",
    options=all_columns,
    index=all_columns.index(suggested_date),
)

time_col = st.sidebar.selectbox(
    "Booking time column",
    options=all_columns,
    index=all_columns.index(suggested_time),
)

source_col = st.sidebar.selectbox(
    "Marketing response column",
    options=all_columns,
    index=all_columns.index(suggested_source),
)

other_specify_enabled = st.sidebar.checkbox(
    "CSV has Other/Please Specify column",
    value=suggested_other_specify is not None,
)
other_specify_col = None
if other_specify_enabled:
    other_specify_col = st.sidebar.selectbox(
        "Other/Please Specify column",
        options=all_columns,
        index=all_columns.index(suggested_other_specify) if suggested_other_specify in all_columns else 0,
    )

number_tickets_enabled = st.sidebar.checkbox(
    "CSV has Number Of Tickets column",
    value=suggested_number_tickets is not None,
)
number_tickets_col = None
if number_tickets_enabled:
    number_tickets_col = st.sidebar.selectbox(
        "Number Of Tickets column",
        options=all_columns,
        index=all_columns.index(suggested_number_tickets) if suggested_number_tickets in all_columns else 0,
    )

ticket_col_enabled = st.sidebar.checkbox("CSV has ticket type column", value=has_ticket_like_column)
ticket_type_col = None
if ticket_col_enabled:
    ticket_type_col = st.sidebar.selectbox(
        "Ticket type column",
        options=all_columns,
        index=all_columns.index(suggested_ticket),
    )

st.sidebar.header("Aggregation")
group_by_bookings = st.sidebar.checkbox(
    "Group by bookings instead of tickets",
    value=False,
)
mode_label = "bookings" if group_by_bookings else "tickets"

time_group_options = {
    "Hourly": "h",
    "Daily": "D",
    "Weekly": "W",
    "Monthly": "M",
}
time_group_label = st.sidebar.selectbox("Group time by", options=list(time_group_options.keys()), index=1)
time_group = time_group_options[time_group_label]

columns = ColumnConfig(
    date_col=date_col,
    time_col=time_col,
    source_col=source_col,
    other_specify_col=other_specify_col,
    number_of_tickets_col=number_tickets_col,
    ticket_type_col=ticket_type_col,
)

try:
    prepared_df = prepare_data(raw_df, columns)
except Exception as exc:
    st.error(str(exc))
    st.stop()

st.subheader("Marketing Response Trend")
source_series = get_source_series(prepared_df, mode=mode_label, time_group=time_group)

all_sources = sorted(source_series["source"].unique().tolist())
selected_sources = checkbox_filter(all_sources, "source_filter", "Tick responses to include")

filtered_source = source_series[source_series["source"].isin(selected_sources)]

if filtered_source.empty:
    st.info("No data points for selected responses.")
else:
    y_title = "Tickets" if mode_label == "tickets" else "Bookings"
    fig_source = px.line(
        filtered_source,
        x="period",
        y="value",
        color="source",
        markers=True,
        labels={"period": "Date/Time", "value": y_title, "source": "Response"},
        title=f"Marketing response over time ({mode_label})",
    )
    fig_source.update_layout(legend_title_text="Response")
    st.plotly_chart(fig_source, use_container_width=True)

st.subheader("Ticket Type Trend")
ticket_series = get_ticket_type_series(prepared_df, time_group=time_group)
all_ticket_types = sorted(ticket_series["ticket_type"].unique().tolist())
selected_ticket_types = checkbox_filter(
    all_ticket_types,
    "ticket_type_filter",
    "Tick ticket types to include",
)

filtered_ticket = ticket_series[ticket_series["ticket_type"].isin(selected_ticket_types)]

if filtered_ticket.empty:
    st.info("No data points for selected ticket types.")
else:
    fig_ticket = px.line(
        filtered_ticket,
        x="period",
        y="value",
        color="ticket_type",
        markers=True,
        labels={"period": "Date/Time", "value": "Tickets Sold", "ticket_type": "Ticket Type"},
        title="Ticket types sold over time",
    )
    fig_ticket.update_layout(legend_title_text="Ticket Type")
    st.plotly_chart(fig_ticket, use_container_width=True)

with st.expander("Preview prepared data"):
    st.dataframe(prepared_df.head(100), use_container_width=True)
