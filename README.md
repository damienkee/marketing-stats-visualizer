# Marketing Stats Visualizer

A local web app for analyzing and visualizing show marketing statistics from CSV files.
https://damienkee.github.io/marketing-stats-visualizer/

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

