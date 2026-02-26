/* ── Global app state ────────────────────────────────────────────── */
let allSummoners     = [];
let activeSummonerId = null;
let activeMatches    = [];
let activeStats      = null;
let activeMode       = 'all';
let activeMatchEl    = null;
let activeRank       = null;
let chartWR = null, chartCH = null, chartDUR = null;

/* ── Chart colour palette for duration buckets ───────────────────── */
const DURATION_COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#6b7280'];

/* ── Duration task state ─────────────────────────────────────────── */
let durationPollTimer = null;
const durationCache   = {};

/* ── Heatmap task state ──────────────────────────────────────────── */
let heatmapPollTimer = null;
const heatmapCache   = {};
let _heatPalette     = null;

/* ── Timeline per-minute chart instances ──────────────────────────── */
let chartGoldPM = null, chartDamagePM = null, chartCSPM = null;

/* ── Match detail timeline chart instances ────────────────────────── */
let matchChartGold = null, matchChartDamage = null, matchChartCS = null;

/* ── Sync progress polling state ─────────────────────────────────── */
let syncPollTimer = null;

/* ── Modal autocomplete debounce ─────────────────────────────────── */
let acTimer = null;

/* ── Hash-based routing state ─────────────────────────────────────── */
let _suppressHashChange = false;

function _setHash(summoner, match) {
    _suppressHashChange = true;
    let h = '';
    if (summoner) {
        h = 'summoner=' + encodeURIComponent(summoner);
        if (match) h += '&match=' + encodeURIComponent(match);
    }
    window.location.hash = h;
    setTimeout(() => { _suppressHashChange = false; }, 0);
}

function _parseHash() {
    const h = window.location.hash.slice(1);
    const params = new URLSearchParams(h);
    return {
        summoner: params.get('summoner'),
        match:    params.get('match'),
    };
}

async function _navigateFromHash() {
    const { summoner, match } = _parseHash();
    console.log('[route] navigateFromHash:', { summoner, match, activeSummonerId });
    if (!summoner) {
        if (activeSummonerId) closeProfile();
        return;
    }
    try {
        // If summoner changed, select it
        if (summoner !== activeSummonerId) {
            // Wait for summoner list if not ready
            if (!allSummoners.length) await refreshSummonerList();
            // Find the li by data-riot-id
            let li = null;
            document.querySelectorAll('#summoner-list li').forEach(el => {
                if (el.dataset.riotId === summoner) li = el;
            });
            console.log('[route] selectSummoner from hash, li found:', !!li);
            await selectSummoner(summoner, li, true);
        }
        if (match && activeSummonerId) {
            // Find the match card by data-match-id
            let card = null;
            document.querySelectorAll('#match-history [data-match-id]').forEach(el => {
                if (el.dataset.matchId === match) card = el;
            });
            console.log('[route] selectMatch from hash, card found:', !!card);
            await selectMatch(match, card, true);
        } else if (!match && activeSummonerId && $('match-view') && !$('match-view').classList.contains('hidden')) {
            closeMatch();
        }
    } catch (e) {
        console.error('[route] Error navigating from hash:', e);
    }
}

function _copyShareLink(evt) {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
        const btn = evt && evt.currentTarget ? evt.currentTarget : document.querySelector('.share-btn');
        if (btn) {
            const orig = btn.innerHTML;
            btn.innerHTML = '<span class="text-emerald-400">✓ Copied!</span>';
            setTimeout(() => { btn.innerHTML = orig; }, 1500);
        }
    });
}

/* ═══════════════════════════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════════════════════════ */

async function init() {
    const versionP = fetch('https://ddragon.leagueoflegends.com/api/versions.json')
        .then(r => r.json())
        .then(v => { DD = `https://ddragon.leagueoflegends.com/cdn/${v[0]}`; return v[0]; })
        .catch(() => '14.24.1');

    const [version] = await Promise.all([versionP]);

    fetch(`https://ddragon.leagueoflegends.com/cdn/${version}/data/en_US/champion.json`)
        .then(r => r.json())
        .then(({ data }) => renderSplash(Object.keys(data), version))
        .catch(() => {});

    await refreshSummonerList();

    document.getElementById('search').addEventListener('input', e => {
        const q = e.target.value.toLowerCase();
        renderSummonerList(q ? allSummoners.filter(s => s.riot_id.toLowerCase().includes(q)) : allSummoners);
    });

    startSyncPolling();
    setMobilePanel('list');

    // Hash-based routing: restore state from URL on load
    window.addEventListener('hashchange', () => {
        if (!_suppressHashChange) _navigateFromHash();
    });
    const initialHash = _parseHash();
    console.log('[route] Initial hash:', initialHash, 'raw:', window.location.hash);
    if (initialHash.summoner) {
        await _navigateFromHash();
    }
}

/* ═══════════════════════════════════════════════════════════════════
   SPLASH SCREEN
═══════════════════════════════════════════════════════════════════ */

function renderSplash(champKeys, version) {
    const base  = `https://ddragon.leagueoflegends.com/cdn/${version}/img/champion`;
    const track = document.getElementById('splash-track');
    track.style.cssText = 'display:flex;gap:28px;padding:28px;align-items:flex-start;';

    const style = document.createElement('style');
    style.textContent = `
    @keyframes scrollUp { from{transform:translateY(0)} to{transform:translateY(-50%)} }
    .splash-col { display:flex; flex-direction:column; gap:28px; will-change:transform; flex-shrink:0; }
    `;
    document.head.appendChild(style);

    const CELL = 68, GAP = 28;
    const cols       = Math.ceil(window.innerWidth  / (CELL + GAP)) + 1;
    const rowsNeeded = Math.ceil(window.innerHeight / (CELL + GAP)) + 2;

    const globalPool = [...champKeys].sort(() => Math.random() - 0.5);
    while (globalPool.length < cols * rowsNeeded * 2) globalPool.push(...globalPool);

    for (let c = 0; c < cols; c++) {
        const col   = document.createElement('div');
        const dur   = 80 + c * 7 + Math.random() * 20;
        const delay = -(Math.random() * dur);
        col.className = 'splash-col';
        col.style.cssText = `animation: scrollUp ${dur.toFixed(1)}s linear ${delay.toFixed(1)}s infinite;`;

        const half  = rowsNeeded;
        const slice = globalPool.slice(c * half % globalPool.length, c * half % globalPool.length + half);
        [...slice, ...slice].forEach(key => {
            const img = document.createElement('img');
            img.src = `${base}/${key}.png`;
            img.style.cssText = `width:${CELL}px;height:${CELL}px;border-radius:8px;display:block;flex-shrink:0;`;
            img.onerror = () => { img.style.visibility = 'hidden'; };
            col.appendChild(img);
        });
        track.appendChild(col);
    }
    track.style.opacity = '0.15';
}

