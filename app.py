from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.analytics import (
    ColumnConfig,
    get_postcode_series,
    get_session_ticket_type_breakdown,
    get_source_series,
    get_ticket_type_series,
    prepare_data,
)

st.set_page_config(page_title="Marketing Statistics Visualizer", layout="wide")

st.title("Marketing Statistics Visualizer")
st.caption("Analyze booking trends and ticket demand from a local CSV file.")

DEFAULT_CSV = Path(__file__).parent / "sample_data" / "data.csv"
ROOT_DIR = Path(__file__).parent
ANALYTICS_FILE = ROOT_DIR / "src" / "analytics.py"


def get_code_snippet(path: Path, start: int, end: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(start, 1)
    end = min(end, len(lines))
    return "\n".join(lines[start - 1 : end])


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


def add_monday_guides(fig: go.Figure, date_values: pd.Series) -> None:
    if date_values.empty:
        return

    min_date = pd.to_datetime(date_values.min(), errors="coerce")
    max_date = pd.to_datetime(date_values.max(), errors="coerce")
    if pd.isna(min_date) or pd.isna(max_date):
        return

    first_day = min_date.normalize()
    days_to_monday = (7 - first_day.weekday()) % 7
    first_monday = first_day + pd.Timedelta(days=days_to_monday)
    monday_marks = pd.date_range(
        start=first_monday,
        end=max_date.normalize(),
        freq="W-MON",
    )

    for monday in monday_marks:
        fig.add_vline(
            x=monday,
            line_width=1,
            line_dash="dot",
            line_color="rgba(90,90,90,0.45)",
        )


def canonical_ticket_category(label: str) -> str:
    normalized = " ".join(label.lower().replace("_", " ").replace("-", " ").split())
    alias_to_named = {
        "adult": "adult",
        "adults": "adult",
        "concession": "concession",
        "concessions": "concession",
        "conceccsion": "concession",
        "concesssion": "concession",
        "family": "family",
        "families": "family",
        "junior": "junior",
        "juniors": "junior",
        "group": "group",
        "group10": "group",
        "group box office": "group",
        "season ticket": "season ticket",
        "season tickets": "season ticket",
        "subscriber": "season ticket",
        "subscribers": "season ticket",
        "final dress rehearsal": "final dress rehearsal",
        "final dress rehersal": "final dress rehearsal",
        "complimentary": "complimentary",
        "complementary": "complimentary",
        "comp": "complimentary",
        "front of house": "front of house",
        "foh": "front of house",
        "house seat": "house seats",
        "house seats": "house seats",
        "unsold": "unsold",
        "unknown": "unknown",
    }
    mapped = alias_to_named.get(normalized)
    if mapped is not None:
        return mapped

    if "unsold" in normalized:
        return "unsold"
    if normalized.startswith("season ticket") or "subscriber" in normalized:
        return "season ticket"
    if normalized.startswith("adult"):
        return "adult"
    if normalized.startswith("concession") or normalized.startswith("conce"):
        return "concession"
    if normalized.startswith("family"):
        return "family"
    if normalized.startswith("junior"):
        return "junior"
    if normalized.startswith("group"):
        return "group"
    if normalized.startswith("final dress"):
        return "final dress rehearsal"
    if normalized.startswith("compl"):
        return "complimentary"
    if normalized.startswith("house seat"):
        return "house seats"

    return normalized


def get_ordered_legend_categories(categories: list[str]) -> list[str]:
    named_category_order = [
        "season ticket",
        "adult",
        "concession",
        "family",
        "junior",
        "group",
        "final dress rehearsal",
        "complimentary",
        "house seats",
        "front of house",
        "unknown",
        "unsold",
    ]
    category_rank = {name: idx for idx, name in enumerate(named_category_order)}

    return sorted(
        {str(item).strip() for item in categories if str(item).strip()},
        key=lambda value: (category_rank.get(canonical_ticket_category(value), 10_000), value.lower()),
    )


def build_pie_color_map(categories: list[str]) -> dict[str, str]:
    named_category_colors = {
        "unsold": "#b0b0b0",
        "season ticket": "#9467bd",
        "adult": "#1f77b4",
        "concession": "#2ca02c",
        "family": "#e377c2",
        "junior": "#ff7f0e",
        "group": "#17becf",
        "final dress rehearsal": "#bcbd22",
        "complimentary": "#d62728",
        "house seats": "#1f3b5c",
        "front of house": "#8c564b",
        "unknown": "#7f7f7f",
    }
    palette = (
        px.colors.qualitative.Safe
        + px.colors.qualitative.Set3
        + px.colors.qualitative.Plotly
        + px.colors.qualitative.Bold
    )

    color_map: dict[str, str] = {}
    palette_index = 0
    for category in get_ordered_legend_categories(categories):
        canonical = canonical_ticket_category(category)
        if canonical in named_category_colors:
            color_map[category] = named_category_colors[canonical]
            continue

        color_map[category] = palette[palette_index % len(palette)]
        palette_index += 1

    return color_map


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
DEFAULT_SESSION_DATE = "Session Date"
DEFAULT_SESSION_TIME = "Session Time"

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
session_date_col = DEFAULT_SESSION_DATE if DEFAULT_SESSION_DATE in all_columns else next(
    (c for c in all_columns if "session" in c.lower() and "date" in c.lower()), None
)
session_time_col = DEFAULT_SESSION_TIME if DEFAULT_SESSION_TIME in all_columns else next(
    (c for c in all_columns if "session" in c.lower() and "time" in c.lower()), None
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
    session_date_col=session_date_col,
    session_time_col=session_time_col,
)

try:
    prepared_df = prepare_data(raw_df, columns)
except Exception as exc:
    st.error(str(exc))
    st.stop()

st.subheader("Marketing Response Trend")
exclude_box_office_marketing = st.checkbox(
    "Exclude box office (marketing response only)",
    value=False,
    key="exclude_box_office_marketing",
)
marketing_df = prepared_df
if exclude_box_office_marketing:
    marketing_df = marketing_df[~marketing_df["source"].str.contains("BO", case=True, na=False)]

source_series = get_source_series(marketing_df, mode=mode_label, time_group=time_group)
y_title = "Tickets" if mode_label == "tickets" else "Bookings"

other_mask = source_series["source"].str.lower().str.startswith("other")
non_other_series = source_series[~other_mask]
other_series = source_series[other_mask]

bo_mask = other_series["source"].str.contains(
    r"\bbo\b|season ticket|life member", case=False, regex=True, na=False
)
bo_series = other_series[bo_mask]
rest_other_series = other_series[~bo_mask]

bo_collapsed = bo_series.groupby("period", as_index=False)["value"].sum()
bo_collapsed["source"] = "Box Office"
other_collapsed = rest_other_series.groupby("period", as_index=False)["value"].sum()
other_collapsed["source"] = "Other"
chartable_series = pd.concat(
    [
        non_other_series,
        bo_collapsed[["period", "source", "value"]],
        other_collapsed[["period", "source", "value"]],
    ],
    ignore_index=True,
)

all_sources = sorted(chartable_series["source"].unique().tolist())
selected_sources = checkbox_filter(
    all_sources,
    "source_filter",
    "Tick responses to include",
    default_unchecked={"Unknown"},
)
filtered_source = chartable_series[chartable_series["source"].isin(selected_sources)]

chart_type_source = st.radio(
    "Chart type",
    options=["Line", "Stacked columns"],
    index=1,
    horizontal=True,
    key="chart_type_source",
)

if filtered_source.empty:
    st.info("No data points for selected responses.")
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
    add_monday_guides(fig_source, filtered_source["period"])
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
    add_monday_guides(fig_source, filtered_source["period"])
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
session_ticket_series = get_session_ticket_type_breakdown(prepared_df)
all_pie_categories = prepared_df["ticket_type"].dropna().astype(str).tolist() + [
    "House seats",
    "Unsold",
]
pie_color_map = build_pie_color_map(all_pie_categories)
legend_categories = get_ordered_legend_categories(all_pie_categories)

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
    ticket_breakdown["ticket_type"] = ticket_breakdown["ticket_type"].astype(str)
    ordered_ticket_types = get_ordered_legend_categories(ticket_breakdown["ticket_type"].tolist())
    ticket_breakdown["ticket_type"] = pd.Categorical(
        ticket_breakdown["ticket_type"],
        categories=ordered_ticket_types,
        ordered=True,
    )
    ticket_breakdown = ticket_breakdown.sort_values("ticket_type").reset_index(drop=True)
    ticket_breakdown["ticket_type"] = ticket_breakdown["ticket_type"].astype(str)
    ticket_total = ticket_breakdown["value"].sum()
    ticket_labels = [
        f"{ticket_type}: {(value / ticket_total):.0%}"
        if ticket_total > 0 and (value / ticket_total) > 0.10
        else ""
        for ticket_type, value in zip(ticket_breakdown["ticket_type"], ticket_breakdown["value"])
    ]
    fig_ticket = px.pie(
        ticket_breakdown,
        names="ticket_type",
        values="value",
        color="ticket_type",
        color_discrete_map=pie_color_map,
        title="<b>Ticket type share</b>",
        hole=0.35,
    )
    fig_ticket.update_traces(
        textposition="outside",
        text=ticket_labels,
        textinfo="text",
        pull=0.02,
        sort=False,
        direction="clockwise",
        rotation=0,
    )
    fig_ticket.update_layout(
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        legend_title_text="Ticket Type",
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.12,
            yanchor="bottom",
            entrywidthmode="fraction",
            entrywidth=0.33,
        ),
        margin=dict(t=120, b=10, l=10, r=10),
        height=650,
    )
    st.plotly_chart(fig_ticket, width="stretch")

