# Marketing Stats Visualizer

A local web app for analyzing and visualizing show marketing statistics from CSV files.

## What this app does

- Reads a local CSV (upload or default sample file).
- Combines separate booking date and booking time columns into one datetime x-axis.
- Plots marketing responses over time as a line chart.
- Lets you turn each marketing response on/off using checkboxes.
- Lets you switch between:
  - `tickets` mode: sum `Number Of Tickets`.
  - `bookings` mode: count each unique booking datetime as one booking.
- Plots a separate line chart of ticket types sold over time.
- Builds separate pie charts per session (using `Session Date` + `Session Time`) showing sold ticket types, fixed house seats, and unsold seats up to capacity.

## CSV expectations

Expected CSV headings:

- `Number Of Tickets`
- `Date Booked (UTC+10)`
- `Time Booked`
- `Booking Data: How Did You Find Out About Our Show?`
- `Booking Data: Sub 1: Please Specify`
- `Booking Data: What Is Your Postcode`
- `Ticket Type`

Optional (for per-session sales pies):

- `Session Date`
- `Session Time`

Per-session pie assumptions:

- Total capacity is fixed at `438`.
- `House seats` are fixed at `22` for every session.
- `Unsold` is calculated as `438 - (sold tickets + 22)`.

Example CSV:

Use the included `sample_data/bookings_sample.csv` as a formatting reference.

Note on "Other":

- Values like `Other: billboard near station` are normalized and shown as their own response series.

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
streamlit run app.py
```

4. Open the local URL shown by Streamlit (usually `http://localhost:8501`).

## GitHub sync

If you want this as its own GitHub repository:

1. Open a terminal in this folder.
2. Run:

```bash
git init
git add .
git commit -m "Initial marketing stats visualizer"
```

3. Create an empty repository on GitHub, then run:

```bash
git remote add origin https://github.com/<your-username>/marketing-stats-visualizer.git
git branch -M main
git push -u origin main
```

This app is designed to be a separate project repository.