/* ═══════════════════════════════════════════════════════════════════
   SUMMONER LIST
═══════════════════════════════════════════════════════════════════ */

function renderSummonerList(list) {
    const ul = document.getElementById('summoner-list');
    ul.innerHTML = '';
    list.forEach(function(entry) {
        const { riot_id, region, last_searched, profileIconId } = entry;
        const li = document.createElement('li');
        li.className = 'flex items-center gap-2 px-2 py-2 hover:bg-slate-700/60 text-sm border-b border-slate-700/30 transition-colors group';
        li.dataset.id = riot_id;
        li.dataset.riotId = riot_id;

        const [name, tag]    = riot_id.split('#');
        const fallbackIcon   = DD + '/img/profileicon/29.png';
        const iconSrc        = profileIconId ? (DD + '/img/profileicon/' + profileIconId + '.png') : fallbackIcon;
        const ago            = last_searched ? timeAgo(last_searched) : '';

        const img = document.createElement('img');
        img.src       = iconSrc;
        img.className = 'w-8 h-8 rounded shrink-0 cursor-pointer';
        img.onerror   = function() { img.src = fallbackIcon; };
        img.onclick   = function() { selectSummoner(riot_id, li); };

        const info    = document.createElement('div');
        info.className = 'flex-1 min-w-0 cursor-pointer';
        info.onclick  = function() { selectSummoner(riot_id, li); };

        const nameDiv = document.createElement('div');
        nameDiv.className = 'font-medium truncate';
        nameDiv.innerHTML = name + '<span class="text-slate-500 font-normal">#' + tag + '</span>';

        const regionDiv = document.createElement('div');
        regionDiv.className = 'text-xs text-slate-500 truncate';
        regionDiv.setAttribute('data-region-label', '');
        regionDiv.textContent = region + (ago ? ' \u00b7 ' + ago : '');

        info.appendChild(nameDiv);
        info.appendChild(regionDiv);

        const editBtn = document.createElement('button');
        editBtn.className = 'opacity-0 hidden group-hover:opacity-100 transition-opacity p-1 text-slate-500 hover:text-slate-200 shrink-0';
        editBtn.title     = 'Cambiar región';
        editBtn.textContent = '\u270e';
        editBtn.onclick   = function(e) { e.stopPropagation(); editSummonerRegion(riot_id, editBtn); };

        li.appendChild(img);
        li.appendChild(info);
        li.appendChild(editBtn);
        if (riot_id === activeSummonerId) li.classList.add('bg-slate-700');
        ul.appendChild(li);
    });
}

async function editSummonerRegion(riot_id, btn) {
    const li    = btn.closest('li');
    const label = li.querySelector('[data-region-label]');
    const regions = ['LAN', 'LAS', 'NA', 'EUW', 'EUNE', 'BR', 'KR', 'JP', 'OCE', 'TR', 'RU'];
    const currentRegion = label.textContent.split(' \u00b7 ')[0].trim();
    const prev  = label.textContent;

    const sel = document.createElement('select');
    sel.className = 'bg-slate-700 text-white text-xs rounded px-1 py-0.5 mr-1';
    regions.forEach(function(r) {
        const opt = document.createElement('option');
        opt.value = r; opt.textContent = r;
        if (r === currentRegion) opt.selected = true;
        sel.appendChild(opt);
    });

    const okBtn = document.createElement('button');
    okBtn.className = 'text-xs bg-violet-600 hover:bg-violet-500 text-white rounded px-2 py-0.5 mr-1';
    okBtn.textContent = 'OK';

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'text-xs text-slate-400 hover:text-white';
    cancelBtn.textContent = '\u2715';

    label.textContent = '';
    label.appendChild(sel);
    label.appendChild(okBtn);
    label.appendChild(cancelBtn);

    cancelBtn.onclick = function() { label.textContent = prev; };
    okBtn.onclick = async function() {
        const newRegion = sel.value;
        okBtn.textContent = '\u2026'; okBtn.disabled = true;
        try {
            const res = await fetch('/api/db/summoners/' + encodeURIComponent(riot_id) + '/region', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ region: newRegion }),
            });
            const data = await res.json();
            if (!res.ok) { alert(data.error || 'Error'); label.textContent = prev; return; }
            const iconEl = li.querySelector('img');
            if (data.profileIconId) iconEl.src = DD + '/img/profileicon/' + data.profileIconId + '.png';
            label.textContent = newRegion;
            const s = allSummoners.find(function(x) { return x.riot_id === riot_id; });
            if (s) { s.region = newRegion; if (data.profileIconId) s.profileIconId = data.profileIconId; }
        } catch (e) { alert('Error: ' + e); label.textContent = prev; }
    };
}

async function refreshSummonerList() {
    const { summoners } = await fetch('/api/db/summoners/with-region').then(r => r.json());
    allSummoners = summoners;
    const q = document.getElementById('search').value.toLowerCase();
    renderSummonerList(q ? allSummoners.filter(s => s.riot_id.toLowerCase().includes(q)) : allSummoners);
    document.getElementById('footer-status').textContent = `${summoners.length} summoners loaded`;
}

/* ═══════════════════════════════════════════════════════════════════
   SELECT SUMMONER
═══════════════════════════════════════════════════════════════════ */