st.subheader("Session Sales by Ticket Type")
SESSION_CAPACITY = 438
HOUSE_SEATS = 22
SESSION_ROW_SPACING_PX = 60

if session_ticket_series.empty:
    st.info("No session-level data found. Add 'Session Date' and 'Session Time' columns to view per-session pies.")
else:
    session_groups = list(session_ticket_series.groupby("session_datetime", sort=True))
    sessions_count = len(session_groups)
    pie_cols = min(2, sessions_count)
    pie_rows = math.ceil(sessions_count / pie_cols)
    session_fig_height = max(560, pie_rows * 500)
    session_plot_height = max(session_fig_height - 160, 200)
    session_vertical_spacing = min(SESSION_ROW_SPACING_PX / session_plot_height, 0.2)
    subplot_titles = []
    for session_dt, session_data in session_groups:
        sold_count = int(session_data["value"].sum())
        allocated_count = sold_count + HOUSE_SEATS
        filled_pct = (allocated_count / SESSION_CAPACITY) * 100 if SESSION_CAPACITY else 0
        session_label = pd.to_datetime(session_dt).strftime("%a %d %b %Y, %I:%M %p")
        subplot_titles.append(f"<b>{session_label} | Filled {filled_pct:.0f}%</b>")

    session_fig = make_subplots(
        rows=pie_rows,
        cols=pie_cols,
        specs=[[{"type": "domain"} for _ in range(pie_cols)] for _ in range(pie_rows)],
        subplot_titles=subplot_titles,
        vertical_spacing=session_vertical_spacing,
    )

    summary_rows: list[dict[str, int | str]] = []

    for idx, (session_dt, session_data) in enumerate(session_groups):
        sold_count = int(session_data["value"].sum())
        used_seats = sold_count + HOUSE_SEATS
        unsold_count = max(SESSION_CAPACITY - used_seats, 0)

        chart_rows = [
            {"ticket_type": row.ticket_type, "value": int(row.value)}
            for row in session_data.itertuples(index=False)
            if int(row.value) > 0
        ]
        chart_rows.append({"ticket_type": "House seats", "value": HOUSE_SEATS})
        if unsold_count > 0:
            chart_rows.append({"ticket_type": "Unsold", "value": unsold_count})

        pie_df = pd.DataFrame(chart_rows)
        pie_df["ticket_type"] = pie_df["ticket_type"].astype(str)
        pie_df["value"] = pie_df["value"].astype(int)
        pie_df["ticket_type"] = pd.Categorical(
            pie_df["ticket_type"],
            categories=legend_categories,
            ordered=True,
        )
        pie_df = pie_df.sort_values("ticket_type").reset_index(drop=True)
        pie_df["ticket_type"] = pie_df["ticket_type"].astype(str)
        total_value = pie_df["value"].sum()
        label_text = [
            f"{ticket_type}: {(value / total_value):.0%}"
            if total_value > 0 and (value / total_value) > 0.10
            else ""
            for ticket_type, value in zip(pie_df["ticket_type"], pie_df["value"])
        ]

        session_label = pd.to_datetime(session_dt).strftime("%a %d %b %Y, %I:%M %p")
        row = idx // pie_cols + 1
        col = idx % pie_cols + 1

        session_fig.add_trace(
            go.Pie(
                labels=pie_df["ticket_type"],
                values=pie_df["value"],
                marker={"colors": [pie_color_map.get(label, "#808080") for label in pie_df["ticket_type"]]},
                hole=0.35,
                text=label_text,
                textinfo="text",
                textposition="outside",
                pull=0.015,
                showlegend=False,
                sort=False,
                direction="clockwise",
                rotation=0,
                name=session_label,
            ),
            row=row,
            col=col,
        )

        summary_rows.append(
            {
                "Session": session_label,
                "Sold": sold_count,
                "House seats": HOUSE_SEATS,
                "Capacity": SESSION_CAPACITY,
            }
        )

    session_fig.update_layout(
        title_text="<b>Session seat mix</b>",
        legend_title_text="Seat Category",
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.12,
            yanchor="bottom",
            entrywidthmode="fraction",
            entrywidth=0.33,
        ),
        margin=dict(t=120, b=10, l=10, r=10),
        height=session_fig_height,
    )

    for category in legend_categories:
        session_fig.add_trace(
            go.Bar(
                x=[None],
                y=[None],
                name=category,
                marker_color=pie_color_map.get(category, "#808080"),
                showlegend=True,
                visible="legendonly",
                hoverinfo="skip",
            )
        )

    session_fig.update_xaxes(visible=False, showgrid=False, zeroline=False)
    session_fig.update_yaxes(visible=False, showgrid=False, zeroline=False)

    st.plotly_chart(session_fig, width="stretch")
    st.dataframe(pd.DataFrame(summary_rows), width="stretch")

