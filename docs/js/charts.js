// Chart rendering (Plotly.js) for the Marketing Statistics Visualizer.

// Formats a local wall-clock Date as a naive "YYYY-MM-DDTHH:mm:ss" string
// (no 'Z'/timezone) so Plotly renders the literal booking time as recorded,
// rather than toISOString()'s UTC conversion shifting it by the visitor's
// timezone offset (and potentially rolling bookings near midnight onto the
// wrong calendar day).
function fmtDate(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function mondayGuideShapes(periods) {
  if (!periods.length) return [];
  const min = new Date(Math.min(...periods.map((p) => p.getTime())));
  const max = new Date(Math.max(...periods.map((p) => p.getTime())));
  const firstDay = new Date(min.getFullYear(), min.getMonth(), min.getDate());
  const daysToMonday = (7 - firstDay.getDay() + 1) % 7; // matches pandas W-MON anchoring
  const firstMonday = new Date(firstDay);
  firstMonday.setDate(firstDay.getDate() + daysToMonday);

  const shapes = [];
  for (let d = new Date(firstMonday); d <= max; d.setDate(d.getDate() + 7)) {
    shapes.push({
      type: 'line',
      xref: 'x', yref: 'paper',
      x0: fmtDate(d), x1: fmtDate(d),
      y0: 0, y1: 1,
      line: { width: 1, dash: 'dot', color: 'rgba(90,90,90,0.45)' },
    });
  }
  return shapes;
}

function groupBySource(series) {
  const bySource = new Map();
  for (const row of series) {
    if (!bySource.has(row.source)) bySource.set(row.source, []);
    bySource.get(row.source).push(row);
  }
  return bySource;
}

function renderTrendChart(divId, filteredSeries, { chartType, yTitle, modeLabel }) {
  const el = document.getElementById(divId);
  if (!filteredSeries.length) {
    Plotly.purge(el);
    el.innerHTML = '<p class="empty-note">No data points for selected responses.</p>';
    return;
  }
  el.innerHTML = '';

  const bySource = groupBySource(filteredSeries);
  const sources = Array.from(bySource.keys()).sort((a, b) => a.localeCompare(b));
  const colorMap = window.Categories.assignTrendColors(sources);

  const traces = sources.map((source) => {
    const rows = bySource.get(source).slice().sort((a, b) => a.period - b.period);
    return {
      x: rows.map((r) => fmtDate(r.period)),
      y: rows.map((r) => r.value),
      name: source,
      type: chartType === 'bar' ? 'bar' : 'scatter',
      mode: chartType === 'bar' ? undefined : 'lines+markers',
      marker: { color: colorMap[source] },
      line: chartType === 'bar' ? undefined : { color: colorMap[source] },
    };
  });

  const layout = {
    title: { text: `Marketing response over time (${modeLabel})` },
    barmode: chartType === 'bar' ? 'stack' : undefined,
    legend: { title: { text: 'Response' } },
    xaxis: {
      title: { text: 'Date/Time' },
      showgrid: true, gridwidth: 1, gridcolor: 'rgba(200,200,200,0.4)',
      dtick: 86400000,
    },
    yaxis: { title: { text: yTitle } },
    shapes: mondayGuideShapes(filteredSeries.map((r) => r.period)),
    margin: { t: 60, b: 60, l: 60, r: 20 },
    height: 480,
  };

  Plotly.newPlot(el, traces, layout, { responsive: true, displaylogo: false });
}

function renderOtherTable(divId, otherSeriesDetailed, yTitle) {
  const el = document.getElementById(divId);
  if (!otherSeriesDetailed.length) {
    el.innerHTML = '<p class="empty-note">No \'Other\' responses in the data.</p>';
    return;
  }
  const totals = new Map();
  for (const row of otherSeriesDetailed) {
    totals.set(row.source, (totals.get(row.source) || 0) + row.value);
  }
  const rows = Array.from(totals.entries()).sort((a, b) => b[1] - a[1]);

  let html = `<table class="data-table"><thead><tr><th>#</th><th>Response</th><th>${yTitle}</th></tr></thead><tbody>`;
  rows.forEach(([source, value], idx) => {
    html += `<tr><td>${idx + 1}</td><td>${escapeHtml(source)}</td><td>${value}</td></tr>`;
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function renderTicketPie(divId, ticketBreakdown, colorMap) {
  const el = document.getElementById(divId);
  if (!ticketBreakdown.length) {
    Plotly.purge(el);
    el.innerHTML = '<p class="empty-note">No data points for selected ticket types.</p>';
    return;
  }
  el.innerHTML = '';

  const ordered = window.Categories.getOrderedLegendCategories(ticketBreakdown.map((r) => r.ticketType));
  const byType = new Map(ticketBreakdown.map((r) => [r.ticketType, r.value]));
  const labels = ordered.filter((t) => byType.has(t));
  const values = labels.map((t) => byType.get(t));
  const total = values.reduce((a, b) => a + b, 0);
  const text = labels.map((label, i) => (total > 0 && values[i] / total > 0.10 ? `${label}: ${Math.round((values[i] / total) * 100)}%` : ''));

  const trace = {
    type: 'pie',
    labels, values, text,
    textinfo: 'text',
    textposition: 'outside',
    hole: 0.35,
    pull: 0.02,
    sort: false,
    direction: 'clockwise',
    rotation: 0,
    marker: { colors: labels.map((l) => colorMap[l] || '#808080') },
  };

  const layout = {
    title: { text: 'Ticket type share' },
    legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: 1.12, yanchor: 'bottom', title: { text: 'Ticket Type' } },
    margin: { t: 120, b: 10, l: 10, r: 10 },
    height: 650,
  };

  Plotly.newPlot(el, [trace], layout, { responsive: true, displaylogo: false });
}

const SESSION_CAPACITY = 438;
const HOUSE_SEATS = 22;

function sessionLabel(date) {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const h24 = date.getHours();
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
  const ampm = h24 < 12 ? 'AM' : 'PM';
  const mm = String(date.getMinutes()).padStart(2, '0');
  return `${days[date.getDay()]} ${String(date.getDate()).padStart(2, '0')} ${months[date.getMonth()]} ${date.getFullYear()}, ${h12}:${mm} ${ampm}`;
}

function renderSessionPies(divId, sessionSeries, colorMap, legendCategories) {
  const el = document.getElementById(divId);
  if (!sessionSeries.length) {
    Plotly.purge(el);
    el.innerHTML = "<p class=\"empty-note\">No session-level data found. Add 'Session Date' and 'Session Time' columns to view per-session pies.</p>";
    return null;
  }
  el.innerHTML = '';

  const bySession = new Map();
  for (const row of sessionSeries) {
    const key = row.sessionDatetime.getTime();
    if (!bySession.has(key)) bySession.set(key, { sessionDatetime: row.sessionDatetime, rows: [] });
    bySession.get(key).rows.push(row);
  }
  const sessions = Array.from(bySession.values()).sort((a, b) => a.sessionDatetime - b.sessionDatetime);

  const cols = Math.min(2, sessions.length);
  const rows = Math.ceil(sessions.length / cols);
  const rowGap = 0.08;
  const colGap = 0.06;
  const rowHeight = (1 - rowGap * (rows - 1)) / rows;
  const colWidth = (1 - colGap * (cols - 1)) / cols;

  const traces = [];
  const annotations = [];
  const summaryRows = [];

  sessions.forEach((session, idx) => {
    const soldCount = session.rows.reduce((sum, r) => sum + r.value, 0);
    const usedSeats = soldCount + HOUSE_SEATS;
    const unsoldCount = Math.max(SESSION_CAPACITY - usedSeats, 0);

    const chartRows = session.rows.filter((r) => r.value > 0).map((r) => ({ ticketType: r.ticketType, value: r.value }));
    chartRows.push({ ticketType: 'House seats', value: HOUSE_SEATS });
    if (unsoldCount > 0) chartRows.push({ ticketType: 'Unsold', value: unsoldCount });

    const ordered = legendCategories.filter((cat) => chartRows.some((c) => c.ticketType === cat));
    const byType = new Map(chartRows.map((c) => [c.ticketType, c.value]));
    const labels = ordered;
    const values = labels.map((l) => byType.get(l));
    const total = values.reduce((a, b) => a + b, 0);
    const text = labels.map((l, i) => (total > 0 && values[i] / total > 0.10 ? `${l}: ${Math.round((values[i] / total) * 100)}%` : ''));

    const row = Math.floor(idx / cols);
    const col = idx % cols;
    const xStart = col * (colWidth + colGap);
    const yEnd = 1 - row * (rowHeight + rowGap);
    const yStart = yEnd - rowHeight;

    const allocatedPct = Math.round((usedSeats / SESSION_CAPACITY) * 100);

    traces.push({
      type: 'pie',
      labels, values, text,
      textinfo: 'text',
      textposition: 'outside',
      hole: 0.35,
      pull: 0.015,
      sort: false,
      direction: 'clockwise',
      rotation: 0,
      showlegend: false,
      marker: { colors: labels.map((l) => colorMap[l] || '#808080') },
      domain: { x: [xStart, xStart + colWidth], y: [yStart, yEnd] },
      name: sessionLabel(session.sessionDatetime),
    });

    annotations.push({
      text: `<b>${sessionLabel(session.sessionDatetime)} | Filled ${allocatedPct}%</b>`,
      showarrow: false,
      x: xStart + colWidth / 2, y: yEnd + 0.03,
      xref: 'paper', yref: 'paper',
      xanchor: 'center', yanchor: 'bottom',
      font: { size: 13 },
    });

    summaryRows.push({ session: sessionLabel(session.sessionDatetime), sold: soldCount, houseSeats: HOUSE_SEATS, capacity: SESSION_CAPACITY });
  });

  // Shared legend via invisible dummy bar traces (mirrors the Python legendonly trick).
  for (const category of legendCategories) {
    traces.push({
      type: 'bar', x: [null], y: [null],
      name: category,
      marker: { color: colorMap[category] || '#808080' },
      showlegend: true,
      visible: 'legendonly',
      hoverinfo: 'skip',
    });
  }

  const layout = {
    title: { text: 'Session seat mix' },
    annotations,
    legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: 1.08, yanchor: 'bottom', title: { text: 'Seat Category' } },
    margin: { t: 100, b: 10, l: 10, r: 10 },
    height: Math.max(560, rows * 480),
    xaxis: { visible: false }, yaxis: { visible: false },
  };

  Plotly.newPlot(el, traces, layout, { responsive: true, displaylogo: false });
  return summaryRows;
}

function renderSessionSummaryTable(divId, summaryRows) {
  const el = document.getElementById(divId);
  if (!summaryRows || !summaryRows.length) {
    el.innerHTML = '';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>Session</th><th>Sold</th><th>House seats</th><th>Capacity</th></tr></thead><tbody>';
  for (const r of summaryRows) {
    html += `<tr><td>${escapeHtml(r.session)}</td><td>${r.sold}</td><td>${r.houseSeats}</td><td>${r.capacity}</td></tr>`;
  }
  html += '</tbody></table>';
  el.innerHTML = html;
}

function renderPostcodeMap(divId, mapRows, mapStyle) {
  const el = document.getElementById(divId);
  if (!mapRows.length) {
    Plotly.purge(el);
    el.innerHTML = '<p class="empty-note">No postcode data available (or no postcodes matched the Brisbane lookup table).</p>';
    return;
  }
  el.innerHTML = '';

  const tickets = mapRows.map((r) => r.tickets);
  const minT = Math.min(...tickets);
  const maxT = Math.max(...tickets);
  const minSize = 12, maxSize = 50;
  const bubbleSize = mapRows.map((r) => (maxT === minT ? minSize : minSize + ((r.tickets - minT) * (maxSize - minSize)) / (maxT - minT)));
  const haloSize = bubbleSize.map((s) => s + 2);

  const haloTrace = {
    type: 'scattermap',
    lat: mapRows.map((r) => r.lat), lon: mapRows.map((r) => r.lon),
    mode: 'markers',
    marker: { size: haloSize, color: '#888888', opacity: 0.9 },
    hoverinfo: 'skip', showlegend: false,
  };
  const mainTrace = {
    type: 'scattermap',
    lat: mapRows.map((r) => r.lat), lon: mapRows.map((r) => r.lon),
    mode: 'markers+text',
    marker: { size: bubbleSize, color: '#1f77b4', opacity: 0.75 },
    text: mapRows.map((r) => String(r.tickets)),
    textposition: 'middle center',
    textfont: { color: 'white', size: 11 },
    customdata: mapRows.map((r) => [r.suburb, r.postcode, r.tickets]),
    hovertemplate: '%{customdata[0]}<br>Postcode: %{customdata[1]}<br>Tickets: %{customdata[2]}<extra></extra>',
    showlegend: false,
  };

  const layout = {
    title: { text: 'Tickets sold by postcode' },
    map: {
      style: mapStyle,
      center: { lat: -27.47, lon: 153.02 },
      zoom: 9,
    },
    width: 800, height: 800,
    margin: { t: 60, b: 10, l: 10, r: 10 },
  };

  Plotly.newPlot(el, [haloTrace, mainTrace], layout, { responsive: true, displaylogo: false });
}

function renderPreviewTable(divId, prepared) {
  const el = document.getElementById(divId);
  const rows = prepared.slice(0, 100);
  if (!rows.length) {
    el.innerHTML = '<p class="empty-note">No prepared rows.</p>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>Booking datetime</th><th>Session datetime</th><th>Source</th><th>Ticket count</th><th>Ticket type</th><th>Postcode</th></tr></thead><tbody>';
  for (const r of rows) {
    html += `<tr><td>${r.bookingDatetime.toLocaleString()}</td><td>${r.sessionDatetime ? r.sessionDatetime.toLocaleString() : ''}</td><td>${escapeHtml(r.source)}</td><td>${r.ticketCount}</td><td>${escapeHtml(r.ticketType)}</td><td>${r.postcode || ''}</td></tr>`;
  }
  html += '</tbody></table>';
  el.innerHTML = html;
}

window.Charts = {
  renderTrendChart,
  renderOtherTable,
  renderTicketPie,
  renderSessionPies,
  renderSessionSummaryTable,
  renderPostcodeMap,
  renderPreviewTable,
};