async function selectSummoner(riot_id, el, _fromHash = false) {
    document.querySelectorAll('#summoner-list li').forEach(l => l.classList.remove('bg-slate-700'));
    if (el) el.classList.add('bg-slate-700');
    activeSummonerId = riot_id;
    activeMatchEl    = null;
    activeMode       = 'all';
    activeRank       = null;

    document.getElementById('sync-btn').classList.remove('hidden');
    mount('match-history', skeletonMatchList());
    $('splash').classList.add('hidden');
    $('detail-panel').classList.remove('hidden');
    $('profile-strip').classList.add('hidden');
    $('profile-view').classList.remove('hidden');
    $('match-view').classList.add('hidden');
    mount('stats-row', skeletonStatsRow());
    mount('champ-grid', skeletonChampGrid());

    // Clear profile header while loading
    const [_pn, _pt] = riot_id.split('#');
    $('profile-name').innerHTML = `${_pn}<span class="text-slate-400 text-base font-normal ml-1.5">#${_pt || ''}</span>`;
    $('profile-level').textContent = '';
    mount('profile-rank-badge', '');

    // Fade out splash
    document.getElementById('profile-splash-bg').style.opacity = '0';

    // Reset duration section
    document.getElementById('duration-content').innerHTML =
        '<div class="absolute inset-0 flex items-center justify-center text-slate-600 text-xs">Loading\u2026</div>';
    document.getElementById('duration-btn').disabled = false;
    const _dm = document.getElementById('duration-meta');
    if (_dm) _dm.innerHTML = '';
    document.getElementById('duration-avg').textContent = '—';
    if (durationPollTimer) { clearInterval(durationPollTimer); durationPollTimer = null; }
    if (chartDUR) { chartDUR.destroy(); chartDUR = null; }

    // Reset heatmap section
    if (heatmapPollTimer) { clearInterval(heatmapPollTimer); heatmapPollTimer = null; }
    document.getElementById('heatmap-content').innerHTML =
        '<span class="text-slate-600 text-xs animate-pulse">Loading\u2026</span>';
    document.getElementById('heatmap-btn').disabled = false;
    const _hm = document.getElementById('heatmap-meta');
    if (_hm) _hm.textContent = '';

    // Reset timeline charts
    if (chartGoldPM)   { chartGoldPM.destroy();   chartGoldPM   = null; }
    if (chartDamagePM) { chartDamagePM.destroy(); chartDamagePM = null; }
    if (chartCSPM)     { chartCSPM.destroy();     chartCSPM     = null; }
    const _tlCon = document.getElementById('timeline-content');
    if (_tlCon) { _tlCon.innerHTML = ''; _tlCon.classList.add('hidden'); }

    const summoner = allSummoners.find(s => s.riot_id === riot_id);
    if (summoner?.profileIconId) {
        document.getElementById('profile-icon').src = `${DD}/img/profileicon/${summoner.profileIconId}.png`;
        document.getElementById('profile-icon').style.display = '';
        if (summoner.summonerLevel) $('profile-level').textContent = `Level ${summoner.summonerLevel}`;
    }

    const region = summoner?.region ?? 'LAN';
    const [matchRes, statsRes, rankRes] = await Promise.all([
        fetch(`/api/db/matches?riot_id=${encodeURIComponent(riot_id)}&count=50`).then(r => r.json()),
        fetch(`/api/db/summoner-stats?riot_id=${encodeURIComponent(riot_id)}`).then(r => r.json()),
        fetch(`/api/db/summoner-rank?riot_id=${encodeURIComponent(riot_id)}&region=${region}`)
            .then(r => r.json()).catch(() => ({ entries: [] })),
    ]);

    activeMatches = matchRes.matches || [];
    activeStats   = statsRes;
    activeRank    = rankRes.entries || [];

    document.getElementById('footer-status').textContent =
        `${riot_id} · ${activeMatches.length} matches cached · ${activeStats.total ?? 0} in stats`;

    renderMatchList(activeMatches);
    renderProfile(activeMode);
    setActiveTab(activeMode);

    const mc = document.getElementById('match-count');
    if (mc) mc.textContent = `(${activeMatches.length})`;
    setMobilePanel('profile');

    // Update URL hash
    if (!_fromHash) _setHash(riot_id, null);
}

/* ═══════════════════════════════════════════════════════════════════
   MATCH LIST
═══════════════════════════════════════════════════════════════════ */

function renderMatchList(matches) {
    const container = document.getElementById('match-history');
    if (!matches.length) {
        container.innerHTML = '<p class="p-4 text-slate-500 text-sm">No cached matches yet.</p>';
        return;
    }
    container.innerHTML = '';
    let lastBucket = null;
    matches.forEach(m => {
        const bucket = dateBucket(m.game_creation);
        if (bucket !== lastBucket) {
            lastBucket = bucket;
            const sep = document.createElement('div');
            sep.className = 'px-3 py-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider bg-slate-900/40 border-b border-slate-700/20';
            sep.textContent = bucket;
            container.appendChild(sep);
        }
        const tmpl = document.createElement('template');
        tmpl.innerHTML = MatchHistoryRow(m).trim();
        const card = tmpl.content.firstElementChild;
        card.onclick = () => selectMatch(m.match_id, card);
        container.appendChild(card);
    });
    // Update match count
    const mc = document.getElementById('match-count');
    if (mc) mc.textContent = `(${matches.length})`;
}

/* ═══════════════════════════════════════════════════════════════════
   PROFILE
═══════════════════════════════════════════════════════════════════ */

function renderProfile(mode) {
    if (!activeStats) return;
    const s = mode === 'all'
        ? activeStats
        : (activeStats.by_mode?.[mode] ?? { total: 0, wins: 0, winrate: 0, avg_kda: 0 });

    const total   = s.total   ?? 0;
    const wins    = s.wins    ?? 0;
    const losses  = s.losses  ?? (total - wins);
    const winrate = s.winrate ?? 0;
    const kda     = s.avg_kda ?? 0;
    const durSecs = s.avg_duration
        || (mode === 'all' ? activeStats.avg_duration : null)
        || activeStats.avg_duration;
    const avgDur  = durSecs ? fmtDuration(durSecs) : '—';
    const champs  = (mode === 'all'
        ? activeStats.top_champions
        : (s.top_champions?.length ? s.top_champions : activeStats.top_champions)) || [];

    mount('stats-row', StatsRow({ total, wins, losses, winrate, kda }));
    renderWinrateChart(wins, losses, avgDur);
    renderChampGrid(champs);
    renderProfileHeader();
    runDurationAnalysis();
    runHeatmapAnalysis();
}

function renderProfileHeader() {
    const topChamp = activeStats?.top_champions?.[0]?.champion;
    if (topChamp) {
        const splash = `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${champKey(topChamp)}_0.jpg`;
        const bg  = document.getElementById('profile-splash-bg');
        const img = new Image();
        img.onload = () => {
            bg.style.backgroundImage = `url('${splash}')`;
            requestAnimationFrame(() => { bg.style.opacity = '1'; });
        };
        img.onerror = () => { bg.style.opacity = '0'; };
        img.src = splash;
    }
    const soloEntry = (activeRank || []).find(e => e.queueType === 'RANKED_SOLO_5x5')
                   ?? (activeRank || []).find(e => e.queueType === 'RANKED_FLEX_SR')
                   ?? null;
    mount('profile-rank-badge', RankBadge(soloEntry));
}

function renderChampGrid(champs) {
    mount('champ-grid', champs.slice(0, 6).map(ChampGridItem).join(''));
}

function switchMode(mode) {
    activeMode = mode;
    setActiveTab(mode);
    renderProfile(mode);
    const filtered = mode === 'all'
        ? activeMatches
        : activeMatches.filter(m => (QUEUE_MODE[m.queue_id] ?? 'other') === mode);
    renderMatchList(filtered);
}

