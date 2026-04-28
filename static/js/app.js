/* ============================================================
   IGD Simulation — Frontend Logic
   ============================================================ */

// Chart.js global defaults
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = 'rgba(99,102,241,0.08)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 8;
Chart.defaults.plugins.legend.labels.padding = 16;
Chart.defaults.animation.duration = 800;

// Scenario colors
const COLORS = {
  scenarios: [
    { bg: 'rgba(99,102,241,0.7)',  border: '#6366f1', label: 'Baseline' },
    { bg: 'rgba(34,197,94,0.7)',   border: '#22c55e', label: '+1 Dokter' },
    { bg: 'rgba(245,158,11,0.7)',  border: '#f59e0b', label: '+2 Perawat' },
    { bg: 'rgba(239,68,68,0.7)',   border: '#ef4444', label: 'Wabah 2×' },
  ],
  priority: {
    Merah:  { bg: 'rgba(239,68,68,0.6)',  border: '#ef4444' },
    Kuning: { bg: 'rgba(245,158,11,0.6)', border: '#f59e0b' },
    Hijau:  { bg: 'rgba(34,197,94,0.6)',  border: '#22c55e' },
  }
};

// Chart instances
let chartWait, chartQueue, chartUtil, chartDist;

// ---- DOM refs ----
const $ = (sel) => document.querySelector(sel);
const btnRun       = $('#btn-run');
const overlay      = $('#loading-overlay');
const inpPerawat   = $('#inp-perawat');
const inpDokter    = $('#inp-dokter');
const inpBed       = $('#inp-bed');
const inpInterval  = $('#inp-interval');
const inpDuration  = $('#inp-duration');

// ---- Adjuster buttons (supports float steps) ----
function initAdjButtons() {
  document.querySelectorAll('.btn-adj').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      if (!input) return;
      const step = parseFloat(btn.dataset.step || '1');
      const dir = parseFloat(btn.dataset.dir) > 0 ? 1 : -1;
      const val = parseFloat(input.value) + dir * step;
      const min = parseFloat(input.min);
      const max = parseFloat(input.max);
      if (val >= min && val <= max) {
        input.value = step % 1 === 0 ? Math.round(val) : val.toFixed(1);
      }
    });
  });
}
initAdjButtons();

// ---- Build scenarios from UI ----
function buildScenarios() {
  const p   = parseInt(inpPerawat.value);
  const d   = parseInt(inpDokter.value);
  const b   = parseInt(inpBed.value);
  const iv  = parseFloat(inpInterval.value);
  const dur = parseInt(inpDuration.value);

  // Baseline always included
  const scenarios = [
    { label: 'Baseline', num_perawat: p, num_dokter: d, num_bed: b, interval: iv, duration: dur }
  ];

  // Read each scenario card
  for (let idx = 1; idx <= 3; idx++) {
    const chk = document.querySelector(`.chk-scenario[data-idx="${idx}"]`);
    if (!chk || !chk.checked) continue;

    const name = document.querySelector(`.sc-name[data-idx="${idx}"]`);
    const dp   = document.getElementById(`sc${idx}-dp`);
    const dd   = document.getElementById(`sc${idx}-dd`);
    const db   = document.getElementById(`sc${idx}-db`);
    const mul  = document.getElementById(`sc${idx}-mul`);

    const label      = name ? name.value.trim() || `Skenario ${idx}` : `Skenario ${idx}`;
    const dPerawat   = dp  ? parseInt(dp.value)    || 0 : 0;
    const dDokter    = dd  ? parseInt(dd.value)    || 0 : 0;
    const dBed       = db  ? parseInt(db.value)    || 0 : 0;
    const multiplier = mul ? parseFloat(mul.value) || 1 : 1;

    scenarios.push({
      label:       label,
      num_perawat: Math.max(1, p + dPerawat),
      num_dokter:  Math.max(1, d + dDokter),
      num_bed:     Math.max(1, b + dBed),
      interval:    Math.max(0.5, iv / multiplier),
      duration:    dur,
    });
  }
  return scenarios;
}

