// Port of src/analytics.py — data preparation and aggregation.
// Kept as close as practical to the Python behaviour it replaces, including
// its quirks (e.g. ticket counts are credited in full to every listed
// source on a multi-source booking, not split across them).

const MONTH_NAMES = {
  january: 0, february: 1, march: 2, april: 3, may: 4, june: 5,
  july: 6, august: 7, september: 8, october: 9, november: 10, december: 11,
};

const NAN_LIKE = new Set(['nan', 'none']);

function isBlankOrNaN(text) {
  return !text || NAN_LIKE.has(text.toLowerCase());
}

/**
 * Parses "10 July 2026" + "13:12:52" into a local Date. Falls back to the
 * native Date parser for other formats (numeric dates etc.) since this
 * dataset always exports dates as "D Month YYYY".
 */
function parseDateTime(dateStr, timeStr) {
  const d = String(dateStr ?? '').trim();
  const t = String(timeStr ?? '').trim();
  if (!d) return null;

  let day, month, year;
  const named = d.match(/^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$/);
  if (named) {
    day = parseInt(named[1], 10);
    month = MONTH_NAMES[named[2].toLowerCase()];
    year = parseInt(named[3], 10);
    if (month === undefined) return null;
  } else {
    const native = new Date(t ? `${d} ${t}` : d);
    return Number.isNaN(native.getTime()) ? null : native;
  }

  let hour = 0, minute = 0, second = 0;
  if (t) {
    const tm = t.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?/);
    if (tm) {
      hour = parseInt(tm[1], 10);
      minute = parseInt(tm[2], 10);
      second = tm[3] ? parseInt(tm[3], 10) : 0;
    }
  }
  const dt = new Date(year, month, day, hour, minute, second);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

function normalizeSource(value, otherSpecify) {
  const text = String(value ?? '').trim();
  if (isBlankOrNaN(text)) return 'Unknown';

  const lowered = text.toLowerCase();
  if (lowered.startsWith('other')) {
    let custom = '';
    if (otherSpecify !== null && otherSpecify !== undefined) {
      custom = String(otherSpecify).trim();
      if (NAN_LIKE.has(custom.toLowerCase())) custom = '';
    }
    if (custom) return `Other: ${custom}`;

    const idx = text.indexOf(':');
    const inlineCustom = idx >= 0 ? text.slice(idx + 1).trim() : '';
    return inlineCustom ? `Other: ${inlineCustom}` : 'Other';
  }

  return text;
}

function normalizeSources(value, otherSpecify) {
  const text = String(value ?? '').trim();
  const parts = text.split(';').map((p) => p.trim()).filter(Boolean);

  if (parts.length === 0) return [normalizeSource(value, otherSpecify)];

  return parts.map((part) => {
    const useOtherSpecify = part.toLowerCase().startsWith('other') ? otherSpecify : null;
    return normalizeSource(part, useOtherSpecify);
  });
}

function coerceTicketCount(value) {
  if (value === null || value === undefined) return 1;
  const text = String(value).trim();
  if (isBlankOrNaN(text)) return 1;
  const num = parseFloat(text);
  if (Number.isNaN(num)) return 1;
  return Math.max(Math.trunc(num), 1);
}

function normalizeTicketType(value) {
  const text = String(value ?? '').trim();
  if (isBlankOrNaN(text)) return 'Unknown';
  const key = text.toLowerCase().replace(/[^a-z0-9]/g, '');
  if (key === 'groupboxoffice' || key === 'group10') return 'Group';
  return text;
}

/**
 * @param {Array<Object>} rows - raw CSV rows (header:true parse result)
 * @param {Object} columns - { dateCol, timeCol, sourceCol, otherSpecifyCol,
 *   numberOfTicketsCol, ticketTypeCol, postcodeCol, sessionDateCol, sessionTimeCol }
 * @returns {Array<Object>} prepared records, sorted by bookingDatetime
 */
function prepareData(rows, columns) {
  const required = [columns.dateCol, columns.timeCol, columns.sourceCol];
  const missing = required.filter((c) => !c);
  if (missing.length) {
    throw new Error('Missing required columns: could not detect date/time/source columns in this CSV.');
  }

  const prepared = [];
  let rowId = 0;

  for (const row of rows) {
    const bookingDatetime = parseDateTime(row[columns.dateCol], row[columns.timeCol]);
    if (!bookingDatetime) continue;
    const currentRowId = rowId;
    rowId += 1;

    let sessionDatetime = null;
    if (columns.sessionDateCol && columns.sessionTimeCol) {
      sessionDatetime = parseDateTime(row[columns.sessionDateCol], row[columns.sessionTimeCol]);
    }

    const otherSpecify = columns.otherSpecifyCol ? row[columns.otherSpecifyCol] : null;
    const sources = normalizeSources(row[columns.sourceCol], otherSpecify);

    const ticketCount = columns.numberOfTicketsCol
      ? coerceTicketCount(row[columns.numberOfTicketsCol])
      : 1;

    const ticketType = columns.ticketTypeCol
      ? normalizeTicketType(row[columns.ticketTypeCol])
      : 'Unknown';

    let postcode = null;
    if (columns.postcodeCol) {
      const pm = String(row[columns.postcodeCol] ?? '').match(/(\d{4})/);
      postcode = pm ? pm[1] : null;
    }

    for (const source of sources) {
      prepared.push({
        rowId: currentRowId,
        bookingDatetime,
        sessionDatetime,
        source,
        ticketCount,
        ticketType,
        postcode,
      });
    }
  }

  prepared.sort((a, b) => a.bookingDatetime - b.bookingDatetime);
  return prepared;
}

