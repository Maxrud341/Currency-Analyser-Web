// ==========================================
// 1. Konfigurace a DOM Elementy
// ==========================================
const API_PREFIX = '/exchange';
const DEFAULT_PERIOD_DAYS = '7';
const DEFAULT_BASE_CURRENCY = 'USD';
const DEFAULT_TARGET_CURRENCY = 'CZK';
const STORAGE_KEY = 'exchangeDashboardState';

const $ = sel => document.querySelector(sel);
const baseSelect = $('#baseCurrency');
const targetSelect = $('#targetCurrency');
const periodSelect = $('#period');
const btnCalculate = $('#btnCalculate');
const btnReset = $('#btnReset');
const loadingEl = $('#loading');

const currentRateBox = $('#currentRateBox');
const avgBox = $('#avgBox');
const strongWeakBox = $('#strongWeakBox');
const ctx = $('#ratesChart').getContext('2d');

const compareCurrencySelect = $('#compareCurrencySelect');
const btnAddCurrency = $('#btnAddCurrency');
const comparisonTableBody = $('#comparisonTableBody');

let chart = null;
let comparedCurrencies = [];
let tableRates = {};

// ==========================================
// 2. Pomocné funkce
// ==========================================
function showLoading(on) {
  loadingEl.classList.toggle('d-none', !on);
  btnCalculate.disabled = on;
  btnReset.disabled = on;
}

function formatNumber(v) {
  if (v === null || v === undefined) return '—';
  return Number(v).toLocaleString('cs-CZ', { maximumFractionDigits: 6 });
}

function api(path) {
  return fetch(API_PREFIX + path).then(async r => {
    if (!r.ok) throw new Error(`${r.status}`);
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
// 3. Inicializace a Vykreslování
// ==========================================
async function initCurrencyLists() {
  try {
    const codes = await api('/supported-currencies');
    const optionsHtml = codes.map(c => `<option value="${c}">${c}</option>`).join('');

    baseSelect.innerHTML = optionsHtml;
    targetSelect.innerHTML = optionsHtml;
    compareCurrencySelect.innerHTML = `<option value="" selected disabled>Vyberte měnu...</option>` + optionsHtml;

    baseSelect.value = codes.includes(DEFAULT_BASE_CURRENCY) ? DEFAULT_BASE_CURRENCY : codes[0];
    targetSelect.value = codes.includes(DEFAULT_TARGET_CURRENCY) ? DEFAULT_TARGET_CURRENCY : codes[1];
  } catch (e) {
    console.error("Chyba načítání podporovaných měn", e);
  }
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
        tension: 0.2, pointRadius: 2, fill: true
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      interaction: { intersect: false, mode: 'index' }
    }
  });
}

function renderTable() {
  if (comparedCurrencies.length === 0) {
    comparisonTableBody.innerHTML = `<tr><td colspan="2" class="text-center text-muted">Žádné měny k porovnání</td></tr>`;
    return;
  }

  comparisonTableBody.innerHTML = comparedCurrencies.map(c => {
    const val = tableRates[c] ? formatNumber(tableRates[c]) : '<span class="spinner-border spinner-border-sm text-primary"></span>';
    return `
      <tr>
        <td>
          <div class="d-flex justify-content-between align-items-center">
            ${c}
            <button class="btn btn-sm text-danger py-0 px-1 border-0" onclick="removeCurrency('${c}')">✕</button>
          </div>
        </td>
        <td class="fw-medium">${val}</td>
      </tr>
    `;
  }).join('');
}

// ==========================================
// 4. Logika tabulky (okamžitý výpočet)
// ==========================================

// Aktualizuje kurzy a nejsilnější/nejslabší měny z tabulky
async function updateComparison() {
  const base = baseSelect.value;

  if (comparedCurrencies.length === 0) {
    tableRates = {};
    renderTable();
    strongWeakBox.innerHTML = '<span class="text-muted">Přidejte měny do tabulky</span>';
    return;
  }

  const currStr = comparedCurrencies.join(',');
  try {
    const [s, w] = await Promise.all([
      api(`/strongest?currencies=${currStr}&base=${base}`),
      api(`/weakest?currencies=${currStr}&base=${base}`)
    ]);

    tableRates = s.all_rates || {};
    renderTable();

    const fmt = v => (v < 0.0001 ? '< 0.0001' : formatNumber(v));
strongWeakBox.innerHTML = `
  <div class="sw-grid">
    <div class="sw-row">
      <span class="sw-label">Nejsilnější:</span>
      <span class="badge bg-success sw-badge">${s.strongest.currency}</span>
      <span class="sw-value">${fmt(s.strongest.rate)}</span>
    </div>
    <div class="sw-row">
      <span class="sw-label">Nejslabší:</span>
      <span class="badge bg-danger sw-badge">${w.weakest.currency}</span>
      <span class="sw-value">${fmt(w.weakest.rate)}</span>
    </div>
  </div>
`;
  } catch (e) {
    strongWeakBox.innerHTML = '<span class="text-danger">Chyba načítání</span>';
  }
}

