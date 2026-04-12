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

async function loadStats() {
  const filters = getFilters();
  const qs = buildQuery(filters);

  document.getElementById('status').textContent = 'Loading aggregate stats...';

  const res = await fetch(`/api/stats?${qs}`);
  const data = await res.json();

  const body = document.getElementById('tableBody');
  body.innerHTML = data.players.map(p => `
    <tr>
      <td class="name">${p.full_name || ''}</td>
      <td class="team">${p.current_team || ''}</td>
      <td class="pos">${p.position || ''}</td>
      <td>${formatDecimal(p.avg, 3)}</td>
      <td>${formatDecimal(p.obp, 3)}</td>
      <td>${formatDecimal(p.slg, 3)}</td>
      <td>${formatDecimal(p.ops, 3)}</td>
      <td>${p.hits ?? 0}</td>
      <td>${p.at_bats ?? 0}</td>
      <td>${p.home_runs ?? 0}</td>
      <td>${p.rbi ?? 0}</td>
      <td>${p.stolen_bases ?? 0}</td>
      <td>${p.walks ?? 0}</td>
      <td>${p.hitting_strikeouts ?? 0}</td>
      <td>${Number(p.era ?? 0).toFixed(2)}</td>
      <td>${formatDecimal(p.whip, 3)}</td>
      <td>${p.pitching_strikeouts ?? 0}</td>
      <td>${p.innings_pitched ?? 0}</td>
      <td>${p.wins ?? 0}</td>
      <td>${p.losses ?? 0}</td>
      <td>${p.saves ?? 0}</td>
    </tr>
  `).join('');

  document.getElementById('status').textContent = `Loaded ${data.count} aggregate player stat rows.`;
}

function downloadCSV() {
  const filters = getFilters();
  const qs = buildQuery(filters);
  window.location.href = `/download.csv?${qs}`;
}
