import json
import time
import re
import os
import webbrowser
from playwright.sync_api import sync_playwright


def clean_cia_text(text):
    if not text:
        return ""
    text = text.replace('\xa0', ' ').replace('|', ' ')
    abbreviations = {
        r"\bAdm\b": "Admiral", r"\bAdmin\b": "Administrative", r"\bAsst\b": "Assistant",
        r"\bBrig\b": "Brigadier", r"\bCapt\b": "Captain", r"\bCdr\b": "Commander",
        r"\bCdte\b": "Comandante", r"\bChmn\.?(?![a-z])": "Chairman", r"\bCol\b": "Colonel",
        r"\bCtte\b": "Committee", r"\bDel\b": "Delegate", r"\bDep\b": "Deputy",
        r"\bDept\b": "Department", r"\bDir\b": "Director", r"\bDiv\b": "Division",
        r"\bDr\b": "Doctor", r"\bEng\b": "Engineer", r"\bFd\. Mar\b": "Field Marshal",
        r"\bFed\b": "Federal", r"\bGen\b": "General", r"\bGovt\.?": "Government", r"\bGovt\b": "Government",
        r"\bIntl\b": "International", r"\bLt\b": "Lieutenant", r"\bMaj\b": "Major",
        r"\bMar\b": "Marshal", r"\bMbr\b": "Member", r"\bMin\b": "Minister",
        r"\bNDE\b": "No Diplomatic Exchange", r"\bOrg\b": "Organization",
        r"\bPres\.?(?![a-z])": "President", r"\bProf\b": "Professor", r"\bRAdm\b": "Rear Admiral",
        r"\bRet\b": "Retired", r"\bSec\b": "Secretary", r"\bVAdm\b": "Vice Admiral",
        r"\bVMar\b": "Vice Marshal"
    }
    cleaned = text
    for abbrev, full in abbreviations.items():
        cleaned = re.sub(abbrev, full, cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', cleaned).strip()


def is_top_leader(role):
    role_lower = role.lower().strip()
    role_normalized = role_lower.rstrip(".")

    DISQUALIFIERS = [
        "deputy", "vice", "assistant", "minister of", "minister for",
        "head of office", "head of cabinet", "cabinet",
        "central bank", "national bank", "director", "chief of staff",
        "acting minister", "exchequer", "representative"
    ]
    if any(d in role_lower for d in DISQUALIFIERS):
        return False

    if role_normalized.startswith("president"):
        remainder = role_normalized[len("president"):].strip()
        if not remainder:
            return True
        if remainder.startswith("("):
            return True
        ALLOWED_SUFFIXES = [
            "of the republic", "of the state", "of the bolivarian",
            "of the transitional", "of the federal", "of the islamic",
            ", state affairs commission",
            ", swiss confederation",
        ]
        if any(remainder.startswith(s) for s in ALLOWED_SUFFIXES):
            return True
        return False

    HEAD_ROLES = [
        "prime minister", "king", "queen", "chancellor",
        "emperor", "supreme leader", "supreme pontiff",
        "sovereign", "amir", "sultan",
        "governor general", "grand duke",
        "prince", "captain regent",
        "head of state", "head of government", "chief of state",
        "federal councillor",
        "general secretary",
        "chairman, sovereignty council",
        "president, state affairs commission",
        "governor",
        "premier",
        "acting president",
        "acting prime minister",
    ]
    return any(role_normalized == r or role_normalized.startswith(r) for r in HEAD_ROLES)


def generate_html_report(data, output_path):
    """Writes a static HTML shell; all data is loaded at runtime from top_world_leaders.json."""

    # Used only for the console summary printed below — not embedded in HTML.
    total_countries = len(data)
    total_leaders = sum(len(c["leaders"]) for c in data)
    print(f"  Stats: {total_countries} countries, {total_leaders} leaders (fetched dynamically at runtime)")

    html = """\
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>World Leaders — CIA Intelligence Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0c0f;
    --surface: #111318;
    --surface2: #181c23;
    --border: #1e2530;
    --border-bright: #2a3545;
    --text: #d4dbe8;
    --text-muted: #4a5568;
    --text-dim: #2d3748;
    --accent: #c8a96e;
    --accent2: #5b9bd5;
    --green: #4ade80;
    --red: #f87171;
    --purple: #a78bfa;
    --gold: #fbbf24;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 14px;
    line-height: 1.6;
    min-height: 100vh;
  }

  /* ── HEADER ── */
  .header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 28px 40px 24px;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(8px);
  }

  .header-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    flex-wrap: wrap;
  }

  .title-block { display: flex; flex-direction: column; gap: 4px; }

  .classified-tag {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.2em;
    color: var(--accent);
    text-transform: uppercase;
    border: 1px solid var(--accent);
    padding: 2px 8px;
    display: inline-block;
    width: fit-content;
    margin-bottom: 6px;
    opacity: 0.9;
  }

  h1 {
    font-family: 'DM Serif Display', serif;
    font-size: 32px;
    font-weight: 400;
    color: #e8edf5;
    letter-spacing: -0.02em;
    line-height: 1.1;
  }

  h1 em {
    font-style: italic;
    color: var(--accent);
  }

  .subtitle {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.05em;
    margin-top: 2px;
  }

  .stats-row {
    display: flex;
    gap: 28px;
    align-items: center;
    flex-wrap: wrap;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .stat-num {
    font-family: 'DM Serif Display', serif;
    font-size: 28px;
    color: var(--accent);
    line-height: 1;
  }

  .stat-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }

  .stat-divider {
    width: 1px;
    height: 32px;
    background: var(--border-bright);
  }

  /* ── CONTROLS ── */
  .controls {
    padding: 16px 40px;
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }

  .search-wrapper {
    position: relative;
    flex: 1;
    min-width: 220px;
    max-width: 380px;
  }

  .search-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    font-size: 13px;
    pointer-events: none;
  }

  input[type="text"] {
    width: 100%;
    background: var(--surface2);
    border: 1px solid var(--border-bright);
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    padding: 8px 12px 8px 34px;
    outline: none;
    transition: border-color 0.2s;
  }

  input[type="text"]:focus { border-color: var(--accent); }
  input[type="text"]::placeholder { color: var(--text-dim); }

  .filter-btn {
    background: var(--surface2);
    border: 1px solid var(--border-bright);
    color: var(--text-muted);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.08em;
    padding: 8px 14px;
    cursor: pointer;
    transition: all 0.15s;
    text-transform: uppercase;
  }

  .filter-btn:hover { border-color: var(--accent); color: var(--accent); }
  .filter-btn.active { background: var(--accent); color: #0a0c0f; border-color: var(--accent); font-weight: 500; }

  .result-count {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
    margin-left: auto;
  }

  .result-count span { color: var(--accent); }

  /* ── TABLE ── */
  .table-wrapper {
    padding: 0 40px 60px;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 24px;
    table-layout: fixed;
  }

  thead th:nth-child(1), td:nth-child(1) { width: 25%; }
  thead th:nth-child(2), td:nth-child(2) { width: 35%; }
  thead th:nth-child(3), td:nth-child(3) { width: 40%; }

  thead th {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--text-muted);
    padding: 10px 16px;
    text-align: left;
    border-bottom: 1px solid var(--border-bright);
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    transition: color 0.15s;
  }

  thead th:hover { color: var(--accent); }

  thead th .sort-indicator { margin-left: 4px; opacity: 0.4; }
  thead th.sort-asc .sort-indicator::after { content: ' ↑'; opacity: 1; color: var(--accent); }
  thead th.sort-desc .sort-indicator::after { content: ' ↓'; opacity: 1; color: var(--accent); }

  .data-row {
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }

  .data-row:hover { background: var(--surface2); }
  .data-row.hidden { display: none; }

  td {
    padding: 11px 16px;
    vertical-align: middle;
  }

  .country-cell {
    font-weight: 500;
    color: #c5cfe0;
    white-space: nowrap;
    min-width: 180px;
  }

  .country-cell.muted { color: transparent; }

  .flag { margin-right: 8px; font-size: 16px; }

  .leader-name {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    color: var(--text);
    letter-spacing: 0.02em;
  }

  .role-badge {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    padding: 3px 9px;
    border-radius: 2px;
    letter-spacing: 0.04em;
    font-weight: 500;
    white-space: nowrap;
  }

  .role-president  { background: rgba(91,155,213,0.15); color: #7db8e8; border: 1px solid rgba(91,155,213,0.3); }
  .role-pm         { background: rgba(74,222,128,0.12); color: #6ed99a; border: 1px solid rgba(74,222,128,0.25); }
  .role-king       { background: rgba(251,191,36,0.12); color: #f0c04a; border: 1px solid rgba(251,191,36,0.25); }
  .role-other      { background: rgba(167,139,250,0.12); color: #b8a4f5; border: 1px solid rgba(167,139,250,0.25); }

  /* ── LEGEND ── */
  .legend {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    padding: 0 40px 0;
    margin-top: 16px;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 11px;
    color: var(--text-muted);
    font-family: 'IBM Plex Mono', monospace;
  }

  /* ── LOADING / EMPTY STATE ── */
  .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    display: none;
  }

  .empty-state.visible { display: block; }

  /* ── FOOTER ── */
  .footer {
    padding: 20px 40px;
    border-top: 1px solid var(--border);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--text-dim);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    display: flex;
    justify-content: space-between;
  }

  /* ── ANIMATIONS ── */
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .data-row { animation: fadeIn 0.3s ease forwards; }
  .data-row:nth-child(1)  { animation-delay: 0.02s; }
  .data-row:nth-child(5)  { animation-delay: 0.05s; }
  .data-row:nth-child(10) { animation-delay: 0.08s; }
  .data-row:nth-child(20) { animation-delay: 0.12s; }
  .data-row:nth-child(40) { animation-delay: 0.18s; }
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div class="title-block">
      <div class="classified-tag">CIA · World Leaders Database</div>
      <h1>Foreign <em>Governments</em></h1>
      <div class="subtitle">SOURCE: cia.gov/resources/world-leaders · HEADS OF STATE &amp; GOVERNMENT ONLY</div>
    </div>
    <div class="stats-row">
      <div class="stat">
        <div class="stat-num" id="statCountries">—</div>
        <div class="stat-label">Countries</div>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <div class="stat-num" id="statLeaders">—</div>
        <div class="stat-label">Leaders</div>
      </div>
    </div>
  </div>
</div>

<div class="controls">
  <div class="search-wrapper">
    <span class="search-icon">⌕</span>
    <input type="text" id="searchInput" placeholder="Search country or name...">
  </div>
  <button class="filter-btn active" data-filter="all">All</button>
  <button class="filter-btn" data-filter="president">Presidents</button>
  <button class="filter-btn" data-filter="prime minister">Prime Ministers</button>
  <button class="filter-btn" data-filter="king|queen|sultan|amir|emperor">Monarchs</button>
  <div class="result-count" id="resultCount"><span id="visibleCount">—</span> leaders shown</div>
</div>

<div class="legend">
  <div class="legend-item"><span class="role-badge role-president">President</span></div>
  <div class="legend-item"><span class="role-badge role-pm">Prime Minister</span></div>
  <div class="legend-item"><span class="role-badge role-king">Monarch / Ruler</span></div>
  <div class="legend-item"><span class="role-badge role-other">Other Head</span></div>
</div>

<div class="table-wrapper">
  <table id="leadersTable">
    <thead>
      <tr>
        <th data-col="country">Country <span class="sort-indicator"></span></th>
        <th data-col="role">Role <span class="sort-indicator"></span></th>
        <th data-col="name">Name <span class="sort-indicator"></span></th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
  <div class="empty-state" id="emptyState">
    NO RECORDS MATCH — ADJUST FILTERS
  </div>
</div>

<div class="footer">
  <span id="footerDate">Generated from CIA World Leaders</span>
  <span>Filtered: Heads of State &amp; Government only</span>
</div>

<script>
  const FLAGS = {
    "United States": "🇺🇸", "China": "🇨🇳", "Russia": "🇷🇺", "Germany": "🇩🇪",
    "France": "🇫🇷", "United Kingdom": "🇬🇧", "Japan": "🇯🇵", "India": "🇮🇳",
    "Brazil": "🇧🇷", "Canada": "🇨🇦", "Australia": "🇦🇺", "Italy": "🇮🇹",
    "South Korea": "🇰🇷", "Spain": "🇪🇸", "Mexico": "🇲🇽", "Indonesia": "🇮🇩",
    "Turkey": "🇹🇷", "Saudi Arabia": "🇸🇦", "Netherlands": "🇳🇱", "Switzerland": "🇨🇭",
    "Israel": "🇮🇱", "Iran": "🇮🇷", "Egypt": "🇪🇬", "Pakistan": "🇵🇰",
    "Argentina": "🇦🇷", "Nigeria": "🇳🇬", "South Africa": "🇿🇦", "Ukraine": "🇺🇦",
    "Poland": "🇵🇱", "Sweden": "🇸🇪", "Norway": "🇳🇴", "Denmark": "🇩🇰",
    "Finland": "🇫🇮", "Belgium": "🇧🇪", "Austria": "🇦🇹", "Portugal": "🇵🇹",
    "Greece": "🇬🇷", "Czech Republic": "🇨🇿", "Romania": "🇷🇴", "Hungary": "🇭🇺",
    "Iraq": "🇮🇶", "Syria": "🇸🇾", "Jordan": "🇯🇴", "Lebanon": "🇱🇧",
    "Qatar": "🇶🇦", "Kuwait": "🇰🇼", "UAE": "🇦🇪", "Bahrain": "🇧🇭",
    "United Arab Emirates": "🇦🇪", "Afghanistan": "🇦🇫", "Bangladesh": "🇧🇩",
    "Thailand": "🇹🇭", "Vietnam": "🇻🇳", "Philippines": "🇵🇭", "Malaysia": "🇲🇾",
    "Singapore": "🇸🇬", "New Zealand": "🇳🇿", "Colombia": "🇨🇴", "Chile": "🇨🇱",
    "Peru": "🇵🇪", "Venezuela": "🇻🇪", "Cuba": "🇨🇺", "Morocco": "🇲🇦",
    "Algeria": "🇩🇿", "Tunisia": "🇹🇳", "Libya": "🇱🇾", "Sudan": "🇸🇩",
    "Ethiopia": "🇪🇹", "Kenya": "🇰🇪", "Ghana": "🇬🇭", "Tanzania": "🇹🇿",
    "North Korea": "🇰🇵", "Myanmar": "🇲🇲", "Sri Lanka": "🇱🇰"
  };

  function getRoleClass(role) {
    const r = role.toLowerCase();
    if (r.includes('president')) return 'role-president';
    if (r.includes('prime minister')) return 'role-pm';
    if (['king', 'queen', 'sultan', 'amir', 'emperor'].some(k => r.includes(k))) return 'role-king';
    return 'role-other';
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderTable(data) {
    const totalCountries = data.length;
    const totalLeaders = data.reduce((sum, c) => sum + c.leaders.length, 0);

    document.getElementById('statCountries').textContent = totalCountries;
    document.getElementById('statLeaders').textContent = totalLeaders;
    document.getElementById('visibleCount').textContent = totalLeaders;

    const tbody = document.getElementById('tableBody');
    let html = '';

    data.forEach(country => {
      const flag = FLAGS[country.country] || '🌐';
      const escapedCountry = escapeHtml(country.country);

      country.leaders.forEach((leader, j) => {
        const roleClass = getRoleClass(leader.role);
        const escapedRole = escapeHtml(leader.role);
        const escapedName = escapeHtml(leader.name);

        const countryCell = j === 0
          ? `<td class="country-cell"><span class="flag">${flag}</span>${escapedCountry}</td>`
          : `<td class="country-cell muted"></td>`;

        html += `
        <tr class="data-row"
            data-country="${escapedCountry.toLowerCase()}"
            data-role="${escapedRole.toLowerCase()}">
          ${countryCell}
          <td><span class="role-badge ${roleClass}">${escapedRole}</span></td>
          <td class="leader-name">${escapedName}</td>
        </tr>`;
      });
    });

    tbody.innerHTML = html;
  }

  function setupInteractivity() {
    const tbody = document.getElementById('tableBody');
    const searchInput = document.getElementById('searchInput');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const visibleCount = document.getElementById('visibleCount');
    const emptyState = document.getElementById('emptyState');

    let currentFilter = 'all';
    let currentSearch = '';
    let sortCol = null;
    let sortAsc = true;

    function getRows() {
      return Array.from(tbody.querySelectorAll('.data-row'));
    }

    function applyFilters() {
      const rows = getRows();
      let visible = 0;

      rows.forEach(row => {
        const country = row.dataset.country || '';
        const role = row.dataset.role || '';
        const name = row.querySelector('.leader-name')?.textContent.toLowerCase() || '';

        const matchSearch = !currentSearch ||
          country.includes(currentSearch) ||
          role.includes(currentSearch) ||
          name.includes(currentSearch);

        const matchFilter = currentFilter === 'all' ||
          new RegExp(currentFilter).test(role);

        if (matchSearch && matchFilter) {
          row.classList.remove('hidden');
          visible++;
        } else {
          row.classList.add('hidden');
        }
      });

      visibleCount.textContent = visible;
      emptyState.classList.toggle('visible', visible === 0);
    }

    searchInput.addEventListener('input', e => {
      currentSearch = e.target.value.toLowerCase().trim();
      applyFilters();
    });

    filterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        applyFilters();
      });
    });

    document.querySelectorAll('thead th[data-col]').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        if (sortCol === col) { sortAsc = !sortAsc; }
        else { sortCol = col; sortAsc = true; }

        document.querySelectorAll('thead th').forEach(t => {
          t.classList.remove('sort-asc', 'sort-desc');
        });
        th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');

        const allRows = getRows();
        allRows.sort((a, b) => {
          let va = '', vb = '';
          if (col === 'country') {
            va = a.dataset.country; vb = b.dataset.country;
          } else if (col === 'role') {
            va = a.dataset.role; vb = b.dataset.role;
          } else {
            va = a.querySelector('.leader-name')?.textContent.toLowerCase() || '';
            vb = b.querySelector('.leader-name')?.textContent.toLowerCase() || '';
          }
          return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
        });

        allRows.forEach(r => tbody.appendChild(r));
        applyFilters();
      });
    });
  }

  async function init() {
    const emptyState = document.getElementById('emptyState');
    try {
      const res = await fetch('top_world_leaders.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      renderTable(data);
      setupInteractivity();

      const now = new Date();
      const pad = n => String(n).padStart(2, '0');
      const ts = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
      document.getElementById('footerDate').textContent =
        `Generated from CIA World Leaders · ${ts}`;

    } catch (err) {
      console.error('Failed to load world leaders data:', err);
      emptyState.textContent = 'FAILED TO LOAD DATA — ' + err.message;
      emptyState.classList.add('visible');
      document.getElementById('statCountries').textContent = 'ERR';
      document.getElementById('statLeaders').textContent = 'ERR';
    }
  }

  init();
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 HTML shell written: {output_path}")


def run_scraper():
    all_results = []
    base_url = "https://www.cia.gov"
    index_url = "https://www.cia.gov/resources/world-leaders/foreign-governments/"

    with sync_playwright() as p:
        headless = os.environ.get("CI", "false") == "true"
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        print("🔗 Loading index page...")
        page.goto(index_url, wait_until="networkidle")

        print("⚡ Selecting 'All' option...")
        try:
            page.select_option("select.per-page", label="All")
            page.wait_for_load_state("networkidle")
            time.sleep(3)
        except Exception:
            print("⚠️  Could not switch to 'All', continuing.")

        links = page.locator('main a[href*="/world-leaders/foreign-governments/"]').all()
        all_country_urls = []
        for l in links:
            href = l.get_attribute("href")
            if href and "/foreign-governments/" in href:
                full_path = base_url + href if href.startswith("/") else href
                if full_path.strip("/") != index_url.strip("/") and full_path not in all_country_urls:
                    all_country_urls.append(full_path)

        print(f"📊 Found {len(all_country_urls)} countries.")

        skipped = []
        failed = []

        for i, url in enumerate(all_country_urls):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                country_name = clean_cia_text(page.locator("h1").inner_text())
                leaders = []
                leader_elements = page.locator('.leader-info').all()

                seen = set()
                for el in leader_elements:
                    raw_text = el.inner_text().strip()
                    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                    if len(lines) >= 2:
                        role = clean_cia_text(lines[0])
                        name = clean_cia_text(lines[-1])
                        key = (role.lower(), name.lower())
                        if is_top_leader(role) and key not in seen:
                            seen.add(key)
                            leaders.append({"role": role, "name": name})

                if leaders:
                    all_results.append({"country": country_name, "leaders": leaders})
                    print(f"[{i+1}/{len(all_country_urls)}] ✅ {country_name}: {len(leaders)} leaders")
                else:
                    skipped.append(country_name)
                    first_roles = [clean_cia_text(el.inner_text().split('\n')[0]) for el in leader_elements[:3]]
                    print(f"[{i+1}/{len(all_country_urls)}] — {country_name}: filtered (roles found: {first_roles})")

            except Exception as e:
                failed.append(url)
                print(f"❌ Error at {url}: {e}")

        browser.close()

        print(f"\n📊 Summary:")
        print(f"  ✅ Countries with leaders: {len(all_results)}")
        print(f"  — Filtered (no matching roles): {len(skipped)}")
        for s in skipped:
            print(f"      • {s}")
        print(f"  ❌ Technical errors: {len(failed)}")
        for f_ in failed:
            print(f"      • {f_}")

    json_path = "top_world_leaders.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=4)
    print(f"\n💾 JSON saved: {json_path}")

    html_path = os.path.abspath("index.html")
    generate_html_report(all_results, html_path)

    if not os.environ.get("CI"):
        print(f"\n🌐 Opening report in browser...")
        webbrowser.open(f"file://{html_path}")

    print("\n✨ Scrape complete!")


if __name__ == "__main__":
    run_scraper()
