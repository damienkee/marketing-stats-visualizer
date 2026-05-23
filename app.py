from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics import ColumnConfig, get_postcode_series, get_source_series, get_ticket_type_series, prepare_data

st.set_page_config(page_title="Marketing Statistics Visualizer", layout="wide")

st.title("Marketing Statistics Visualizer")
st.caption("Analyze booking trends and ticket demand from a local CSV file.")

DEFAULT_CSV = Path(__file__).parent / "sample_data" / "data.csv"


@st.cache_data(show_spinner=False)
def load_dataframe(uploaded_file_bytes: bytes | None) -> pd.DataFrame:
    if uploaded_file_bytes is not None:
        return pd.read_csv(BytesIO(uploaded_file_bytes))
    return pd.read_csv(DEFAULT_CSV)


def checkbox_filter(
    options: list[str],
    key_prefix: str,
    label: str,
    default_unchecked: set[str] | None = None,
) -> list[str]:
    st.markdown(label)
    if not options:
        return []

    unchecked = {value.lower() for value in (default_unchecked or set())}
    selected: list[str] = []
    cols = st.columns(3)
    for idx, option in enumerate(options):
        col = cols[idx % 3]
        checked = col.checkbox(option, value=(option.lower() not in unchecked), key=f"{key_prefix}_{idx}")
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

all_columns = list(raw_df.columns)

DEFAULT_NUMBER_TICKETS = "Number Of Tickets"
DEFAULT_DATE = "Date Booked (UTC+10)"
DEFAULT_TIME = "Time Booked"
DEFAULT_SOURCE = "Booking Data: How Did You Find Out About Our Show?"
DEFAULT_OTHER_SPECIFY = "Booking Data: Sub 1: Please Specify"
DEFAULT_TICKET_TYPE = "Ticket Type"
DEFAULT_POSTCODE = "Booking Data: What Is Your Postcode"

date_col = DEFAULT_DATE if DEFAULT_DATE in all_columns else next((c for c in all_columns if "date" in c.lower()), all_columns[0])
time_col = DEFAULT_TIME if DEFAULT_TIME in all_columns else next((c for c in all_columns if "time" in c.lower()), all_columns[0])
source_col = DEFAULT_SOURCE if DEFAULT_SOURCE in all_columns else next(
    (c for c in all_columns if "find" in c.lower() or "source" in c.lower() or "hear" in c.lower()), all_columns[0]
)
other_specify_col = DEFAULT_OTHER_SPECIFY if DEFAULT_OTHER_SPECIFY in all_columns else None
number_tickets_col = DEFAULT_NUMBER_TICKETS if DEFAULT_NUMBER_TICKETS in all_columns else None
ticket_type_col = DEFAULT_TICKET_TYPE if DEFAULT_TICKET_TYPE in all_columns else next(
    (c for c in all_columns if "ticket" in c.lower() or "type" in c.lower()), None
)
postcode_col = DEFAULT_POSTCODE if DEFAULT_POSTCODE in all_columns else next(
    (c for c in all_columns if "postcode" in c.lower()), None
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

st.sidebar.header("Filters")
exclude_box_office = st.sidebar.checkbox("Exclude box office", value=False)

st.sidebar.header("Map")
map_style_options = [
    "open-street-map",
    "carto-positron",
    "carto-darkmatter",
    "white-bg",
    "stamen-terrain",
    "stamen-toner",
    "stamen-watercolor",
]
selected_map_style = st.sidebar.selectbox("Map base style", options=map_style_options, index=1)

columns = ColumnConfig(
    date_col=date_col,
    time_col=time_col,
    source_col=source_col,
    other_specify_col=other_specify_col,
    number_of_tickets_col=number_tickets_col,
    ticket_type_col=ticket_type_col,
    postcode_col=postcode_col,
)

try:
    prepared_df = prepare_data(raw_df, columns)
except Exception as exc:
    st.error(str(exc))
    st.stop()

if exclude_box_office:
    prepared_df = prepared_df[~prepared_df["source"].str.contains("BO", case=True, na=False)]

st.subheader("Marketing Response Trend")
source_series = get_source_series(prepared_df, mode=mode_label, time_group=time_group)
y_title = "Tickets" if mode_label == "tickets" else "Bookings"

other_mask = source_series["source"].str.lower().str.startswith("other")
non_other_series = source_series[~other_mask]
other_series = source_series[other_mask]

all_sources = sorted(non_other_series["source"].unique().tolist())
selected_sources = checkbox_filter(
    all_sources,
    "source_filter",
    "Tick responses to include",
    default_unchecked={"Unknown"},
)
filtered_source = non_other_series[non_other_series["source"].isin(selected_sources)]

chart_type_source = st.radio(
    "Chart type",
    options=["Line", "Stacked columns"],
    index=1,
    horizontal=True,
    key="chart_type_source",
)

if filtered_source.empty:
    st.info("No data points for selected non-'Other' responses.")
elif chart_type_source == "Stacked columns":
    fig_source = px.bar(
        filtered_source,
        x="period",
        y="value",
        color="source",
        barmode="stack",
        labels={"period": "Date/Time", "value": y_title, "source": "Response"},
        title=f"Marketing response over time ({mode_label})",
    )
    fig_source.update_layout(
        legend_title_text="Response",
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor="rgba(200,200,200,0.4)", dtick=86400000),
    )
    st.plotly_chart(fig_source, width="stretch")