function periodStart(date, freq) {
  const y = date.getFullYear();
  const m = date.getMonth();
  const dNum = date.getDate();
  if (freq === 'h') return new Date(y, m, dNum, date.getHours());
  if (freq === 'D') return new Date(y, m, dNum);
  if (freq === 'W') {
    const day = new Date(y, m, dNum);
    const dow = day.getDay(); // 0=Sun..6=Sat
    const diffToMonday = (dow + 6) % 7;
    day.setDate(day.getDate() - diffToMonday);
    return day;
  }
  if (freq === 'M') return new Date(y, m, 1);
  return date;
}

/**
 * @param {Array<Object>} prepared
 * @param {{mode: 'tickets'|'bookings', timeGroup: 'h'|'D'|'W'|'M'}} opts
 * @returns {Array<{period: Date, source: string, value: number}>}
 */
function getSourceSeries(prepared, { mode, timeGroup }) {
  let rows = prepared;
  if (mode === 'bookings') {
    const seen = new Set();
    rows = [];
    for (const r of prepared) {
      const key = `${r.bookingDatetime.getTime()}|${r.source}`;
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push(r);
    }
  }

  const buckets = new Map();
  for (const r of rows) {
    const period = periodStart(r.bookingDatetime, timeGroup);
    const value = mode === 'bookings' ? 1 : r.ticketCount;
    const key = `${period.getTime()}|${r.source}`;
    const existing = buckets.get(key);
    if (existing) {
      existing.value += value;
    } else {
      buckets.set(key, { period, source: r.source, value });
    }
  }

  return Array.from(buckets.values()).sort((a, b) => a.period - b.period);
}

function getTicketTypeSeries(prepared, timeGroup) {
  const buckets = new Map();
  for (const r of prepared) {
    const period = periodStart(r.bookingDatetime, timeGroup);
    const key = `${period.getTime()}|${r.ticketType}`;
    const existing = buckets.get(key);
    if (existing) {
      existing.value += r.ticketCount;
    } else {
      buckets.set(key, { period, ticketType: r.ticketType, value: r.ticketCount });
    }
  }
  return Array.from(buckets.values()).sort((a, b) => a.period - b.period);
}

/**
 * Total tickets actually sold across the whole dataset. Counts each raw
 * CSV row once (by rowId) rather than summing over `prepared`, which
 * deliberately double-counts multi-source bookings (e.g. "Facebook;Email
 * list") once per exploded source row for the marketing-response chart.
 */
function getTotalTicketsSold(prepared) {
  const seen = new Set();
  let total = 0;
  for (const r of prepared) {
    if (seen.has(r.rowId)) continue;
    seen.add(r.rowId);
    total += r.ticketCount;
  }
  return total;
}

function getPostcodeSeries(prepared) {
  const buckets = new Map();
  for (const r of prepared) {
    if (!r.postcode) continue;
    buckets.set(r.postcode, (buckets.get(r.postcode) || 0) + r.ticketCount);
  }
  return Array.from(buckets.entries()).map(([postcode, tickets]) => ({ postcode, tickets }));
}

function getSessionTicketTypeBreakdown(prepared) {
  const buckets = new Map();
  for (const r of prepared) {
    if (!r.sessionDatetime) continue;
    const key = `${r.sessionDatetime.getTime()}|${r.ticketType}`;
    const existing = buckets.get(key);
    if (existing) {
      existing.value += r.ticketCount;
    } else {
      buckets.set(key, { sessionDatetime: r.sessionDatetime, ticketType: r.ticketType, value: r.ticketCount });
    }
  }
  return Array.from(buckets.values()).sort(
    (a, b) => a.sessionDatetime - b.sessionDatetime || a.ticketType.localeCompare(b.ticketType)
  );
}

window.Analytics = {
  parseDateTime,
  normalizeSource,
  normalizeSources,
  coerceTicketCount,
  normalizeTicketType,
  prepareData,
  periodStart,
  getSourceSeries,
  getTicketTypeSeries,
  getPostcodeSeries,
  getSessionTicketTypeBreakdown,
  getTotalTicketsSold,
};
