// ==========================================
// CONFIGURATION & CONSTANTS
// ==========================================
const API_PREFIX = '';
const DEFAULT_PERIOD_DAYS = '7';
const DEFAULT_BASE_CURRENCY = 'USD';
const DEFAULT_TARGET_CURRENCY = 'CZK';
const STORAGE_KEY = 'exchangeDashboardState'; // Key for Local Storage

// ==========================================
// DOM ELEMENTS
// ==========================================
const $ = sel => document.querySelector(sel);

const baseSelect = $('#baseCurrency');
const targetSelect = $('#targetCurrency');
const periodSelect = $('#period');
const btnCalculate = $('#btnCalculate');
const btnReset = $('#btnReset');
const loadingEl = $('#loading');
const avgBox = $('#avgBox');
const strongWeakBox = $('#strongWeakBox');
const ctx = document.getElementById('ratesChart').getContext('2d');

// ==========================================
// STATE VARIABLES
// ==========================================
let chart = null;
let allCurrenciesList = [];

// ==========================================
// UTILITY FUNCTIONS
// ==========================================

function showLoading(on) {
  loadingEl.classList.toggle('d-none', !on);
  btnCalculate.disabled = on;
  btnReset.disabled = on;
}

function formatNumber(v) {
  if (v === null || v === undefined) return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 6 });
}

function api(path) {
  return fetch(API_PREFIX + path).then(async r => {
    if (!r.ok) {
      const text = await r.text().catch(() => '');
      throw new Error(`${r.status} ${r.statusText} ${text}`);
    }
    return r.json();
  });
}

function buildDateRange(days) {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - (days - 1));
  const fmt = d => d.toISOString().slice(0, 10);
  return { date_from: fmt(from), date_to: fmt(to) };
}

// ==========================================
// LOCAL STORAGE FUNCTIONS (NEW)
// ==========================================

/**
 * Saves current parameters and results to Local Storage
 */
function saveState(chartLabels, chartValues) {
  const state = {
    base: baseSelect.value,
    target: targetSelect.value,
    period: periodSelect.value,
    avgHtml: avgBox.innerHTML,
    strongWeakHtml: strongWeakBox.innerHTML,
    chartData: {
      labels: chartLabels || (chart ? chart.data.labels : []),
      values: chartValues || (chart ? chart.data.datasets[0].data : []),
      label: `${targetSelect.value}/${baseSelect.value}`
    }
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

/**
 * Loads saved parameters and restores the interface
 */
function loadState() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return false;

  try {
    const state = JSON.parse(saved);

    // Restore input values
    baseSelect.value = state.base;
    targetSelect.value = state.target;
    periodSelect.value = state.period;

    // Restore result text
    avgBox.innerHTML = state.avgHtml;
    strongWeakBox.innerHTML = state.strongWeakHtml;

    // Restore chart if saved data exists
    if (state.chartData && state.chartData.labels.length > 0) {
      renderChart(state.chartData.labels, state.chartData.values, state.chartData.label);
    }
    return true;
  } catch (e) {
    console.error("Error reading from localStorage", e);
    return false;
  }
}

// ==========================================
// CORE FUNCTIONS
// ==========================================

async function initCurrencyLists() {
  const data = await api('/exchange/latest');
  const rates = data.rates || {};
  const codes = Object.keys(rates).sort();

  if (!codes.includes(data.base)) codes.unshift(data.base);

  allCurrenciesList = codes;

  const optionsHtml = codes.map(c => `<option value="${c}">${c}</option>`).join('');
  baseSelect.innerHTML = optionsHtml;
  targetSelect.innerHTML = optionsHtml;

  baseSelect.value = codes.includes(DEFAULT_BASE_CURRENCY) ? DEFAULT_BASE_CURRENCY : (data.base || codes[0]);
  targetSelect.value = codes.includes(DEFAULT_TARGET_CURRENCY) ? DEFAULT_TARGET_CURRENCY : codes[0];
}

function renderChart(labels, values, labelText) {
  if (chart) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.data.datasets[0].label = labelText;
    chart.update();
    return;
  }

  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: labelText,
        data: values,
        borderColor: '#0d6efd',
        backgroundColor: 'rgba(13,110,253,0.08)',
        tension: 0.2,
        pointRadius: 2,
        fill: true
      }]
    },
    options: {
      plugins: {
        legend: {
          display: false
        }
      }
    }
  });
}

async function calculate() {
  showLoading(true);

  const base = baseSelect.value;
  const target = targetSelect.value;
  const days = Number(periodSelect.value);
  const { date_from, date_to } = buildDateRange(days);

  // Variables to store chart data for saving later
  let chartLabels = [];
  let chartValues = [];

  try {
    const hist = await api(`/exchange/historical-range?currencies=${target}&base=${base}&date_from=${date_from}&date_to=${date_to}`);
    chartLabels = Object.keys(hist.rates || {}).sort();
    chartValues = chartLabels.map(d => hist.rates[d]);
    renderChart(chartLabels, chartValues, `${target}/${base}`);
  } catch (e) {
    showLoading(false);
    return;
  }

  try {
    const avg = await api(`/exchange/average?currencies=${target}&base=${base}&date_from=${date_from}&date_to=${date_to}`);
    avgBox.innerHTML = `<div class="h5">${formatNumber(avg.averages?.[target])}</div>`;
  } catch (e) {
    avgBox.innerHTML = `Error`;
  }

  try {
    const [s, w] = await Promise.all([
      api(`/exchange/strongest?currencies=${allCurrenciesList}&base=${base}`),
      api(`/exchange/weakest?currencies=${allCurrenciesList}&base=${base}`)
    ]);

    const fmt = v => v < 0.0001 ? '>0.0001' : formatNumber(v);

    strongWeakBox.innerHTML = `
      <div><strong>Strongest:</strong> ${s.strongest.currency} — ${fmt(s.strongest.rate)}</div>
      <div><strong>Weakest:</strong> ${w.weakest.currency} — ${fmt(w.weakest.rate)}</div>
    `;
  } catch (e) {
    strongWeakBox.innerHTML = 'Error';
  }

  // Save all calculations and settings after successful execution
  saveState(chartLabels, chartValues);

  showLoading(false);
}

function resetForm() {
  periodSelect.value = DEFAULT_PERIOD_DAYS;

  const baseOptions = Array.from(baseSelect.options);
  baseSelect.value = baseOptions.some(o => o.value === DEFAULT_BASE_CURRENCY) ? DEFAULT_BASE_CURRENCY : baseOptions[0].value;

  const targetOptions = Array.from(targetSelect.options);
  targetSelect.value = targetOptions.some(o => o.value === DEFAULT_TARGET_CURRENCY) ? DEFAULT_TARGET_CURRENCY : targetOptions[0].value;

  avgBox.innerHTML = '';
  strongWeakBox.innerHTML = '';

  if (chart) {
    chart.data.labels = [];
    chart.data.datasets[0].data = [];
    chart.update();
  }

  // Clear Local Storage on reset
  localStorage.removeItem(STORAGE_KEY);
}

// ==========================================
// INITIALIZATION & EVENT LISTENERS
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
  // First, load the currency list so the selects are populated with options
  await initCurrencyLists();

  // Attempt to load state. If it doesn't exist, default values remain
  loadState();

  btnCalculate.onclick = calculate;
  btnReset.onclick = resetForm;
});