// ---- API call ----
async function runSimulation() {
  const scenarios = buildScenarios();
  overlay.classList.remove('hidden');
  btnRun.disabled = true;

  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenarios }),
    });
    const data = await res.json();
    renderResults(data.results);
  } catch (err) {
    console.error('Simulation error:', err);
    alert('Gagal menjalankan simulasi. Pastikan server berjalan.');
  } finally {
    setTimeout(() => {
      overlay.classList.add('hidden');
      btnRun.disabled = false;
    }, 300);
  }
}

// ---- Render all results ----
function renderResults(results) {
  if (!results || results.length === 0) return;
  const baseline = results[0];

  updateStats(baseline);
  updateWaitChart(results);
  updateQueueChart(results);
  updateUtilChart(results);
  updateDistChart(baseline);
  updateTable(results);
  updateConclusion(results);
}

// ---- Stat cards with count-up ----
function animateValue(el, target, suffix = '') {
  const start = parseFloat(el.textContent) || 0;
  const dur = 600;
  const t0 = performance.now();

  function tick(now) {
    const progress = Math.min((now - t0) / dur, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const current = start + (target - start) * ease;
    el.textContent = (Number.isInteger(target) ? Math.round(current) : current.toFixed(1)) + suffix;
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function updateStats(b) {
  animateValue($('#stat-total'), b.total_pasien);
  animateValue($('#stat-wait'), b.mean_wait_all, ' mnt');
  animateValue($('#stat-util'), b.utilisasi_mean, '%');
  animateValue($('#stat-critical'), b.max_wait_critical, ' mnt');
}

// ---- Chart: Wait time comparison (grouped bar) ----
function updateWaitChart(results) {
  const labels = ['Merah', 'Kuning', 'Hijau'];
  const datasets = results.map((r, i) => ({
    label: r.label,
    data: labels.map(p => r.per_prioritas[p].mean_wait),
    backgroundColor: COLORS.scenarios[i]?.bg || 'rgba(150,150,150,0.5)',
    borderColor: COLORS.scenarios[i]?.border || '#999',
    borderWidth: 1,
    borderRadius: 6,
    maxBarThickness: 40,
  }));

  if (chartWait) {
    chartWait.data.datasets = datasets;
    chartWait.update();
  } else {
    chartWait = new Chart($('#chart-wait'), {
      type: 'bar',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)} mnt`
            }
          }
        },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Waktu Tunggu (mnt)' } }
        }
      }
    });
  }
}

// ---- Chart: Queue over time (line) ----
function updateQueueChart(results) {
  const datasets = results.map((r, i) => ({
    label: r.label,
    data: r.antrean_t.map((t, j) => ({ x: t, y: r.antrean_total[j] })),
    borderColor: COLORS.scenarios[i]?.border || '#999',
    backgroundColor: 'transparent',
    borderWidth: 1.8,
    pointRadius: 0,
    tension: 0.3,
  }));

  if (chartQueue) {
    chartQueue.data.datasets = datasets;
    chartQueue.update();
  } else {
    chartQueue = new Chart($('#chart-queue'), {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          tooltip: {
            callbacks: {
              title: items => `Menit ke-${items[0].parsed.x}`,
              label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y} pasien`
            }
          }
        },
        scales: {
          x: { type: 'linear', title: { display: true, text: 'Waktu (menit)' } },
          y: { beginAtZero: true, title: { display: true, text: 'Jumlah dalam Antrean' } }
        }
      }
    });
  }
}

