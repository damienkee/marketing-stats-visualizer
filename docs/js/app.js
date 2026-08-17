// Orchestration: CSV loading, column detection, control wiring, render pipeline.
// Nothing here ever sends data anywhere — CSV parsing and all analysis run
// entirely in this browser tab.

const DEFAULT_COLUMN_NAMES = {
  numberOfTickets: 'Number Of Tickets',
  date: 'Date Booked (UTC+10)',
  time: 'Time Booked',
  source: 'Booking Data: How Did You Find Out About Our Show?',
  otherSpecify: 'Booking Data: Sub 1: Please Specify',
  ticketType: 'Ticket Type',
  postcode: 'Booking Data: What Is Your Postcode',
  sessionDate: 'Session Date',
  sessionTime: 'Session Time',
};

const state = {
  rawRows: null,
  allColumns: [],
  columns: null,
  prepared: null,
  postcodeLookup: null,
  sourceSelections: new Map(),
  ticketTypeSelections: new Map(),
};

function detectColumns(allColumns) {
  const lower = allColumns.map((c) => c.toLowerCase());
  const findBy = (predicate) => {
    const idx = lower.findIndex(predicate);
    return idx >= 0 ? allColumns[idx] : null;
  };
  const exactOr = (defaultName, predicate, fallbackToFirst = false) => {
    if (allColumns.includes(defaultName)) return defaultName;
    const found = findBy(predicate);
    if (found) return found;
    return fallbackToFirst ? allColumns[0] : null;
  };

  return {
    dateCol: exactOr(DEFAULT_COLUMN_NAMES.date, (c) => c.includes('date'), true),
    timeCol: exactOr(DEFAULT_COLUMN_NAMES.time, (c) => c.includes('time'), true),
    sourceCol: exactOr(
      DEFAULT_COLUMN_NAMES.source,
      (c) => c.includes('find') || c.includes('source') || c.includes('hear'),
      true
    ),
    otherSpecifyCol: allColumns.includes(DEFAULT_COLUMN_NAMES.otherSpecify) ? DEFAULT_COLUMN_NAMES.otherSpecify : null,
    numberOfTicketsCol: allColumns.includes(DEFAULT_COLUMN_NAMES.numberOfTickets) ? DEFAULT_COLUMN_NAMES.numberOfTickets : null,
    ticketTypeCol: exactOr(DEFAULT_COLUMN_NAMES.ticketType, (c) => c.includes('ticket') || c.includes('type')),
    postcodeCol: exactOr(DEFAULT_COLUMN_NAMES.postcode, (c) => c.includes('postcode')),
    sessionDateCol: exactOr(DEFAULT_COLUMN_NAMES.sessionDate, (c) => c.includes('session') && c.includes('date')),
    sessionTimeCol: exactOr(DEFAULT_COLUMN_NAMES.sessionTime, (c) => c.includes('session') && c.includes('time')),
  };
}

function showError(message) {
  const el = document.getElementById('error-banner');
  if (!message) {
    el.hidden = true;
    el.textContent = '';
    return;
  }
  el.hidden = false;
  el.textContent = message;
}

function parseCsvText(text) {
  const stripped = text.replace(/^﻿/, '');
  const result = Papa.parse(stripped, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h) => h.trim(),
  });
  return result.data;
}

function loadFromRows(rows, sourceLabel) {
  showError(null);
  if (!rows.length) {
    showError('The CSV file is empty.');
    return;
  }
  state.rawRows = rows;
  state.allColumns = Object.keys(rows[0]).map((c) => c.trim()).filter((c) => c.length > 0);
  state.columns = detectColumns(state.allColumns);

  try {
    state.prepared = Analytics.prepareData(state.rawRows, state.columns);
  } catch (err) {
    showError(err.message);
    state.prepared = null;
    return;
  }

  document.getElementById('data-source-note').textContent = `${sourceLabel} — ${state.prepared.length} prepared rows`;
  state.sourceSelections.clear();
  state.ticketTypeSelections.clear();
  renderAll();
}