function setActiveTab(mode) {
    document.querySelectorAll('.tab-btn').forEach(b => {
        const active = b.dataset.mode === mode;
        b.className = 'tab-btn px-3 py-1 rounded text-sm transition-colors ' +
            (active ? 'bg-violet-700 text-white font-semibold' : 'text-slate-400 hover:text-white hover:bg-slate-700');
    });
}

/* ═══════════════════════════════════════════════════════════════════
   CHARTS
═══════════════════════════════════════════════════════════════════ */

function renderWinrateChart(wins, losses, avgDur) {
    if (chartWR) chartWR.destroy();
    const ctx = document.getElementById('chart-winrate').getContext('2d');
    chartWR = new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{ data: [wins, losses], backgroundColor: ['#3b82f6', '#334155'], borderWidth: 0, hoverOffset: 4 }]
        },
        options: {
            cutout: '74%',
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            animation: { duration: 400 }
        }
    });
    const pct = wins + losses ? Math.round(wins / (wins + losses) * 100) : null;
    document.getElementById('winrate-label').querySelector('span').textContent = pct !== null ? pct + '%' : '—';
    if (avgDur) document.getElementById('duration-avg').textContent = avgDur;
}

function renderChampChart(champs) {
    if (chartCH) chartCH.destroy();
    if (!champs.length) return;
    const ctx = document.getElementById('chart-champs').getContext('2d');
    chartCH = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: champs.map(c => c.champion),
            datasets: [
                { label: 'Wins',   data: champs.map(c => c.wins),             backgroundColor: '#3b82f688', borderRadius: 3 },
                { label: 'Losses', data: champs.map(c => c.games - c.wins),   backgroundColor: '#ef444444', borderRadius: 3 },
            ]
        },
        options: {
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + ctx.parsed.x } }
            },
            scales: {
                x: { stacked: true, grid: { color: '#33415533' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                y: { stacked: true, grid: { display: false },     ticks: { color: '#cbd5e1',  font: { size: 10 } } }
            },
            animation: { duration: 400 }
        }
    });
}

/* ═══════════════════════════════════════════════════════════════════
   MATCH DETAIL
═══════════════════════════════════════════════════════════════════ */

async function selectMatch(match_id, el, _fromHash = false) {
    if (activeMatchEl) activeMatchEl.classList.remove('bg-slate-700');
    if (el) el.classList.add('bg-slate-700');
    activeMatchEl = el;

    // Destroy previous match charts
    _destroyMatchCharts();

    $('profile-view').classList.add('hidden');
    $('match-view').classList.remove('hidden');
    mount('match-content', '<div class="flex items-center justify-center py-12 text-slate-400 text-sm"><span class="inline-block w-4 h-4 border-2 border-slate-500 border-t-slate-200 rounded-full animate-spin mr-2"></span>Loading match\u2026</div>');

    // Build profile strip
    const s    = activeStats;
    const top3 = (s?.top_champions || []).slice(0, 3);
    document.getElementById('strip-champs').innerHTML = top3.map(c =>
        `<img src="${DD}/img/champion/${champKey(c.champion)}.png" class="w-7 h-7 rounded" title="${c.champion}" onerror="this.style.display='none'">`
    ).join('');
    document.getElementById('strip-name').textContent  = activeSummonerId.split('#')[0];
    document.getElementById('strip-stats').textContent = s ? `${s.total}G · ${s.winrate}%WR · ${s.avg_kda} KDA` : '';
    $('profile-strip').classList.remove('hidden');

    // Scroll detail panel to top
    $('detail-panel').scrollTop = 0;

    const data = await fetch(`/api/db/match/${match_id}?riot_id=${encodeURIComponent(activeSummonerId)}`).then(r => r.json());
    if (data.error) { mount('match-content', `<p class="text-red-400 py-8">${data.error}</p>`); return; }

    const blue    = data.participants.filter(p => p.teamId === 100);
    const red     = data.participants.filter(p => p.teamId === 200);
    const maxDmg  = Math.max(...data.participants.map(p => p.totalDamageDealtToChampions), 1);
    const maxGold = Math.max(...data.participants.map(p => p.goldEarned), 1);

    const timelineHtml = data.timeline_metrics ? MatchTimelineCharts() : '';

    mount('match-content', `
    ${MatchDetailHeader(data.focused_participant, data.game_duration, data.game_mode_label, data.game_creation)}
    <div class="flex justify-end mb-3">
      <button id="ai-btn" onclick="analyzeWithAI('${match_id}')"
        class="px-3 py-1.5 bg-violet-700 hover:bg-violet-600 rounded text-sm font-medium transition-colors flex items-center gap-1.5">
        🤖 Analyze with AI
      </button>
    </div>
    <div id="ai-result" class="hidden mb-4 bg-slate-800/80 rounded-lg p-4 text-sm text-slate-200 whitespace-pre-wrap leading-relaxed border border-slate-700/50"></div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
      ${TeamTable(blue, 'Blue', data.blue_win,  data.focused_participant, maxDmg, maxGold, data.game_duration)}
      ${TeamTable(red,  'Red',  !data.blue_win, data.focused_participant, maxDmg, maxGold, data.game_duration)}
    </div>
    ${timelineHtml}`);

    // Render match-level timeline charts if data is available
    if (data.timeline_metrics) {
        _renderMatchTimeline(data.timeline_metrics);
    }

    setMobilePanel('match-detail');

    // Update URL hash
    if (!_fromHash) _setHash(activeSummonerId, match_id);
}

function _destroyMatchCharts() {
    if (matchChartGold)   { matchChartGold.destroy();   matchChartGold   = null; }
    if (matchChartDamage) { matchChartDamage.destroy(); matchChartDamage = null; }
    if (matchChartCS)     { matchChartCS.destroy();     matchChartCS     = null; }
}

