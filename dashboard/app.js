// ============================================================
// SoilSense ZM — Web Dashboard
// app.js — API integration, view logic, charts
//
// Author: Lushomo Sibalwa — 202301072 — ZCAS University
// ============================================================

const API = window.location.origin;

// ── STATE ────────────────────────────────────────────────────

let currentView = 'farmer';
let farmersData = [];
let healthChart = null;
let activityChart = null;

// ── INIT ─────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  checkApiStatus();
  setupViewSwitcher();
  setupReadingForm();
  setupRegisterForm();
  setupModals();

  // Auto-refresh officer data every 30s
  setInterval(() => {
    if (currentView === 'officer') loadOfficerData();
  }, 30000);
});

// ── API STATUS ───────────────────────────────────────────────

async function checkApiStatus() {
  const dot = document.getElementById('apiDot');
  const label = document.getElementById('apiLabel');
  try {
    const res = await fetch(`${API}/`);
    const data = await res.json();
    dot.classList.add('online');
    dot.classList.remove('offline');
    label.textContent = data.model_loaded ? 'Model Ready' : 'Model Missing';
  } catch {
    dot.classList.add('offline');
    dot.classList.remove('online');
    label.textContent = 'API Offline';
  }
}

// ── VIEW SWITCHER ────────────────────────────────────────────

function setupViewSwitcher() {
  const btns = document.querySelectorAll('.view-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      if (view === currentView) return;
      currentView = view;

      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.getElementById(`${view}View`).classList.add('active');

      if (view === 'officer') loadOfficerData();
    });
  });
}

// ── READING FORM ─────────────────────────────────────────────