function loadDefaultSample() {
  fetch('data/sample_data.csv')
    .then((res) => res.text())
    .then((text) => loadFromRows(parseCsvText(text), 'Using bundled sample file'))
    .catch((err) => showError(`Could not load sample data: ${err.message}`));
}

function loadPostcodeLookup() {
  return fetch('data/brisbane_postcodes.csv')
    .then((res) => res.text())
    .then((text) => {
      const rows = parseCsvText(text);
      state.postcodeLookup = new Map(
        rows.map((r) => [String(r.postcode).trim(), { suburb: r.suburb, lat: parseFloat(r.lat), lon: parseFloat(r.lon) }])
      );
    })
    .catch((err) => showError(`Could not load postcode lookup: ${err.message}`));
}

function containsBO(source) {
  return source.includes('BO'); // case-sensitive, mirrors the Python filter
}

function renderCheckboxGrid(containerId, options, selectionsMap, defaultUncheckedLower, onChange) {
  const container = document.getElementById(containerId);
  for (const key of Array.from(selectionsMap.keys())) {
    if (!options.includes(key)) selectionsMap.delete(key);
  }
  container.innerHTML = '';
  for (const option of options) {
    if (!selectionsMap.has(option)) {
      selectionsMap.set(option, !defaultUncheckedLower.has(option.toLowerCase()));
    }
    const label = document.createElement('label');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = selectionsMap.get(option);
    input.addEventListener('change', () => {
      selectionsMap.set(option, input.checked);
      onChange();
    });
    label.appendChild(input);
    label.appendChild(document.createTextNode(option));
    container.appendChild(label);
  }
}

function selectedOptions(selectionsMap) {
  return Array.from(selectionsMap.entries()).filter(([, checked]) => checked).map(([opt]) => opt);
}

function lumpOtherSeries(otherSeries) {
  const boPattern = /\bbo\b|season ticket|life member/i;
  const bo = [];
  const rest = [];
  for (const row of otherSeries) {
    (boPattern.test(row.source) ? bo : rest).push(row);
  }
  const collapse = (rows, label) => {
    const byPeriod = new Map();
    for (const row of rows) {
      const key = row.period.getTime();
      byPeriod.set(key, (byPeriod.get(key) || 0) + row.value);
    }
    return Array.from(byPeriod.entries()).map(([time, value]) => ({ period: new Date(time), source: label, value }));
  };
  return [...collapse(bo, 'Box Office'), ...collapse(rest, 'Other')];
}

