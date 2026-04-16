const API_PREFIX = '';
const $ = sel => document.querySelector(sel);

const baseSelect = $('#baseCurrency');
const targetSelect = $('#targetCurrency');
const periodSelect = $('#period');
const btnCalculate = $('#btnCalculate');
const btnReset = $('#btnReset');
const loadingEl = $('#loading');
const resultSummary = $('#resultSummary');
const avgBox = $('#avgBox');
const strongWeakBox = $('#strongWeakBox');
const ctx = document.getElementById('ratesChart').getContext('2d');

let chart = null;
let allCurrenciesList = [];

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
      const text = await r.text().catch(()=>'');
      throw new Error(`${r.status} ${r.statusText} ${text}`);
    }
    return r.json();
  });
}

async function initCurrencyLists() {
  const data = await api('/exchange/latest');
  const rates = data.rates || {};
  const codes = Object.keys(rates).sort();

  if (!codes.includes(data.base)) codes.unshift(data.base);

  allCurrenciesList = codes;

  baseSelect.innerHTML = codes.map(c => `<option value="${c}">${c}</option>`).join('');
  targetSelect.innerHTML = baseSelect.innerHTML;

  baseSelect.value = 'USD' in rates ? 'USD' : data.base || codes[0];
  targetSelect.value = codes.includes('CZK') ? 'CZK' : codes[0];
}

function buildDateRange(days) {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - (days - 1));
  const fmt = d => d.toISOString().slice(0,10);
  return { date_from: fmt(from), date_to: fmt(to) };
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
    }
  });
}

async function calculate() {
  showLoading(true);

  const base = baseSelect.value;
  const target = targetSelect.value;
  const days = Number(periodSelect.value);
  const { date_from, date_to } = buildDateRange(days);

  try {
    const hist = await api(`/exchange/historical-range?currencies=${target}&base=${base}&date_from=${date_from}&date_to=${date_to}`);

    const labels = Object.keys(hist.rates || {}).sort();
    const values = labels.map(d => hist.rates[d]);

    renderChart(labels, values, `${target}/${base}`);

    resultSummary.innerHTML = `${date_from} → ${date_to}`;

  } catch (e) {
    resultSummary.innerHTML = `Error: ${e.message}`;
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
          const base = baseSelect.value;

          const [s, w] = await Promise.all([
            api(`/exchange/strongest?currencies=${allCurrenciesList}&base=${base}`),
            api(`/exchange/weakest?currencies=${allCurrenciesList}&base=${base}`)
      ]);

    const fmt = v => v < 0.0001 ? '>0.0001' : formatNumber(v);

    strongWeakBox.innerHTML = `
      <div>${s.strongest.currency} — ${fmt(s.strongest.rate)}</div>
      <div>${w.weakest.currency} — ${fmt(w.weakest.rate)}</div>
    `;
  } catch (e) {
    strongWeakBox.innerHTML = 'Error';
  }

  showLoading(false);
}

function resetForm() {
  periodSelect.value = '7';
  baseSelect.selectedIndex = 0;
  targetSelect.selectedIndex = 0;

  resultSummary.innerHTML = '';
  avgBox.innerHTML = '';
  strongWeakBox.innerHTML = '';

  if (chart) {
    chart.data.labels = [];
    chart.data.datasets[0].data = [];
    chart.update();
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  await initCurrencyLists();
  btnCalculate.onclick = calculate;
  btnReset.onclick = resetForm;
});