btnAddCurrency.onclick = async () => {
  const c = compareCurrencySelect.value;
  if (c && !comparedCurrencies.includes(c)) {
    comparedCurrencies.push(c);

    renderTable(); // Zobrazí měnu s načítacím kolečkem
    btnAddCurrency.disabled = true; // Ochrana proti spamu

    await updateComparison(); // Okamžitý dotaz na API
    saveState(chart?.data.labels || [], chart?.data.datasets[0].data || []); // Uložit do LS

    btnAddCurrency.disabled = false;
  }
  compareCurrencySelect.value = "";
};

window.removeCurrency = async function(code) {
  comparedCurrencies = comparedCurrencies.filter(c => c !== code);
  delete tableRates[code];

  await updateComparison(); // Přepočítá min/max bez smazané měny
  saveState(chart?.data.labels || [], chart?.data.datasets[0].data || []);
};

// ==========================================
// 5. Hlavní výpočet grafu a průměru
// ==========================================
async function calculate() {
  showLoading(true);

  const base = baseSelect.value;
  const target = targetSelect.value;
  const days = Number(periodSelect.value);
  const { date_from, date_to } = buildDateRange(days);

  let chartLabels = [], chartValues = [];

  // 1. Aktuální kurz
  try {
    const curr = await api(`/current?from=${base}&to=${target}`);
    currentRateBox.innerHTML = `
      <div class="h5 mb-1 fw-bold">${formatNumber(curr.rate)}</div>
    `;
  } catch (e) {
    currentRateBox.innerHTML = '<span class="text-danger">Chyba</span>';
  }

  // 2. Historie (Graf)
  try {
    const hist = await api(`/historical-range?currencies=${target}&base=${base}&date_from=${date_from}&date_to=${date_to}`);
    chartLabels = Object.keys(hist.rates || {}).sort();
    chartValues = chartLabels.map(d => hist.rates[d]);
    renderChart(chartLabels, chartValues, `${target}/${base}`);
  } catch (e) {
    console.error("Chyba grafu", e);
  }

  // 3. Průměr
  try {
    const avg = await api(`/average?currencies=${target}&base=${base}&date_from=${date_from}&date_to=${date_to}`);
    avgBox.innerHTML = `<div class="h5 mb-0 fw-bold">${formatNumber(avg.averages?.[target])}</div>`;
  } catch (e) {
    avgBox.innerHTML = '<span class="text-danger">Chyba</span>';
  }

  // 4. Obnova tabulky (pokud byla např. změněna Base měna)
  await updateComparison();

  saveState(chartLabels, chartValues);
  showLoading(false);
}

// ==========================================
// 6. Reset a LocalStorage
// ==========================================
function resetForm() {
  periodSelect.value = DEFAULT_PERIOD_DAYS;
  comparedCurrencies = [];
  tableRates = {};

  avgBox.innerHTML = '';
  currentRateBox.innerHTML = '';
  strongWeakBox.innerHTML = '';

  if (chart) {
    chart.data.labels = [];
    chart.data.datasets[0].data = [];
    chart.update();
  }

  renderTable();
  localStorage.removeItem(STORAGE_KEY);
}

function saveState(labels, values) {
  const state = {
    base: baseSelect.value,
    target: targetSelect.value,
    period: periodSelect.value,
    compared: comparedCurrencies,
    rates: tableRates,
    currHtml: currentRateBox.innerHTML,
    avgHtml: avgBox.innerHTML,
    swHtml: strongWeakBox.innerHTML,
    chart: { labels, values, label: `${targetSelect.value}/${baseSelect.value}` }
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function loadState() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return;

  try {
    const s = JSON.parse(saved);
    baseSelect.value = s.base;
    targetSelect.value = s.target;
    periodSelect.value = s.period;

    comparedCurrencies = s.compared || [];
    tableRates = s.rates || {};

    currentRateBox.innerHTML = s.currHtml || '';
    avgBox.innerHTML = s.avgHtml || '';
    strongWeakBox.innerHTML = s.swHtml || '';

    renderTable();

    if (s.chart && s.chart.labels && s.chart.labels.length > 0) {
      renderChart(s.chart.labels, s.chart.values, s.chart.label);
    }
  } catch (e) {
    console.error("Chyba při čtení z localStorage", e);
  }
}

// ==========================================
// 7. Spuštění
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
  await initCurrencyLists();
  loadState();
  renderTable();

  btnCalculate.onclick = calculate;
  btnReset.onclick = resetForm;
});