function renderAll() {
  if (!state.prepared) return;

  const groupByBookings = document.getElementById('group-by-bookings').checked;
  const modeLabel = groupByBookings ? 'bookings' : 'tickets';
  const timeGroup = 'D';
  const mapStyle = document.getElementById('map-style-select').value;
  const excludeBoPostcode = document.getElementById('exclude-bo-postcode').checked;
  const chartType = document.querySelector('input[name="chart-type"]:checked').value;
  const sessionCapacity = parseInt(document.getElementById('session-capacity').value, 10) || 438;
  const sessionCount = parseInt(document.getElementById('session-count').value, 10) || 8;

  const yTitle = modeLabel === 'tickets' ? 'Tickets' : 'Bookings';

  // --- Season capacity stats ---
  const totalSeatsAvailable = sessionCapacity * sessionCount;
  const totalTicketsSold = Analytics.getTotalTicketsSold(state.prepared);
  const percentSold = totalSeatsAvailable > 0 ? (totalTicketsSold / totalSeatsAvailable) * 100 : 0;
  document.getElementById('stat-total-seats').textContent = totalSeatsAvailable.toLocaleString();
  document.getElementById('stat-total-sold').textContent = totalTicketsSold.toLocaleString();
  document.getElementById('stat-percent-sold').textContent = `${percentSold.toFixed(1)}%`;

  // --- Marketing Response Trend ---
  const sourceSeries = Analytics.getSourceSeries(state.prepared, { mode: modeLabel, timeGroup });

  const nonOtherSeries = sourceSeries.filter((r) => !r.source.toLowerCase().startsWith('other'));
  const otherSeries = sourceSeries.filter((r) => r.source.toLowerCase().startsWith('other'));
  const lumped = lumpOtherSeries(otherSeries);
  const chartableSeries = [...nonOtherSeries, ...lumped];

  const allSources = Array.from(new Set(chartableSeries.map((r) => r.source))).sort((a, b) => a.localeCompare(b));
  renderCheckboxGrid('source-filter', allSources, state.sourceSelections, new Set(['unknown']), renderAll);
  const selectedSources = new Set(selectedOptions(state.sourceSelections));
  const filteredSource = chartableSeries.filter((r) => selectedSources.has(r.source));

  Charts.renderTrendChart('trend-chart', filteredSource, { chartType, yTitle, modeLabel });
  Charts.renderOtherTable('other-table', otherSeries, yTitle);

  // --- Ticket Type Breakdown ---
  const ticketSeries = Analytics.getTicketTypeSeries(state.prepared, timeGroup);
  const allTicketTypes = Array.from(new Set(ticketSeries.map((r) => r.ticketType))).sort((a, b) => a.localeCompare(b));
  renderCheckboxGrid('ticket-type-filter', allTicketTypes, state.ticketTypeSelections, new Set(['final dress rehearsal']), renderAll);
  const selectedTicketTypes = new Set(selectedOptions(state.ticketTypeSelections));
  const filteredTicket = ticketSeries.filter((r) => selectedTicketTypes.has(r.ticketType));

  const allPieCategories = [...state.prepared.map((r) => r.ticketType), 'House seats', 'Unsold'];
  const pieColorMap = Categories.buildPieColorMap(allPieCategories);
  const legendCategories = Categories.getOrderedLegendCategories(allPieCategories);

  const ticketBreakdownMap = new Map();
  for (const row of filteredTicket) {
    ticketBreakdownMap.set(row.ticketType, (ticketBreakdownMap.get(row.ticketType) || 0) + row.value);
  }
  const ticketBreakdown = Array.from(ticketBreakdownMap.entries()).map(([ticketType, value]) => ({ ticketType, value }));
  Charts.renderTicketPie('ticket-pie', ticketBreakdown, pieColorMap);

  // --- Session Sales ---
  const sessionSeries = Analytics.getSessionTicketTypeBreakdown(state.prepared);
  const summaryRows = Charts.renderSessionPies('session-pies', sessionSeries, pieColorMap, legendCategories, sessionCapacity);
  Charts.renderSessionSummaryTable('session-summary', summaryRows);

  // --- Preview table ---
  Charts.renderPreviewTable('preview-table', state.prepared);

  // --- Postcode map ---
  const postcodeRows = excludeBoPostcode ? state.prepared.filter((r) => !containsBO(r.source)) : state.prepared;
  const postcodeSeries = Analytics.getPostcodeSeries(postcodeRows);
  const mapRows = [];
  if (state.postcodeLookup) {
    for (const { postcode, tickets } of postcodeSeries) {
      const lookup = state.postcodeLookup.get(postcode);
      if (lookup) mapRows.push({ postcode, tickets, suburb: lookup.suburb, lat: lookup.lat, lon: lookup.lon });
    }
  }
  Charts.renderPostcodeMap('postcode-map', mapRows, mapStyle);
}

function wireControls() {
  document.getElementById('csv-upload').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => loadFromRows(parseCsvText(reader.result), `Loaded: ${file.name}`);
    reader.onerror = () => showError(`Could not read file: ${reader.error}`);
    reader.readAsText(file);
  });

  ['group-by-bookings', 'exclude-bo-postcode'].forEach((id) => {
    document.getElementById(id).addEventListener('change', renderAll);
  });
  document.getElementById('map-style-select').addEventListener('change', renderAll);
  document.getElementById('session-capacity').addEventListener('input', renderAll);
  document.getElementById('session-count').addEventListener('input', renderAll);
  document.querySelectorAll('input[name="chart-type"]').forEach((el) => {
    el.addEventListener('change', renderAll);
  });
}

wireControls();
loadPostcodeLookup().then(loadDefaultSample);