function _renderMatchTimeline(metrics) {
    if (!metrics || !metrics.gold_per_min || !metrics.gold_per_min.length) return;

    const labels = metrics.gold_cumulative.map((_, i) => `${i}m`);

    const baseOpts = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: '#1e293b',
                titleColor: '#94a3b8',
                bodyColor: '#e2e8f0',
                borderColor: '#334155',
                borderWidth: 1,
            },
        },
        scales: {
            x: { ticks: { color: '#64748b', font: { size: 9 }, maxTicksLimit: 10 }, grid: { color: '#1e293b' } },
            y: { ticks: { color: '#64748b', font: { size: 9 }, callback: v => v >= 1000 ? (v/1000).toFixed(1)+'k' : v }, grid: { color: '#1e293b' } },
        },
        animation: { duration: 400 },
    };

    function _mk(id, cumData, rateData, cumColor, rateColor, cumLabel, rateLabel) {
        const el = document.getElementById(id);
        if (!el) return null;
        return new Chart(el, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: cumLabel, data: cumData, borderColor: cumColor, backgroundColor: cumColor + '18', fill: true, tension: 0.35, pointRadius: 0, pointHoverRadius: 3, borderWidth: 2 },
                    { label: rateLabel, data: rateData, borderColor: rateColor, backgroundColor: rateColor + '00', borderDash: [4, 3], tension: 0.35, pointRadius: 0, pointHoverRadius: 3, borderWidth: 1.5 },
                ],
            },
            options: baseOpts,
        });
    }

    matchChartGold   = _mk('match-chart-gold',   metrics.gold_cumulative,   metrics.gold_per_min,   '#fbbf24', '#fbbf2488', 'Total Gold', 'Gold/min');
    matchChartDamage = _mk('match-chart-damage', metrics.damage_cumulative, metrics.damage_per_min, '#f87171', '#f8717188', 'Total Damage', 'Dmg/min');
    matchChartCS     = _mk('match-chart-cs',     metrics.cs_cumulative,     metrics.cs_per_min,     '#34d399', '#34d39988', 'Total CS',    'CS/min');
}

function closeMatch() {
    if (activeMatchEl) activeMatchEl.classList.remove('bg-slate-700');
    activeMatchEl = null;
    _destroyMatchCharts();
    $('match-view').classList.add('hidden');
    $('profile-strip').classList.add('hidden');
    $('profile-view').classList.remove('hidden');
    setMobilePanel('profile');
    _setHash(activeSummonerId, null);
}

function closeProfile() {
    if (activeMatchEl) activeMatchEl.classList.remove('bg-slate-700');
    activeMatchEl = null;
    $('match-view').classList.add('hidden');
    $('profile-strip').classList.add('hidden');
    $('detail-panel').classList.add('hidden');
    $('splash').classList.remove('hidden');

    document.querySelectorAll('#summoner-list li').forEach(l => l.classList.remove('bg-slate-700'));
    activeSummonerId = null;
    activeMatches    = [];
    activeStats      = null;
    activeRank       = [];

    if (durationPollTimer) { clearInterval(durationPollTimer); durationPollTimer = null; }
    if (chartDUR) { chartDUR.destroy(); chartDUR = null; }
    if (chartWR)  { chartWR.destroy();  chartWR  = null; }
    if (heatmapPollTimer) { clearInterval(heatmapPollTimer); heatmapPollTimer = null; }
    if (chartGoldPM)   { chartGoldPM.destroy();   chartGoldPM   = null; }
    if (chartDamagePM) { chartDamagePM.destroy(); chartDamagePM = null; }
    if (chartCSPM)     { chartCSPM.destroy();     chartCSPM     = null; }
    const _dm = document.getElementById('duration-meta');
    if (_dm) _dm.innerHTML = '';
    document.getElementById('duration-content').innerHTML =
        '<div class="absolute inset-0 flex items-center justify-center text-slate-600 text-xs">Loading\u2026</div>';
    setMobilePanel('list');
    _setHash(null, null);
}

async function analyzeWithAI(match_id) {
    const btn    = document.getElementById('ai-btn');
    const result = document.getElementById('ai-result');
    btn.disabled = true; btn.textContent = 'Analyzing\u2026';
    result.classList.remove('hidden'); result.textContent = '\u2026';

    const detail = await fetch(`/api/db/match/${match_id}?riot_id=${encodeURIComponent(activeSummonerId)}`).then(r => r.json());
    if (!detail.focused_participant || !detail.focused_stats) {
        result.textContent = 'No participant data for AI.';
        btn.disabled = false; btn.textContent = '🤖 Analyze with AI'; return;
    }
    try {
        const { analysis } = await fetch('/api/ai/match-analysis', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nombre: detail.focused_participant.name,
                stats: detail.focused_stats,
                participant: detail.focused_participant,
                game_mode: detail.game_mode
            }),
        }).then(r => r.json());
        result.textContent = analysis ?? 'No analysis returned.';
    } catch (e) { result.textContent = `Error: ${e.message}`; }
    btn.disabled = false; btn.textContent = '🤖 Analyze with AI';
}

/* ═══════════════════════════════════════════════════════════════════
   SYNC SUMMONER
═══════════════════════════════════════════════════════════════════ */

async function syncSummoner() {
    if (!activeSummonerId) return;
    const btn  = document.getElementById('sync-btn');
    const icon = document.getElementById('sync-icon');
    btn.disabled  = true;
    icon.style.animation = 'spin 0.8s linear infinite';
    document.getElementById('footer-status').textContent = `Syncing ${activeSummonerId}\u2026`;

    const summoner = allSummoners.find(s => s.riot_id === activeSummonerId);
    const region   = summoner?.region ?? 'LAN';
    try {
        await fetch(`/api/summoner/${encodeURIComponent(activeSummonerId)}/match-history?region=${region}&count=10&analyze=false`);
        startSyncPolling();
        const [matchRes, statsRes, rankRes] = await Promise.all([
            fetch(`/api/db/matches?riot_id=${encodeURIComponent(activeSummonerId)}&count=50`).then(r => r.json()),
            fetch(`/api/db/summoner-stats?riot_id=${encodeURIComponent(activeSummonerId)}`).then(r => r.json()),
            fetch(`/api/db/summoner-rank?riot_id=${encodeURIComponent(activeSummonerId)}&region=${region}&force=1`)
                .then(r => r.json()).catch(() => ({ entries: [] })),
        ]);
        activeMatches = matchRes.matches || [];
        activeStats   = statsRes;
        activeRank    = rankRes.entries || [];
        renderMatchList(activeMatches);
        renderProfile(activeMode);
        document.getElementById('footer-status').textContent =
            `${activeSummonerId} · ${activeMatches.length} matches cached · ${activeStats.total ?? 0} in stats`;
    } catch (e) {
        document.getElementById('footer-status').textContent = `Sync failed: ${e.message}`;
    }
    icon.style.animation = '';
    btn.disabled = false;
    refreshSummonerList();
}

/* ═══════════════════════════════════════════════════════════════════
   MODAL
═══════════════════════════════════════════════════════════════════ */

function openModal() {
    document.getElementById('modal-backdrop').classList.remove('hidden');
    document.getElementById('modal-input').value = '';
    document.getElementById('modal-status').textContent = '';
    setTimeout(() => document.getElementById('modal-input').focus(), 50);
}

function closeModal(e) {
    if (e && e.target !== document.getElementById('modal-backdrop')) return;
    document.getElementById('modal-backdrop').classList.add('hidden');
    document.getElementById('modal-autocomplete').classList.add('hidden');
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.getElementById('modal-backdrop').classList.add('hidden');
});

