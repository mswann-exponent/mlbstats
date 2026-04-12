let currentPlayers = [];
let currentSortKey = "hits";
let currentSortDir = "desc";

function getFilters() {
  return {
    season: document.getElementById('season').value,
    start_date: document.getElementById('start_date').value,
    end_date: document.getElementById('end_date').value
  };
}

function buildQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.append(key, value);
  });
  return query.toString();
}

function formatDecimal(value, digits = 3) {
  const num = Number(value || 0);
  return num.toFixed(digits);
}

function sortPlayers(players, key, dir) {
  const sorted = [...players].sort((a, b) => {
    const av = a[key];
    const bv = b[key];

    const aNum = Number(av);
    const bNum = Number(bv);
    const bothNumeric = !Number.isNaN(aNum) && !Number.isNaN(bNum);

    let cmp = 0;
    if (bothNumeric) {
      cmp = aNum - bNum;
    } else {
      cmp = String(av ?? "").localeCompare(String(bv ?? ""));
    }

    return dir === "asc" ? cmp : -cmp;
  });

  return sorted;
}

function renderTable(players) {
  const body = document.getElementById('tableBody');
  const sorted = sortPlayers(players, currentSortKey, currentSortDir);

  body.innerHTML = sorted.map(p => `
    <tr>
      <td class="name">${p.full_name || ''}</td>
      <td class="team">${p.current_team || ''}</td>
      <td class="pos">${p.position || ''}</td>
      <td>${p.hits ?? 0}</td>
      <td>${p.home_runs ?? 0}</td>
      <td>${p.rbi ?? 0}</td>
      <td>${formatDecimal(p.avg, 3)}</td>
      <td>${p.runs ?? 0}</td>
      <td>${p.stolen_bases ?? 0}</td>
      <td>${p.wins ?? 0}</td>
      <td>${p.pitching_strikeouts ?? 0}</td>
      <td>${p.saves ?? 0}</td>
    </tr>
  `).join('');
}

async function loadStats() {
  const filters = getFilters();
  const qs = buildQuery(filters);

  document.getElementById('status').textContent = 'Loading aggregate stats...';

  const res = await fetch(`/api/stats?${qs}`);
  const data = await res.json();

  currentPlayers = data.players || [];
  renderTable(currentPlayers);

  document.getElementById('status').textContent =
    `Loaded ${data.count} aggregate player rows for season ${filters.season}.`;
}

function downloadCSV() {
  const filters = getFilters();
  const qs = buildQuery(filters);
  window.location.href = `/download.csv?${qs}`;
}

async function setLast7Days() {
  const res = await fetch('/api/date-presets');
  const data = await res.json();
  document.getElementById('start_date').value = data.last_7;
  document.getElementById('end_date').value = data.today;
  loadStats();
}

async function setLast30Days() {
  const res = await fetch('/api/date-presets');
  const data = await res.json();
  document.getElementById('start_date').value = data.last_30;
  document.getElementById('end_date').value = data.today;
  loadStats();
}

function setSeasonToDate() {
  const season = document.getElementById('season').value;
  document.getElementById('start_date').value = `${season}-01-01`;
  document.getElementById('end_date').value = '';
  loadStats();
}

function clearDates() {
  document.getElementById('start_date').value = '';
  document.getElementById('end_date').value = '';
  loadStats();
}

function attachSortHandlers() {
  const headers = document.querySelectorAll('#statsTable th[data-key]');
  headers.forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (currentSortKey === key) {
        currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
      } else {
        currentSortKey = key;
        currentSortDir = 'desc';
      }
      renderTable(currentPlayers);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  attachSortHandlers();
  loadStats();
});