function setupReadingForm() {
  const form = document.getElementById('readingForm');
  const btn = document.getElementById('btnPredict');
  const newBtn = document.getElementById('btnNewReading');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    btn.classList.add('loading');
    btn.disabled = true;

    const payload = {
      pH: parseFloat(form.pH.value),
      moisture: parseFloat(form.moisture.value),
      temperature: parseFloat(form.temperature.value),
    };

    // Optional fields
    if (form.nitrogen.value) payload.nitrogen = parseFloat(form.nitrogen.value);
    if (form.phosphorus.value) payload.phosphorus = parseFloat(form.phosphorus.value);
    if (form.organic_carbon.value) payload.organic_carbon = parseFloat(form.organic_carbon.value);
    if (form.farmer_phone.value) payload.farmer_phone = form.farmer_phone.value.trim();

    try {
      const res = await fetch(`${API}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Prediction failed');
      }

      const data = await res.json();
      displayResult(data);
      showToast('Soil analysis complete!', 'success');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.classList.remove('loading');
      btn.disabled = false;
    }
  });

  newBtn.addEventListener('click', () => {
    document.getElementById('resultPanel').classList.remove('visible');
    document.getElementById('readingCard').scrollIntoView({ behavior: 'smooth' });
    form.reset();
  });
}

// ── DISPLAY PREDICTION RESULT ────────────────────────────────

function displayResult(data) {
  const panel = document.getElementById('resultPanel');
  const header = document.getElementById('resultHeader');
  const icon = document.getElementById('resultIcon');
  const label = document.getElementById('resultLabel');
  const conf = document.getElementById('resultConfidence');
  const timestamp = document.getElementById('resultTimestamp');

  // Status mapping
  const statusMap = {
    'Healthy':  { icon: '✅', class: 'healthy' },
    'Moderate': { icon: '⚠️', class: 'moderate' },
    'Degraded': { icon: '🔶', class: 'degraded' },
    'Critical': { icon: '🚨', class: 'critical' },
  };

  const status = statusMap[data.soil_health] || statusMap['Moderate'];

  // Header
  header.className = `result-header ${status.class}`;
  icon.textContent = status.icon;
  label.textContent = `${data.soil_health} Soil`;
  conf.textContent = `${data.confidence}% confidence${data.sms_sent ? ' · SMS sent ✓' : ''}`;
  timestamp.textContent = new Date().toLocaleString('en-ZM', {
    dateStyle: 'medium', timeStyle: 'short'
  });

  // Advisory sections
  document.getElementById('resultSummary').textContent = data.advisory.summary;
  document.getElementById('resultLime').textContent = data.advisory.lime_recommendation;
  document.getElementById('resultFertilizer').textContent = data.advisory.fertilizer_recommendation;

  // Crop list
  const cropsEl = document.getElementById('resultCrops');
  cropsEl.innerHTML = '';
  data.advisory.crop_suitability.forEach(crop => {
    const li = document.createElement('li');
    li.textContent = crop;
    cropsEl.appendChild(li);
  });

  // Management advice
  const adviceEl = document.getElementById('resultAdvice');
  adviceEl.innerHTML = '';
  data.advisory.management_advice.forEach(tip => {
    const li = document.createElement('li');
    li.textContent = tip;
    adviceEl.appendChild(li);
  });

  // Show panel
  panel.classList.add('visible');
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── OFFICER VIEW ─────────────────────────────────────────────

async function loadOfficerData() {
  try {
    const res = await fetch(`${API}/farmers`);
    if (!res.ok) throw new Error('Failed to load farmers');
    farmersData = await res.json();
    renderStats();
    renderFarmerTable();
    renderCharts();
  } catch (err) {
    showToast('Failed to load data: ' + err.message, 'error');
  }
}

function renderStats() {
  const total = farmersData.length;
  let totalReadings = 0;
  let healthy = 0;
  let atRisk = 0;

  farmersData.forEach(f => {
    totalReadings += f.total_readings || 0;
    if (f.latest_alert_level === 'green') healthy++;
    if (f.latest_alert_level === 'orange' || f.latest_alert_level === 'red') atRisk++;
  });

  document.getElementById('statFarmers').textContent = total;
  document.getElementById('statReadings').textContent = totalReadings;
  document.getElementById('statHealthy').textContent = healthy;
  document.getElementById('statAtRisk').textContent = atRisk;

  const farmersWithReadings = farmersData.filter(f => f.total_readings > 0).length;
  document.getElementById('statHealthyPct').textContent =
    farmersWithReadings > 0 ? `${Math.round(healthy / farmersWithReadings * 100)}% of assessed farms` : '';
  document.getElementById('statAtRiskPct').textContent =
    farmersWithReadings > 0 ? `${Math.round(atRisk / farmersWithReadings * 100)}% need intervention` : '';
}

function renderFarmerTable() {
  const tbody = document.getElementById('farmerTableBody');
  const empty = document.getElementById('farmerEmpty');
  const wrap = document.getElementById('farmerTableWrap');
  const count = document.getElementById('farmerCount');

  if (farmersData.length === 0) {
    empty.style.display = 'block';
    wrap.style.display = 'none';
    count.textContent = 'No farmers registered';
    return;
  }

  empty.style.display = 'none';
  wrap.style.display = 'block';
  count.textContent = `${farmersData.length} farmer${farmersData.length !== 1 ? 's' : ''} registered`;

  tbody.innerHTML = '';

  farmersData.forEach(f => {
    const tr = document.createElement('tr');

    const alertBadge = f.latest_alert_level
      ? `<span class="badge badge-${f.latest_alert_level}">${f.latest_prediction || '—'}</span>`
      : '<span class="badge" style="color:var(--text-muted);">No data</span>';

    tr.innerHTML = `
      <td class="farmer-name">${escHtml(f.name)}</td>
      <td>${escHtml(f.location)}</td>
      <td>${escHtml(f.phone)}</td>
      <td>${f.farm_size_hectares ? f.farm_size_hectares + ' ha' : '—'}</td>
      <td>${f.total_readings}</td>
      <td>${alertBadge}</td>
      <td><button class="btn btn-secondary btn-sm" data-farmer-id="${f.id}">View</button></td>
    `;

    // View button handler
    tr.querySelector('button').addEventListener('click', () => openFarmerDetail(f));
    tbody.appendChild(tr);
  });
}

function renderCharts() {
  // Count by health status
  const counts = { Healthy: 0, Moderate: 0, Degraded: 0, Critical: 0, 'No Data': 0 };
  farmersData.forEach(f => {
    if (!f.latest_prediction) counts['No Data']++;
    else counts[f.latest_prediction] = (counts[f.latest_prediction] || 0) + 1;
  });

  const labels = Object.keys(counts).filter(k => counts[k] > 0);
  const values = labels.map(k => counts[k]);
  const colorMap = {
    'Healthy': '#198754',
    'Moderate': '#E9C46A',
    'Degraded': '#E76F51',
    'Critical': '#C1121F',
    'No Data': '#3a3f47',
  };
  const colors = labels.map(k => colorMap[k] || '#3a3f47');

  // Health distribution donut
  const ctx1 = document.getElementById('chartHealth');
  if (healthChart) healthChart.destroy();
  healthChart = new Chart(ctx1, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: '#0a0d12',
        borderWidth: 3,
        hoverBorderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '65%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#9aa0a8',
            font: { family: 'Inter', size: 11 },
            padding: 14,
            usePointStyle: true,
            pointStyleWidth: 8,
          },
        },
      },
    },
  });

  // Activity chart — readings per farmer (bar)
  const ctx2 = document.getElementById('chartActivity');
  if (activityChart) activityChart.destroy();

  const topFarmers = [...farmersData]
    .filter(f => f.total_readings > 0)
    .sort((a, b) => b.total_readings - a.total_readings)
    .slice(0, 8);

  activityChart = new Chart(ctx2, {
    type: 'bar',
    data: {
      labels: topFarmers.map(f => f.name.split(' ')[0]),
      datasets: [{
        label: 'Readings',
        data: topFarmers.map(f => f.total_readings),
        backgroundColor: 'rgba(25, 135, 84, 0.6)',
        borderColor: '#198754',
        borderWidth: 1,
        borderRadius: 6,
        barPercentage: 0.6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      indexAxis: 'y',
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#5f6570', font: { family: 'Inter', size: 10 } },
        },
        y: {
          grid: { display: false },
          ticks: { color: '#9aa0a8', font: { family: 'Inter', size: 11 } },
        },
      },
      plugins: {
        legend: { display: false },
      },
    },
  });
}

// ── FARMER DETAIL MODAL ──────────────────────────────────────

async function openFarmerDetail(farmer) {
  const modal = document.getElementById('farmerDetailModal');

  document.getElementById('detailAvatar').textContent = farmer.name.charAt(0).toUpperCase();
  document.getElementById('detailName').textContent = farmer.name;
  document.getElementById('detailMeta').textContent =
    `${farmer.location} · ${farmer.phone}${farmer.farm_size_hectares ? ' · ' + farmer.farm_size_hectares + ' ha' : ''}`;

  const alertBadge = farmer.latest_alert_level
    ? `<span class="badge badge-${farmer.latest_alert_level}">${farmer.latest_prediction}</span>`
    : '<span class="badge" style="color:var(--text-muted);">No readings</span>';
  document.getElementById('detailBadge').innerHTML = alertBadge;

  const listEl = document.getElementById('detailReadingsList');
  listEl.innerHTML = '<div class="empty-state"><div class="empty-state-text">Loading...</div></div>';

  modal.classList.add('visible');

  // Fetch readings
  try {
    const res = await fetch(`${API}/farmers/${farmer.id}/readings`);
    if (!res.ok) throw new Error('Failed');
    const readings = await res.json();

    if (readings.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">No readings yet</div></div>';
      return;
    }

    listEl.innerHTML = '';
    readings.forEach(r => {
      const statusClass = (r.prediction || '').toLowerCase();
      const date = r.created_at ? new Date(r.created_at).toLocaleString('en-ZM', {
        dateStyle: 'medium', timeStyle: 'short'
      }) : '—';

      const div = document.createElement('div');
      div.className = `reading-card ${statusClass}`;
      div.innerHTML = `
        <div class="reading-meta">
          <span class="badge badge-${alertColor(r.prediction)}">${r.prediction || '—'}</span>
          <span class="reading-date">${date}</span>
        </div>
        <div class="reading-values">
          <span><span class="label">pH</span> ${r.pH ?? '—'}</span>
          <span><span class="label">Moisture</span> ${r.moisture ?? '—'}%</span>
          <span><span class="label">Temp</span> ${r.temperature ?? '—'}°C</span>
          <span><span class="label">Conf</span> ${r.confidence ?? '—'}%</span>
        </div>
      `;
      listEl.appendChild(div);
    });
  } catch {
    listEl.innerHTML = '<div class="empty-state"><div class="empty-state-text" style="color:var(--color-critical);">Failed to load readings</div></div>';
  }
}

function alertColor(prediction) {
  const map = { 'Healthy': 'green', 'Moderate': 'yellow', 'Degraded': 'orange', 'Critical': 'red' };
  return map[prediction] || 'green';
}

// ── REGISTER FARMER ──────────────────────────────────────────

function setupRegisterForm() {
  const form = document.getElementById('registerForm');
  const btn = document.getElementById('btnSubmitFarmer');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    btn.classList.add('loading');
    btn.disabled = true;

    const payload = {
      name: document.getElementById('regName').value.trim(),
      phone: document.getElementById('regPhone').value.trim(),
      location: document.getElementById('regLocation').value.trim(),
      district: 'Kafue',
    };

    const size = document.getElementById('regFarmSize').value;
    if (size) payload.farm_size_hectares = parseFloat(size);

    try {
      const res = await fetch(`${API}/farmers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Registration failed');
      }

      showToast(`${payload.name} registered successfully!`, 'success');
      document.getElementById('registerModal').classList.remove('visible');
      form.reset();
      loadOfficerData();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.classList.remove('loading');
      btn.disabled = false;
    }
  });
}

// ── MODALS ───────────────────────────────────────────────────

function setupModals() {
  // Register modal
  document.getElementById('btnRegisterFarmer').addEventListener('click', () => {
    document.getElementById('registerModal').classList.add('visible');
  });
  document.getElementById('closeRegisterModal').addEventListener('click', () => {
    document.getElementById('registerModal').classList.remove('visible');
  });

  // Farmer detail modal
  document.getElementById('closeFarmerDetail').addEventListener('click', () => {
    document.getElementById('farmerDetailModal').classList.remove('visible');
  });

  // Close on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('visible');
    });
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.visible').forEach(m => m.classList.remove('visible'));
    }
  });
}

// ── TOAST NOTIFICATIONS ──────────────────────────────────────

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  toast.innerHTML = `<span>${icons[type] || ''}</span> ${escHtml(message)}`;

  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) toast.remove();
  }, 4000);
}

// ── UTILITIES ────────────────────────────────────────────────

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