function setupModalAutocomplete() {
    const input = document.getElementById('modal-input');
    const list  = document.getElementById('modal-autocomplete');
    input.addEventListener('input', () => {
        clearTimeout(acTimer);
        const q = input.value.trim();
        if (q.length < 1) { list.classList.add('hidden'); return; }
        acTimer = setTimeout(async () => {
            const { summoners } = await fetch(`/api/db/summoners/autocomplete?q=${encodeURIComponent(q)}&limit=8`).then(r => r.json());
            if (!summoners.length) { list.classList.add('hidden'); return; }
            list.innerHTML = summoners.map(s =>
                `<li class="px-3 py-2 text-sm hover:bg-slate-600 cursor-pointer" onclick="pickAC('${s}')">${s}</li>`
            ).join('');
            list.classList.remove('hidden');
        }, 180);
    });
    input.addEventListener('keydown', e => { if (e.key === 'Enter') submitModal(); });
}

function pickAC(value) {
    document.getElementById('modal-input').value = value;
    const tag = value.split('#')[1];
    if (tag) {
        const sel = document.getElementById('modal-region');
        const opt = [...sel.options].find(o => o.value === tag.toUpperCase());
        if (opt) sel.value = opt.value;
    }
    document.getElementById('modal-autocomplete').classList.add('hidden');
}

async function submitModal() {
    const riot_id = document.getElementById('modal-input').value.trim();
    const region  = document.getElementById('modal-region').value;
    const status  = document.getElementById('modal-status');
    const btn     = document.getElementById('modal-submit-btn');
    if (!riot_id.includes('#')) { status.textContent = 'Use Name#TAG format.'; return; }
    btn.disabled  = true;
    btn.innerHTML = '<span class="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2"></span>Loading\u2026';
    status.textContent = 'Fetching matches from Riot API\u2026';
    try {
        const res  = await fetch(`/api/summoner/${encodeURIComponent(riot_id)}/match-history?region=${region}&count=10&analyze=false`);
        const data = await res.json();
        if (!res.ok) { status.textContent = data.error || 'Error fetching matches.'; btn.disabled = false; btn.textContent = 'Load matches'; return; }
        status.innerHTML = `<span class="text-green-400">✓ Loaded ${data.matches?.length ?? 0} matches for ${riot_id}</span>`;
        await refreshSummonerList();
        setTimeout(() => {
            const li = document.querySelector(`#summoner-list li[data-id="${riot_id}"]`);
            if (li) li.click();
            document.getElementById('modal-backdrop').classList.add('hidden');
            btn.disabled = false; btn.textContent = 'Load matches';
        }, 800);
    } catch (e) { status.textContent = `Error: ${e.message}`; btn.disabled = false; btn.textContent = 'Load matches'; }
}

/* ═══════════════════════════════════════════════════════════════════
   DURATION ANALYSIS
═══════════════════════════════════════════════════════════════════ */

async function runDurationAnalysis(force = false) {
    if (!activeSummonerId) return;

    // 1. JS in-memory cache
    if (!force && durationCache[activeSummonerId]) {
        renderDurationResult(durationCache[activeSummonerId]);
        return;
    }

    const btn     = document.getElementById('duration-btn');
    const content = document.getElementById('duration-content');
    btn.disabled  = true;
    btn.style.animation  = 'spin 0.8s linear infinite';
    content.innerHTML    = `<div class="absolute inset-0 flex items-center justify-center text-slate-500 text-xs animate-pulse">Loading\u2026</div>`;

    // 2. Server-side Redis cache (instant if available)
    if (!force) {
        try {
            const sc = await fetch(`/api/db/analysis-cache?riot_id=${encodeURIComponent(activeSummonerId)}&type=duration`).then(r => r.json());
            if (sc.cached) {
                btn.disabled = false; btn.style.animation = '';
                durationCache[activeSummonerId] = sc.result;
                renderDurationResult(sc.result);
                return;
            }
        } catch (_) { /* fall through to task */ }
    }

    // 3. No cache — enqueue Celery task
    if (durationPollTimer) { clearInterval(durationPollTimer); durationPollTimer = null; }
    content.innerHTML = `<div class="absolute inset-0 flex items-center justify-center text-slate-500 text-xs animate-pulse">Fetching\u2026</div>`;

    const summoner = allSummoners.find(s => s.riot_id === activeSummonerId);
    const region   = summoner?.region ?? 'LAN';
    let taskId;
    try {
        const res = await fetch('/api/tasks/duration-stats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ riot_id: activeSummonerId, count: 50, region, force: !!force })
        }).then(r => r.json());
        taskId = res.task_id;
    } catch (e) {
        content.innerHTML = `<div class="text-red-400 text-xs p-2">${e.message}</div>`;
        btn.disabled = false; btn.style.animation = ''; return;
    }

    durationPollTimer = setInterval(async () => {
        const r = await fetch(`/api/tasks/${taskId}`).then(r => r.json()).catch(() => null);
        if (!r) return;
        if (r.status === 'PROGRESS' && r.progress) {
            content.innerHTML = `<div class="absolute inset-0 flex items-center justify-center text-slate-500 text-xs animate-pulse">${r.progress.current}/${r.progress.total} matches\u2026</div>`;
        } else if (r.status === 'SUCCESS') {
            clearInterval(durationPollTimer); durationPollTimer = null;
            btn.disabled = false; btn.style.animation = '';
            durationCache[activeSummonerId] = r.result;
            renderDurationResult(r.result);
        } else if (r.status === 'FAILURE') {
            clearInterval(durationPollTimer); durationPollTimer = null;
            btn.disabled = false; btn.style.animation = '';
            content.innerHTML = `<div class="absolute inset-0 flex items-center justify-center text-red-400 text-xs p-2">${r.error || 'Analysis failed'}</div>`;
        }
    }, 2000);
}

