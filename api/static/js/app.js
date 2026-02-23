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

/* ── Sync progress polling state ─────────────────────────────────── */
let syncPollTimer = null;

/* ── Modal autocomplete debounce ─────────────────────────────────── */
let acTimer = null;

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

async function selectSummoner(riot_id, el) {
    document.querySelectorAll('#summoner-list li').forEach(l => l.classList.remove('bg-slate-700'));
    el.classList.add('bg-slate-700');
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

async function selectMatch(match_id, el) {
    if (activeMatchEl) activeMatchEl.classList.remove('bg-slate-700');
    el.classList.add('bg-slate-700');
    activeMatchEl = el;

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
    </div>`);

    setMobilePanel('match-detail');
}

function closeMatch() {
    if (activeMatchEl) activeMatchEl.classList.remove('bg-slate-700');
    activeMatchEl = null;
    $('match-view').classList.add('hidden');
    $('profile-strip').classList.add('hidden');
    $('profile-view').classList.remove('hidden');
    setMobilePanel('profile');
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
    const _dm = document.getElementById('duration-meta');
    if (_dm) _dm.innerHTML = '';
    document.getElementById('duration-content').innerHTML =
        '<div class="absolute inset-0 flex items-center justify-center text-slate-600 text-xs">Loading\u2026</div>';
    setMobilePanel('list');
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
    if (!force && durationCache[activeSummonerId]) {
        renderDurationResult(durationCache[activeSummonerId]);
        return;
    }
    if (durationPollTimer) { clearInterval(durationPollTimer); durationPollTimer = null; }

    const btn     = document.getElementById('duration-btn');
    const content = document.getElementById('duration-content');
    btn.disabled  = true;
    btn.style.animation  = 'spin 0.8s linear infinite';
    content.innerHTML    = `<div class="absolute inset-0 flex items-center justify-center text-slate-500 text-xs animate-pulse">Fetching\u2026</div>`;

    const summoner = allSummoners.find(s => s.riot_id === activeSummonerId);
    const region   = summoner?.region ?? 'LAN';
    let taskId;
    try {
        const res = await fetch('/api/tasks/duration-stats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ riot_id: activeSummonerId, count: 50, region })
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