with st.expander("Preview prepared data"):
    st.dataframe(prepared_df.head(100), width="stretch")

st.subheader("Postcode Hotspot Map")
_POSTCODE_LOOKUP = Path(__file__).parent / "sample_data" / "brisbane_postcodes.csv"

@st.cache_data(show_spinner=False)
def load_postcode_lookup() -> pd.DataFrame:
    return pd.read_csv(_POSTCODE_LOOKUP, dtype={"postcode": str})

exclude_box_office_postcode = st.checkbox(
    "Exclude box office (postcode map only)",
    value=False,
    key="exclude_box_office_postcode",
)
postcode_df = prepared_df
if exclude_box_office_postcode:
    postcode_df = postcode_df[~postcode_df["source"].str.contains("BO", case=True, na=False)]

postcode_series = get_postcode_series(postcode_df)
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

st.divider()
with st.expander("Tutorial: How this dashboard works", expanded=False):
    st.markdown(
        """
### 1. Libraries and responsibilities
- **Streamlit** builds the interface: sidebar filters, charts, tables, and page layout.
- **Pandas** transforms CSV rows into analysis-ready data.
- **Plotly Express** builds high-level charts quickly (bar, line, pie, map setup).
- **Plotly Graph Objects** provides low-level control for map bubble styling (halo + labels).

### 2. Core flow
1. Load CSV (uploaded file or default sample file).
2. Detect key columns (date/time/source/tickets/ticket type/postcode).
3. Prepare data with standardized fields.
4. Build chart-specific aggregated datasets.
5. Render visualizations and apply interactive filters.
"""
    )

    st.markdown("**Main imports and setup (app.py)**")
    st.code(get_code_snippet(ROOT_DIR / "app.py", 1, 22), language="python")

    st.markdown("**Data preparation model (src/analytics.py)**")
    st.code(get_code_snippet(ANALYTICS_FILE, 7, 27), language="python")

    st.markdown("**Where raw data becomes standardized (src/analytics.py)**")
    st.code(get_code_snippet(ANALYTICS_FILE, 80, 143), language="python")

    st.markdown("**Marketing response visualization section (app.py)**")
    st.code(get_code_snippet(ROOT_DIR / "app.py", 144, 205), language="python")

    st.markdown("**Ticket type pie chart section (app.py)**")
    st.code(get_code_snippet(ROOT_DIR / "app.py", 218, 246), language="python")

    st.markdown("**Postcode hotspot map section (app.py)**")
    st.code(get_code_snippet(ROOT_DIR / "app.py", 254, 334), language="python")