function renderDurationResult(result) {
    const content = document.getElementById('duration-content');
    if (!result || result.error) {
        content.innerHTML = `<div class="absolute inset-0 flex items-center justify-center text-red-400 text-sm">${result?.error || 'No data'}</div>`;
        return;
    }
    const stats   = result.general_stats || {};
    const buckets = (result.buckets || []).filter(b => b.total > 0);
    const wr      = stats.win_rate ?? 0;

    if (chartDUR) { chartDUR.destroy(); chartDUR = null; }
    content.innerHTML = `<div class="absolute inset-0"><canvas id="chart-duration"></canvas></div>`;

    const meta = document.getElementById('duration-meta');
    if (meta) meta.innerHTML = `
        <span><b class="text-white">${stats.total_analyzed ?? 0}</b>g</span>
        <span><b class="text-white">${(stats.avg_duration_min ?? 0).toFixed(1)}</b>m</span>
        <span class="font-semibold ${wr >= 50 ? 'text-blue-400' : 'text-red-400'}">${wr.toFixed(1)}%</span>`;

    const labels   = buckets.map(b => b.label);
    const pctData  = buckets.map(b => +(b.pct     ?? 0).toFixed(1));
    const wrData   = buckets.map(b => +(b.win_pct ?? 0).toFixed(1));
    const bgColors = buckets.map((_, i) => DURATION_COLORS[i] || '#6b7280');

    chartDUR = new Chart(document.getElementById('chart-duration').getContext('2d'), {
        data: {
            labels,
            datasets: [
                {
                    type: 'bar', label: '% of Games', data: pctData,
                    backgroundColor: bgColors.map(c => c + '55'), borderColor: bgColors,
                    borderWidth: 1.5, borderRadius: 4, yAxisID: 'yPct',
                },
                {
                    type: 'line', label: 'Win %', data: wrData,
                    borderColor: '#a78bfa', backgroundColor: '#a78bfa22',
                    borderWidth: 2.5, pointRadius: 4,
                    pointBackgroundColor: wrData.map(v => v >= 50 ? '#3b82f6' : '#ef4444'),
                    tension: 0.35, fill: true, yAxisID: 'yWR',
                },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y + '%' } }
            },
            scales: {
                yPct: { type: 'linear', position: 'left',  grid: { color: '#33415533' }, ticks: { color: '#64748b', font: { size: 9 }, callback: v => v + '%' }, min: 0 },
                yWR:  { type: 'linear', position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#a78bfa', font: { size: 9 }, callback: v => v + '%' }, min: 0, max: 100 },
                x:    { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 9 } } }
            },
            animation: { duration: 500 }
        }
    });
}

/* ═══════════════════════════════════════════════════════════════════
   POSITION HEATMAP
═══════════════════════════════════════════════════════════════════ */

function getHeatPalette() {
    if (_heatPalette) return _heatPalette;
    const c = document.createElement('canvas');
    c.width = 256; c.height = 1;
    const ctx = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 256, 0);
    g.addColorStop(0.0,  '#0000ff');
    g.addColorStop(0.15, '#00bbff');
    g.addColorStop(0.35, '#00ffaa');
    g.addColorStop(0.55, '#aaff00');
    g.addColorStop(0.75, '#ffdd00');
    g.addColorStop(1.0,  '#ff0000');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 256, 1);
    const data = ctx.getImageData(0, 0, 256, 1).data;
    _heatPalette = [];
    for (let i = 0; i < 256; i++) _heatPalette.push([data[i*4], data[i*4+1], data[i*4+2]]);
    return _heatPalette;
}

async function runHeatmapAnalysis(force = false) {
    if (!activeSummonerId) return;

    // 1. JS in-memory cache
    if (!force && heatmapCache[activeSummonerId]) {
        renderHeatmapResult(heatmapCache[activeSummonerId]);
        return;
    }

    const btn     = document.getElementById('heatmap-btn');
    const content = document.getElementById('heatmap-content');
    btn.disabled  = true;
    btn.style.animation = 'spin 0.8s linear infinite';
    content.innerHTML   = '<span class="text-slate-500 text-xs animate-pulse">Loading\u2026</span>';

    // 2. Server-side Redis cache (instant if available)
    if (!force) {
        try {
            const sc = await fetch(`/api/db/analysis-cache?riot_id=${encodeURIComponent(activeSummonerId)}&type=heatmap`).then(r => r.json());
            if (sc.cached) {
                btn.disabled = false; btn.style.animation = '';
                heatmapCache[activeSummonerId] = sc.result;
                renderHeatmapResult(sc.result);
                return;
            }
        } catch (_) { /* fall through to task */ }
    }

    // 3. No cache — enqueue Celery task
    if (heatmapPollTimer) { clearInterval(heatmapPollTimer); heatmapPollTimer = null; }
    content.innerHTML = '<span class="text-slate-500 text-xs animate-pulse">Fetching timeline data\u2026</span>';

    const summoner = allSummoners.find(s => s.riot_id === activeSummonerId);
    const region   = summoner?.region ?? 'LAN';
    let taskId;
    try {
        const res = await fetch('/api/tasks/heatmap', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ riot_id: activeSummonerId, count: 20, region, force: !!force })
        }).then(r => r.json());
        taskId = res.task_id;
    } catch (e) {
        content.innerHTML = `<span class="text-red-400 text-xs">${e.message}</span>`;
        btn.disabled = false; btn.style.animation = ''; return;
    }

    heatmapPollTimer = setInterval(async () => {
        const r = await fetch(`/api/tasks/${taskId}`).then(r => r.json()).catch(() => null);
        if (!r) return;
        if (r.status === 'PROGRESS' && r.progress) {
            content.innerHTML = `<span class="text-slate-500 text-xs animate-pulse">${r.progress.current}/${r.progress.total} matches\u2026</span>`;
        } else if (r.status === 'SUCCESS') {
            clearInterval(heatmapPollTimer); heatmapPollTimer = null;
            btn.disabled = false; btn.style.animation = '';
            heatmapCache[activeSummonerId] = r.result;
            renderHeatmapResult(r.result);
        } else if (r.status === 'FAILURE') {
            clearInterval(heatmapPollTimer); heatmapPollTimer = null;
            btn.disabled = false; btn.style.animation = '';
            content.innerHTML = `<span class="text-red-400 text-xs">${r.error || 'Analysis failed'}</span>`;
        }
    }, 2500);
}