else:
    fig_source = px.line(
        filtered_source,
        x="period",
        y="value",
        color="source",
        markers=True,
        labels={"period": "Date/Time", "value": y_title, "source": "Response"},
        title=f"Marketing response over time ({mode_label})",
    )
    fig_source.update_layout(
        legend_title_text="Response",
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor="rgba(200,200,200,0.4)", dtick=86400000),
    )
    st.plotly_chart(fig_source, width="stretch")

st.subheader("Other Responses")
if other_series.empty:
    st.info("No 'Other' responses in the data.")
else:
    other_counts = (
        other_series.groupby("source", as_index=False)["value"]
        .sum()
        .rename(columns={"source": "Response", "value": y_title})
        .sort_values(y_title, ascending=False)
        .reset_index(drop=True)
    )
    other_counts.index += 1
    st.dataframe(other_counts, height=(len(other_counts) + 1) * 35 + 3, width="stretch")

st.subheader("Ticket Type Breakdown")
ticket_series = get_ticket_type_series(prepared_df, time_group=time_group)
all_ticket_types = sorted(ticket_series["ticket_type"].unique().tolist())
selected_ticket_types = checkbox_filter(
    all_ticket_types,
    "ticket_type_filter",
    "Tick ticket types to include",
    default_unchecked={"Final dress rehearsal"},
)

filtered_ticket = ticket_series[ticket_series["ticket_type"].isin(selected_ticket_types)]

if filtered_ticket.empty:
    st.info("No data points for selected ticket types.")
else:
    ticket_breakdown = filtered_ticket.groupby("ticket_type", as_index=False)["value"].sum()
    fig_ticket = px.pie(
        ticket_breakdown,
        names="ticket_type",
        values="value",
        title="Ticket type share",
        hole=0.35,
    )
    fig_ticket.update_traces(
        textposition="outside",
        textinfo="label+percent",
        pull=0.02,
    )
    fig_ticket.update_layout(uniformtext_minsize=10, uniformtext_mode="hide")
    fig_ticket.update_layout(legend_title_text="Ticket Type")
    st.plotly_chart(fig_ticket, width="stretch")

with st.expander("Preview prepared data"):
    st.dataframe(prepared_df.head(100), width="stretch")

st.subheader("Postcode Hotspot Map")
_POSTCODE_LOOKUP = Path(__file__).parent / "sample_data" / "brisbane_postcodes.csv"

@st.cache_data(show_spinner=False)
def load_postcode_lookup() -> pd.DataFrame:
    return pd.read_csv(_POSTCODE_LOOKUP, dtype={"postcode": str})

postcode_series = get_postcode_series(prepared_df)
if postcode_series.empty:
    st.info("No postcode data available.")
else:
    postcode_lookup = load_postcode_lookup()
    map_df = postcode_series.merge(postcode_lookup[["postcode", "suburb", "lat", "lon"]], on="postcode", how="inner")
    if map_df.empty:
        st.info("No postcodes matched the Brisbane lookup table.")
    else:
        fig_map = px.scatter_map(
            map_df,
            lat="lat",
            lon="lon",
            size="tickets",
            hover_name="suburb",
            hover_data={"postcode": True, "tickets": True, "lat": False, "lon": False},
            size_max=50,
            zoom=9,
            center={"lat": -27.47, "lon": 153.02},
            map_style=selected_map_style,
            title="Tickets sold by postcode",
        )
        min_marker_size = 12.0
        max_marker_size = 50.0
        tickets = map_df["tickets"].astype(float)
        if tickets.max() == tickets.min():
            bubble_size = pd.Series(min_marker_size, index=map_df.index)
        else:
            bubble_size = min_marker_size + (tickets - tickets.min()) * (max_marker_size - min_marker_size) / (tickets.max() - tickets.min())
        halo_size = bubble_size + 2.0

        halo_trace = go.Scattermap(
            lat=map_df["lat"],
            lon=map_df["lon"],
            mode="markers",
            marker={
                "size": halo_size,
                "sizemode": "diameter",
                "color": "#888888",
                "opacity": 0.9,
                "allowoverlap": True,
            },
            hoverinfo="skip",
            showlegend=False,
        )
        main_trace = go.Scattermap(
            lat=map_df["lat"],
            lon=map_df["lon"],
            mode="markers+text",
            marker={
                "size": bubble_size,
                "sizemode": "diameter",
                "color": "#1f77b4",
                "opacity": 0.75,
                "allowoverlap": True,
            },
            text=map_df["tickets"].astype(str),
            textposition="middle center",
            textfont={"color": "white", "size": 11},
            customdata=map_df[["suburb", "postcode", "tickets"]],
            hovertemplate="%{customdata[0]}<br>Postcode: %{customdata[1]}<br>Tickets: %{customdata[2]}<extra></extra>",
            showlegend=False,
        )
        fig_map_layout = fig_map.layout
        fig_map = go.Figure(layout=fig_map_layout)
        fig_map.add_trace(halo_trace)
        fig_map.add_trace(main_trace)
        fig_map.update_layout(width=800, height=800)
        st.plotly_chart(fig_map, width="content")
