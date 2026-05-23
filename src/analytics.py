from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ColumnConfig:
    date_col: str
    time_col: str
    source_col: str
    other_specify_col: str | None = None
    number_of_tickets_col: str | None = None
    ticket_type_col: str | None = None
    postcode_col: str | None = None


def normalize_source(value: object, other_specify: object | None) -> str:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return "Unknown"

    lowered = text.lower()
    if lowered.startswith("other"):
        custom = ""
        if other_specify is not None:
            custom = str(other_specify).strip()
            if custom.lower() in {"nan", "none"}:
                custom = ""
        if custom:
            return f"Other: {custom}"

        parts = text.split(":", 1)
        inline_custom = parts[1].strip() if len(parts) > 1 else ""
        return f"Other: {inline_custom}" if inline_custom else "Other"

    return text


def normalize_sources(value: object, other_specify: object | None) -> list[str]:
    text = str(value).strip()
    parts = [part.strip() for part in text.split(";") if part.strip()]

    if not parts:
        return [normalize_source(value, other_specify)]

    normalized: list[str] = []
    for part in parts:
        use_other_specify = other_specify if part.lower().startswith("other") else None
        normalized.append(normalize_source(part, use_other_specify))

    return normalized


def _coerce_ticket_count(value: object) -> int:
    if value is None:
        return 1

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return 1

    try:
        count = int(float(text))
    except ValueError:
        return 1

    return max(count, 1)


def normalize_ticket_type(value: object) -> str:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return "Unknown"

    normalized_key = "".join(ch for ch in text.lower() if ch.isalnum())
    if normalized_key in {"groupboxoffice", "group10"}:
        return "Group"

    return text


def prepare_data(df: pd.DataFrame, columns: ColumnConfig) -> pd.DataFrame:
    required = [columns.date_col, columns.time_col, columns.source_col]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    working = df.copy()
    working = working.rename(columns={columns.source_col: "source"})

    date_part = working[columns.date_col].astype(str).str.strip()
    time_part = working[columns.time_col].astype(str).str.strip()
    working["booking_datetime"] = pd.to_datetime(
        date_part + " " + time_part,
        errors="coerce",
        dayfirst=True,
    )
    working = working.dropna(subset=["booking_datetime"])

    if columns.other_specify_col and columns.other_specify_col in working.columns:
        working["source"] = working.apply(
            lambda row: normalize_sources(row["source"], row[columns.other_specify_col]),
            axis=1,
        )
    else:
        working["source"] = working["source"].map(lambda value: normalize_sources(value, None))

    working = working.explode("source", ignore_index=True)

    if columns.number_of_tickets_col and columns.number_of_tickets_col in working.columns:
        working["ticket_count"] = working[columns.number_of_tickets_col].map(_coerce_ticket_count)
    else:
        working["ticket_count"] = 1

    if columns.ticket_type_col and columns.ticket_type_col in working.columns:
        working = working.rename(columns={columns.ticket_type_col: "ticket_type"})
    else:
        working["ticket_type"] = "Unknown"

    working["ticket_type"] = working["ticket_type"].map(normalize_ticket_type)

    if columns.postcode_col and columns.postcode_col in working.columns:
        working["postcode"] = (
            working[columns.postcode_col]
            .astype(str)
            .str.strip()
            .str.extract(r"(\d{4})", expand=False)
        )
    else:
        working["postcode"] = None

    return working.sort_values("booking_datetime").reset_index(drop=True)


def get_source_series(
    prepared_df: pd.DataFrame,
    *,
    mode: str,
    time_group: str,
) -> pd.DataFrame:
    if mode not in {"tickets", "bookings"}:
        raise ValueError("mode must be 'tickets' or 'bookings'")

    data = prepared_df.copy()

    if mode == "bookings":
        data = data.drop_duplicates(subset=["booking_datetime", "source"]).copy()
        data["value"] = 1
    else:
        data["value"] = data["ticket_count"]

    data["period"] = data["booking_datetime"].dt.to_period(time_group).dt.to_timestamp()

    series = data.groupby(["period", "source"], as_index=False)["value"].sum().sort_values("period")

    return series


def get_postcode_series(prepared_df: pd.DataFrame) -> pd.DataFrame:
    data = prepared_df.dropna(subset=["postcode"]).copy()
    data = data[data["postcode"] != ""]
    series = (
        data.groupby("postcode", as_index=False)["ticket_count"]
        .sum()
        .rename(columns={"ticket_count": "tickets"})
    )
    return series


def get_ticket_type_series(prepared_df: pd.DataFrame, *, time_group: str) -> pd.DataFrame:
    data = prepared_df.copy()
    data["period"] = data["booking_datetime"].dt.to_period(time_group).dt.to_timestamp()

    series = (
        data.groupby(["period", "ticket_type"], as_index=False)["ticket_count"]
        .sum()
        .rename(columns={"ticket_count": "value"})
        .sort_values("period")
    )

    return series
