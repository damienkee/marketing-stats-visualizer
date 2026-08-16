# Marketing Stats Visualizer

A local web app for analyzing and visualizing show marketing statistics from CSV files.

## Web version (GitHub Pages, no install)

The `docs/` folder is a self-contained static rewrite of this app — plain HTML/CSS/JS, no Python, no server. It's a straight port of the same logic in `src/analytics.py` / `app.py` (see `docs/js/analytics.js`, `docs/js/categories.js`), verified to produce identical results against the Python version.

**Your data never leaves your browser.** There's no backend for a static site to send it to — choosing a CSV file reads and parses it entirely client-side (via the File API + a vendored copy of PapaParse) and nothing is ever transmitted anywhere. Charts are drawn with a vendored copy of Plotly.js. Both libraries are committed under `docs/vendor/` rather than loaded from a CDN, so the page works fully offline once loaded and never makes an external network request at all.

### Enable it on GitHub Pages

1. Push this repo to GitHub (see "GitHub sync" below if you haven't already).
2. On GitHub: **Settings → Pages → Build and deployment → Source: Deploy from a branch**.
3. Branch: `main`, folder: `/docs`. Save.
4. GitHub gives you a URL like `https://<your-username>.github.io/marketing-stats-visualizer/` — open it, then use the "Upload CSV" control in the sidebar to load your own file. Without a file it falls back to the bundled sample data.

### Try it locally first

Opening `docs/index.html` directly via `file://` will hit browser restrictions on `fetch()` for local files (used to load the sample CSV/postcode lookup). Serve it over a local HTTP server instead, e.g.:

```bash
cd docs
python -m http.server 8000
```

then open `http://localhost:8000`.

### Relationship to the Python/Streamlit app

The original Python app (`app.py`, root of this repo) still works as before and hasn't been removed — the two are independent. Let me know if you'd like the Python version retired once you've confirmed the web version covers what you need.

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

## Run like an app on Windows (no VS Code needed)

You can now launch this project directly from File Explorer:

1. One-time setup:

```bash
pip install -r requirements.txt
```

2. Start app (visible terminal):

- Double-click `run_app.bat`

3. Start app (hidden terminal):

- Double-click `run_app_hidden.vbs`

4. Stop app:

- Double-click `stop_app.bat`

Tip:

- You can right-click `run_app.bat` or `run_app_hidden.vbs` and create a desktop shortcut.
- After that, launching from the shortcut feels like a normal app.

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
