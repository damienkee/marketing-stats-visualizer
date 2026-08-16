// Port of the ticket-category canonicalization/color-mapping helpers from app.py.
// Used to keep pie chart legend order and colors consistent across charts.

const ALIAS_TO_NAMED = {
  adult: 'adult', adults: 'adult',
  concession: 'concession', concessions: 'concession', conceccsion: 'concession', concesssion: 'concession',
  family: 'family', families: 'family',
  junior: 'junior', juniors: 'junior',
  group: 'group', group10: 'group', 'group box office': 'group',
  'season ticket': 'season ticket', 'season tickets': 'season ticket',
  subscriber: 'season ticket', subscribers: 'season ticket',
  'final dress rehearsal': 'final dress rehearsal', 'final dress rehersal': 'final dress rehearsal',
  complimentary: 'complimentary', complementary: 'complimentary', comp: 'complimentary',
  'front of house': 'front of house', foh: 'front of house',
  'house seat': 'house seats', 'house seats': 'house seats',
  unsold: 'unsold',
  unknown: 'unknown',
};

function canonicalTicketCategory(label) {
  const normalized = String(label).toLowerCase().replace(/[_-]/g, ' ').split(/\s+/).filter(Boolean).join(' ');
  const mapped = ALIAS_TO_NAMED[normalized];
  if (mapped) return mapped;

  if (normalized.includes('unsold')) return 'unsold';
  if (normalized.startsWith('season ticket') || normalized.includes('subscriber')) return 'season ticket';
  if (normalized.startsWith('adult')) return 'adult';
  if (normalized.startsWith('concession') || normalized.startsWith('conce')) return 'concession';
  if (normalized.startsWith('family')) return 'family';
  if (normalized.startsWith('junior')) return 'junior';
  if (normalized.startsWith('group')) return 'group';
  if (normalized.startsWith('final dress')) return 'final dress rehearsal';
  if (normalized.startsWith('compl')) return 'complimentary';
  if (normalized.startsWith('house seat')) return 'house seats';

  return normalized;
}

const NAMED_CATEGORY_ORDER = [
  'season ticket', 'adult', 'concession', 'family', 'junior', 'group',
  'final dress rehearsal', 'complimentary', 'house seats', 'front of house', 'unknown', 'unsold',
];
const CATEGORY_RANK = new Map(NAMED_CATEGORY_ORDER.map((name, idx) => [name, idx]));

function getOrderedLegendCategories(categories) {
  const unique = Array.from(new Set(categories.map((c) => String(c).trim()).filter(Boolean)));
  return unique.sort((a, b) => {
    const rankA = CATEGORY_RANK.has(canonicalTicketCategory(a)) ? CATEGORY_RANK.get(canonicalTicketCategory(a)) : 10000;
    const rankB = CATEGORY_RANK.has(canonicalTicketCategory(b)) ? CATEGORY_RANK.get(canonicalTicketCategory(b)) : 10000;
    if (rankA !== rankB) return rankA - rankB;
    return a.toLowerCase().localeCompare(b.toLowerCase());
  });
}

const NAMED_CATEGORY_COLORS = {
  unsold: '#b0b0b0',
  'season ticket': '#9467bd',
  adult: '#1f77b4',
  concession: '#2ca02c',
  family: '#e377c2',
  junior: '#ff7f0e',
  group: '#17becf',
  'final dress rehearsal': '#bcbd22',
  complimentary: '#d62728',
  'house seats': '#1f3b5c',
  'front of house': '#8c564b',
  unknown: '#7f7f7f',
};

// Fallback palette for categories with no named color, combining several
// Plotly qualitative sequences (exact match to the Python build isn't
// essential here — this only affects rare/unexpected ticket-type labels).
const FALLBACK_PALETTE = [
  '#88CCEE', '#CC6677', '#DDCC77', '#117733', '#332288', '#AA4499', '#44AA99', '#999933', '#882255', '#661100', '#6699CC', '#888888',
  '#8DD3C7', '#FFFFB3', '#BEBADA', '#FB8072', '#80B1D3', '#FDB462', '#B3DE69', '#FCCDE5', '#D9D9D9', '#BC80BD', '#CCEBC5', '#FFED6F',
  '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
  '#7F3C8D', '#11A579', '#3969AC', '#F2B701', '#E73F74', '#80BA5A', '#E68310', '#008695', '#CF1C90', '#F97B72',
];

function buildPieColorMap(categories) {
  const colorMap = {};
  let paletteIndex = 0;
  for (const category of getOrderedLegendCategories(categories)) {
    const canonical = canonicalTicketCategory(category);
    if (NAMED_CATEGORY_COLORS[canonical]) {
      colorMap[category] = NAMED_CATEGORY_COLORS[canonical];
      continue;
    }
    colorMap[category] = FALLBACK_PALETTE[paletteIndex % FALLBACK_PALETTE.length];
    paletteIndex += 1;
  }
  return colorMap;
}

// Generic qualitative palette for the trend chart (sources), assigned in
// first-appearance order, mirroring Plotly Express's default behaviour.
const TREND_PALETTE = [
  '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
  '#1F77B4', '#FF7F0E', '#2CA02C', '#D62728', '#9467BD', '#8C564B', '#E377C2', '#7F7F7F', '#BCBD22', '#17BECF',
];

function assignTrendColors(categoriesInOrder) {
  const colorMap = {};
  categoriesInOrder.forEach((cat, idx) => {
    colorMap[cat] = TREND_PALETTE[idx % TREND_PALETTE.length];
  });
  return colorMap;
}

window.Categories = {
  canonicalTicketCategory,
  getOrderedLegendCategories,
  buildPieColorMap,
  assignTrendColors,
};