// ---- Chart: Doctor utilization (line) ----
function updateUtilChart(results) {
  const datasets = results.map((r, i) => ({
    label: r.label,
    data: r.util_t.map((t, j) => ({ x: t, y: r.util_v[j] })),
    borderColor: COLORS.scenarios[i]?.border || '#999',
    backgroundColor: 'transparent',
    borderWidth: 1.8,
    pointRadius: 0,
    tension: 0.3,
  }));

  // Add 100% capacity line
  datasets.push({
    label: 'Kapasitas Penuh',
    data: [{ x: 0, y: 100 }, { x: results[0].util_t.slice(-1)[0] || 480, y: 100 }],
    borderColor: 'rgba(239,68,68,0.4)',
    borderDash: [6, 4],
    borderWidth: 1.5,
    pointRadius: 0,
    fill: false,
  });

  if (chartUtil) {
    chartUtil.data.datasets = datasets;
    chartUtil.update();
  } else {
    chartUtil = new Chart($('#chart-util'), {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          tooltip: {
            callbacks: {
              title: items => `Menit ke-${items[0].parsed.x}`,
              label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`
            }
          }
        },
        scales: {
          x: { type: 'linear', title: { display: true, text: 'Waktu (menit)' } },
          y: { min: 0, max: 110, title: { display: true, text: 'Utilisasi (%)' } }
        }
      }
    });
  }
}

// ---- Chart: Wait time distribution (histogram) ----
function computeHistogram(values, numBins = 12) {
  if (!values || values.length === 0) return { labels: [], data: [] };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const w = (max - min) / numBins || 1;
  const bins = Array(numBins).fill(0);
  const labels = [];
  for (let i = 0; i < numBins; i++) {
    labels.push(`${Math.round(min + i * w)}`);
  }
  values.forEach(v => {
    const idx = Math.min(Math.floor((v - min) / w), numBins - 1);
    bins[idx]++;
  });
  return { labels, data: bins };
}

function updateDistChart(baseline) {
  const priorities = ['Merah', 'Kuning', 'Hijau'];
  const datasets = priorities.map(p => {
    const hist = computeHistogram(baseline.per_prioritas[p].wait_times);
    return {
      label: p,
      data: hist.data,
      backgroundColor: COLORS.priority[p].bg,
      borderColor: COLORS.priority[p].border,
      borderWidth: 1,
      borderRadius: 4,
    };
  });
  // Use labels from the priority with the most data
  let maxLabels = [];
  priorities.forEach(p => {
    const h = computeHistogram(baseline.per_prioritas[p].wait_times);
    if (h.labels.length > maxLabels.length) maxLabels = h.labels;
  });

  // Recompute with uniform bins across all priorities
  const allWaits = priorities.flatMap(p => baseline.per_prioritas[p].wait_times);
  const globalMin = Math.min(...allWaits);
  const globalMax = Math.max(...allWaits);
  const numBins = 15;
  const binW = (globalMax - globalMin) / numBins || 1;
  const globalLabels = [];
  for (let i = 0; i < numBins; i++) {
    globalLabels.push(`${Math.round(globalMin + i * binW)}`);
  }

  const uniformDatasets = priorities.map(p => {
    const waits = baseline.per_prioritas[p].wait_times;
    const bins = Array(numBins).fill(0);
    waits.forEach(v => {
      const idx = Math.min(Math.floor((v - globalMin) / binW), numBins - 1);
      bins[idx]++;
    });
    return {
      label: p,
      data: bins,
      backgroundColor: COLORS.priority[p].bg,
      borderColor: COLORS.priority[p].border,
      borderWidth: 1,
      borderRadius: 3,
    };
  });

  if (chartDist) {
    chartDist.data.labels = globalLabels;
    chartDist.data.datasets = uniformDatasets;
    chartDist.update();
  } else {
    chartDist = new Chart($('#chart-dist'), {
      type: 'bar',
      data: { labels: globalLabels, datasets: uniformDatasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: {
            callbacks: {
              title: items => `Waktu tunggu ~${items[0].label} mnt`,
              label: ctx => `${ctx.dataset.label}: ${ctx.raw} pasien`
            }
          }
        },
        scales: {
          x: { title: { display: true, text: 'Waktu Tunggu (mnt)' } },
          y: { beginAtZero: true, title: { display: true, text: 'Jumlah Pasien' } }
        }
      }
    });
  }
}

// ---- Comparison Table ----
function updateTable(results) {
  const tbody = $('#tbl-body');
  tbody.innerHTML = '';

  results.forEach((r, i) => {
    const merah  = r.per_prioritas.Merah;
    const kuning = r.per_prioritas.Kuning;
    const hijau  = r.per_prioritas.Hijau;

    let statusClass, statusText;
    if (r.utilisasi_mean > 95) {
      statusClass = 'status-danger';
      statusText = 'Overload';
    } else if (r.utilisasi_mean > 80) {
      statusClass = 'status-warn';
      statusText = 'Tinggi';
    } else {
      statusClass = 'status-ok';
      statusText = 'Stabil';
    }

    const colorDot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${COLORS.scenarios[i]?.border || '#999'};margin-right:8px;"></span>`;

    tbody.innerHTML += `
      <tr>
        <td>${colorDot}<strong>${r.label}</strong></td>
        <td>${r.total_pasien}</td>
        <td class="col-merah">${merah.mean_wait} <small style="color:var(--text-3)">(max ${merah.max_wait})</small></td>
        <td class="col-kuning">${kuning.mean_wait} <small style="color:var(--text-3)">(max ${kuning.max_wait})</small></td>
        <td class="col-hijau">${hijau.mean_wait} <small style="color:var(--text-3)">(max ${hijau.max_wait})</small></td>
        <td>${r.utilisasi_mean}%</td>
        <td><span class="status-badge ${statusClass}">${statusText}</span></td>
      </tr>
    `;
  });
}

// ---- Conclusion ----
function updateConclusion(results) {
  const section = $('#conclusion');
  const textEl  = $('#conclusion-text');
  section.style.display = 'block';

  const baseline = results[0];
  const others   = results.slice(1);

  let html = `<p>Simulasi berjalan selama <strong>${baseline.antrean_t.slice(-1)[0] || 480} menit</strong> dengan
    total <strong>${baseline.total_pasien} pasien</strong> dilayani pada skenario baseline.</p>`;

  if (others.length > 0) {
    // Find the best scenario (lowest mean wait)
    const best = others.reduce((a, b) => a.mean_wait_all < b.mean_wait_all ? a : b);
    const worst = others.reduce((a, b) => a.mean_wait_all > b.mean_wait_all ? a : b);

    html += `<p><strong>Perbandingan:</strong> Dari ${others.length} skenario what-if,
      <span class="highlight hl-green">${best.label}</span> paling efektif
      menurunkan waktu tunggu (rata-rata ${best.mean_wait_all} mnt vs baseline ${baseline.mean_wait_all} mnt).
      Waktu tunggu pasien <strong>Merah (kritis)</strong> turun dari
      ${baseline.per_prioritas.Merah.mean_wait} mnt menjadi ${best.per_prioritas.Merah.mean_wait} mnt.</p>`;

    // Check for any overloaded scenarios
    const overloaded = others.filter(r => r.utilisasi_mean > 95);
    if (overloaded.length > 0) {
      const names = overloaded.map(r => `<span class="highlight hl-red">${r.label}</span>`).join(', ');
      html += `<p><strong>Peringatan:</strong> Skenario ${names} menunjukkan sistem
        <strong>mendekati/melebihi kapasitas</strong> (utilisasi >95%).
        Penambahan resource sangat dibutuhkan pada kondisi ini.</p>`;
    }
  }

  html += `<p style="margin-top:12px;color:var(--text-3);font-style:italic;">
    * Model kasar — parameter dapat di-tune berdasarkan data riil rumah sakit.</p>`;

  textEl.innerHTML = html;
}

// ---- Init ----
btnRun.addEventListener('click', runSimulation);

// Auto-run on load
window.addEventListener('DOMContentLoaded', () => {
  setTimeout(runSimulation, 400);
});