function renderHeatmapResult(result) {
    const content = document.getElementById('heatmap-content');
    const meta    = document.getElementById('heatmap-meta');

    if (!result || result.error) {
        content.innerHTML = `<span class="text-red-400 text-sm">${result?.error || 'No data'}</span>`;
        return;
    }

    const positions = result.positions || [];
    if (!positions.length) {
        content.innerHTML = '<span class="text-slate-500 text-xs">No position data available</span>';
        return;
    }

    if (meta) meta.textContent = `${result.matches_analyzed} games \u00b7 ${positions.length} frames \u00b7 Summoner\u2019s Rift`;

    // Size canvas to fill container width (square)
    const containerW = content.clientWidth || 400;
    const canvasSize = Math.min(containerW, 512);
    content.innerHTML = `<canvas id="heatmap-canvas" width="${canvasSize}" height="${canvasSize}" class="rounded-lg mx-auto block" style="max-width:100%"></canvas>`;

    const canvas = document.getElementById('heatmap-canvas');
    const ctx    = canvas.getContext('2d');
    const S      = canvas.width;
    const MAP    = 14820;

    const mapImg = new Image();
    mapImg.crossOrigin = 'anonymous';

    const drawHeat = () => {
        // Darken minimap slightly so heat colours pop
        ctx.fillStyle = 'rgba(0,0,0,0.25)';
        ctx.fillRect(0, 0, S, S);

        // Build grayscale heat layer via radial gradient dots
        const heat = document.createElement('canvas');
        heat.width = heat.height = S;
        const hctx = heat.getContext('2d');

        const r = Math.max(10, Math.round(S / 28));
        const tpl = document.createElement('canvas');
        tpl.width = tpl.height = r * 2;
        const tctx = tpl.getContext('2d');
        const grad = tctx.createRadialGradient(r, r, 0, r, r, r);
        grad.addColorStop(0, 'rgba(0,0,0,1)');
        grad.addColorStop(1, 'rgba(0,0,0,0)');
        tctx.fillStyle = grad;
        tctx.fillRect(0, 0, r * 2, r * 2);

        const dotAlpha = Math.min(0.3, Math.max(0.04, 100 / positions.length));
        for (const [gx, gy] of positions) {
            const cx = (gx / MAP) * S;
            const cy = (1 - gy / MAP) * S;
            hctx.globalAlpha = dotAlpha;
            hctx.drawImage(tpl, cx - r, cy - r);
        }

        // Colorize via alpha → palette mapping
        const imgData = hctx.getImageData(0, 0, S, S);
        const d       = imgData.data;
        const palette = getHeatPalette();

        // Auto-scale: find max alpha to normalize
        let maxA = 0;
        for (let i = 3; i < d.length; i += 4) { if (d[i] > maxA) maxA = d[i]; }
        const scale = maxA > 0 ? 255 / maxA : 1;

        for (let i = 0; i < d.length; i += 4) {
            const a = d[i + 3];
            if (a < 3) { d[i+3] = 0; continue; }
            const idx = Math.min(255, Math.round(a * scale));
            const [cr, cg, cb] = palette[idx];
            d[i] = cr; d[i+1] = cg; d[i+2] = cb;
            d[i+3] = Math.min(220, Math.round(idx * 0.78) + 40);
        }

        hctx.putImageData(imgData, 0, 0);
        ctx.drawImage(heat, 0, 0);
    };

    mapImg.onload = () => { ctx.drawImage(mapImg, 0, 0, S, S); drawHeat(); };
    mapImg.onerror = () => {
        // Fallback: dark green-ish background
        ctx.fillStyle = '#0d1117';
        ctx.fillRect(0, 0, S, S);
        drawHeat();
    };
    mapImg.src = `${DD}/img/map/map11.png`;

    // Render per-minute metrics if available
    if (result.metrics) {
        renderTimelineMetrics(result.metrics, result.matches_analyzed);
    }
}

/* ═══════════════════════════════════════════════════════════════════
   TIMELINE PER-MINUTE METRICS
═══════════════════════════════════════════════════════════════════ */

function renderTimelineMetrics(metrics, matchCount) {
    const container = $('timeline-content');
    if (!container) return;

    // Guard: skip if no actual data
    if (!metrics || !metrics.gold_per_min || !metrics.gold_per_min.length) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');

    const metaEl = document.getElementById('timeline-meta');
    if (metaEl) metaEl.textContent = `(avg of ${matchCount} games)`;

    container.innerHTML = TimelineChartsContainer();

    if (chartGoldPM)   { chartGoldPM.destroy();   chartGoldPM   = null; }
    if (chartDamagePM) { chartDamagePM.destroy(); chartDamagePM = null; }
    if (chartCSPM)     { chartCSPM.destroy();     chartCSPM     = null; }

    const labels = metrics.gold_per_min.map((_, i) => `${i}m`);

    const baseOpts = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: '#1e293b',
                titleColor: '#94a3b8',
                bodyColor: '#e2e8f0',
                borderColor: '#334155',
                borderWidth: 1,
            },
        },
        scales: {
            x: {
                ticks: { color: '#64748b', font: { size: 9 }, maxTicksLimit: 10 },
                grid: { color: '#1e293b' },
            },
            y: {
                ticks: { color: '#64748b', font: { size: 9 } },
                grid: { color: '#1e293b' },
            },
        },
        animation: { duration: 500 },
    };

    function _makeLineChart(canvasId, data, color, label) {
        const el = document.getElementById(canvasId);
        if (!el) return null;
        return new Chart(el, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label,
                    data,
                    borderColor: color,
                    backgroundColor: color + '22',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    borderWidth: 2,
                }],
            },
            options: {
                ...baseOpts,
                scales: {
                    ...baseOpts.scales,
                    y: {
                        ...baseOpts.scales.y,
                        ticks: {
                            ...baseOpts.scales.y.ticks,
                            callback: v => v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v,
                        },
                    },
                },
            },
        });
    }

    chartGoldPM   = _makeLineChart('chart-gold-pm',   metrics.gold_per_min,   '#fbbf24', 'Gold/min');
    chartDamagePM = _makeLineChart('chart-damage-pm', metrics.damage_per_min, '#f87171', 'Damage/min');
    chartCSPM     = _makeLineChart('chart-cs-pm',     metrics.cs_per_min,     '#34d399', 'CS/min');
}

/* ═══════════════════════════════════════════════════════════════════
   SYNC PROGRESS POLLING
═══════════════════════════════════════════════════════════════════ */

function startSyncPolling() {
    if (syncPollTimer) return;
    syncPollTimer = setInterval(async () => {
        let p;
        try { p = await fetch('/api/db/sync-progress').then(r => r.json()); }
        catch { return; }
        if (!p || p.status === 'idle') return;

        const wrap = document.getElementById('sync-progress-bar-wrap');
        const bar  = document.getElementById('sync-progress-bar');
        const foot = document.getElementById('footer-status');

        if (p.status === 'running') {
            wrap.classList.remove('hidden');
            const pct = p.total ? Math.round(p.current / p.total * 100) : 0;
            bar.style.width = pct + '%';
            foot.textContent = `Syncing ${p.current}/${p.total}`
                + (p.new_matches     ? ` · ${p.new_matches} new`         : '')
                + (p.current_summoner ? ' · ' + p.current_summoner.split('#')[0] : '');
        } else if (p.status === 'done') {
            bar.style.width = '100%';
            setTimeout(() => {
                wrap.classList.add('hidden');
                bar.style.width = '0%';
                foot.textContent = `Sync done · ${p.new_matches ?? 0} new matches · ${p.errors ?? 0} errors`;
                clearInterval(syncPollTimer);
                syncPollTimer = null;
            }, 1500);
        }
    }, 2500);
}

/* ── Bootstrap ───────────────────────────────────────────────────── */
setupModalAutocomplete();
init();
