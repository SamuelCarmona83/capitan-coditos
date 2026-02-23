/* ── DOM helpers ─────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);
function mount(id, html) { $(id).innerHTML = html; }

/* ── UI Components (pure: return HTML strings, no side effects) ───── */

function StatsRow({ total, wins, losses, winrate, kda }) {
    return `
    <div class="bg-slate-800 rounded-lg p-3 text-center">
      <div class="text-2xl font-bold">${total}</div>
      <div class="text-xs text-slate-400 mt-0.5">Games</div>
    </div>
    <div class="bg-slate-800 rounded-lg p-3 text-center">
      <div class="text-2xl font-bold ${winrate >= 50 ? 'text-blue-400' : 'text-red-400'}">${winrate}%</div>
      <div class="text-xs text-slate-400 mt-0.5">${wins}W ${losses}L</div>
    </div>
    <div class="bg-slate-800 rounded-lg p-3 text-center">
      <div class="text-2xl font-bold">${kda}</div>
      <div class="text-xs text-slate-400 mt-0.5">Avg KDA</div>
    </div>`;
}

function ChampGridItem(c) {
    const wr = c.winrate;
    return `
    <div class="flex items-center gap-2">
      <img src="${DD}/img/champion/${champKey(c.champion)}.png" class="w-7 h-7 rounded shrink-0" onerror="this.style.display='none'">
      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between">
          <span class="text-xs font-medium truncate">${c.champion}</span>
          <span class="text-xs ml-1 shrink-0 ${wr >= 50 ? 'text-blue-400' : 'text-red-400'}">${wr}%</span>
        </div>
        <div class="h-1 bg-slate-700 rounded overflow-hidden mt-0.5">
          <div class="h-full rounded ${wr >= 50 ? 'bg-blue-500' : 'bg-red-500'}" style="width:${wr}%"></div>
        </div>
      </div>
    </div>`;
}

function MatchCard(m) {
    const modeLabel = QUEUE_LABEL[m.queue_id] || m.game_mode;
    const border = m.win ? 'border-l-blue-600' : 'border-l-red-700';
    return `
    <div class="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-slate-700/60 transition-colors border-b border-slate-700/30 border-l-2 ${border}" data-match-id="${m.match_id}">
      <img src="${DD}/img/champion/${champKey(m.champion)}.png" class="w-8 h-8 rounded shrink-0" onerror="this.style.display='none'">
      <div class="flex-1 min-w-0">
        <div class="text-sm font-medium truncate">${m.champion}</div>
        <div class="text-xs text-slate-400 truncate">${m.kills}/${m.deaths}/${m.assists} · ${modeLabel}</div>
      </div>
    </div>`;
}

function MatchHistoryRow(m) {
    const modeLabel = QUEUE_LABEL[m.queue_id] || m.game_mode;
    const win = m.win;
    const border = win ? 'border-l-blue-500' : 'border-l-red-500';
    const hoverBg = win ? 'hover:bg-blue-900/10' : 'hover:bg-red-900/10';
    const kda = `${m.kills}/${m.deaths}/${m.assists}`;
    const kdaVal = m.deaths > 0 ? ((m.kills + m.assists) / m.deaths).toFixed(1) : 'Perfect';
    const kdaColor = !m.deaths ? 'text-yellow-400' : (m.kills + m.assists) / m.deaths >= 3 ? 'text-blue-400' : (m.kills + m.assists) / m.deaths >= 1.5 ? 'text-slate-200' : 'text-red-400';
    const dur = m.game_duration ? fmtDuration(m.game_duration) : '';
    const ago = m.game_creation ? timeAgo(m.game_creation) : '';

    return `
    <div class="flex items-center gap-2 sm:gap-3 px-2 sm:px-4 py-2 cursor-pointer ${hoverBg} transition-colors border-l-2 ${border} border-b border-slate-700/20" data-match-id="${m.match_id}">
      <div class="w-4 text-center shrink-0">
        <span class="text-[10px] font-black ${win ? 'text-blue-400' : 'text-red-400'}">${win ? 'W' : 'L'}</span>
      </div>
      <img src="${DD}/img/champion/${champKey(m.champion)}.png" class="w-8 h-8 rounded shrink-0" onerror="this.style.display='none'">
      <div class="w-16 sm:w-20 min-w-0 shrink-0">
        <div class="text-xs sm:text-sm font-medium truncate">${m.champion}</div>
      </div>
      <div class="w-14 sm:w-20 text-center shrink-0">
        <div class="text-xs sm:text-sm font-semibold ${kdaColor}">${kda}</div>
        <div class="text-[10px] text-slate-500">${kdaVal} KDA</div>
      </div>
      <div class="hidden sm:block text-xs text-slate-500 w-24 shrink-0 truncate">${modeLabel}</div>
      <div class="flex-1"></div>
      <div class="text-right shrink-0">
        <div class="text-[11px] text-slate-400">${dur}</div>
        <div class="text-[10px] text-slate-600">${ago}</div>
      </div>
    </div>`;
}

function RankBadge(soloEntry) {
    if (!soloEntry) return '<span class="text-xs text-slate-500">Unranked</span>';
    const tier  = soloEntry.tier;
    const color = TIER_COLOR[tier] || '#94a3b8';
    const label = `${TIER_LABEL(tier)} ${soloEntry.rank}`;
    const lp    = `${soloEntry.leaguePoints} LP`;
    const wr    = soloEntry.wins + soloEntry.losses
        ? Math.round(soloEntry.wins / (soloEntry.wins + soloEntry.losses) * 100)
        : 0;
    const crestUrl = `https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-mini-crests/${tier.toLowerCase()}.svg`;
    const qLabel = soloEntry.queueType === 'RANKED_FLEX_SR' ? 'Flex' : 'Solo/Duo';
    return `
    <div class="flex flex-col items-center gap-2 px-4 py-3 rounded-xl"
         style="background:rgba(10,15,30,0.82);backdrop-filter:blur(8px);border:1.5px solid ${color}44;min-width:110px">
        <img src="${crestUrl}" style="width:72px;height:72px;filter:drop-shadow(0 2px 8px ${color}88)" onerror="this.style.display='none'">
        <div class="text-center leading-snug">
            <div class="text-xs font-medium" style="color:${color}99">${qLabel}</div>
            <div class="font-extrabold text-lg leading-none mt-0.5" style="color:${color}">${label}</div>
            <div class="text-sm font-semibold text-white mt-0.5">${lp}</div>
            <div class="text-xs text-slate-400 mt-0.5">${wr}% WR &middot; ${soloEntry.wins}W ${soloEntry.losses}L</div>
        </div>
    </div>`;
}

function ParticipantRow(p, isFocused, teamWin, maxDmg, maxGold, gameDur) {
    const dmgPct  = Math.round(p.totalDamageDealtToChampions / maxDmg * 100);
    const cspm = gameDur > 0 ? (p.cs / (gameDur / 60)).toFixed(1) : '?';
    const rowBg = isFocused
        ? (teamWin ? 'bg-blue-900/20 border-l-2 border-l-blue-400' : 'bg-red-900/15 border-l-2 border-l-red-400')
        : 'border-l-2 border-l-transparent';
    return `
    <div class="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 ${rowBg} hover:bg-slate-700/20 transition-colors">
      <img src="${DD}/img/champion/${champKey(p.champion)}.png" class="w-7 h-7 sm:w-8 sm:h-8 rounded shrink-0" onerror="this.style.display='none'">
      <div class="w-20 sm:w-28 min-w-0 shrink-0">
        <div class="text-[11px] sm:text-xs font-semibold truncate flex items-center gap-1">
          ${p.name}${isFocused ? ' <span class="text-violet-400 text-[10px]">★</span>' : ''}
        </div>
      </div>
      <div class="w-14 sm:w-16 text-center shrink-0">
        <div class="text-xs font-bold text-slate-200">${p.kills}/${p.deaths}/${p.assists}</div>
      </div>
      <div class="hidden sm:block w-14 text-center text-[11px] text-slate-500 shrink-0">
        ${p.cs} <span class="text-slate-600">(${cspm})</span>
      </div>
      <div class="flex-1 flex items-center gap-1 min-w-0">
        <div class="flex-1 h-1.5 bg-slate-700/60 rounded-full overflow-hidden">
          <div class="h-full bg-violet-500/70 rounded-full" style="width:${dmgPct}%"></div>
        </div>
        <span class="text-[10px] sm:text-xs text-slate-400 w-9 sm:w-11 text-right shrink-0">${(p.totalDamageDealtToChampions/1000).toFixed(1)}k</span>
      </div>
      <div class="hidden sm:block w-10 text-right text-xs text-yellow-500/60 shrink-0">${(p.goldEarned/1000).toFixed(1)}k</div>
      <div class="hidden sm:block w-5 text-right text-[10px] text-slate-600 shrink-0">${p.visionScore}</div>
    </div>`;
}

function ScoreboardHeader() {
    return `
    <div class="hidden sm:flex items-center gap-2 px-3 py-1 text-[10px] text-slate-600 uppercase tracking-wider border-b border-slate-700/30">
      <div class="w-8"></div>
      <div class="w-28">Player</div>
      <div class="w-16 text-center">KDA</div>
      <div class="w-14 text-center">CS</div>
      <div class="flex-1">Damage</div>
      <div class="w-10 text-right">Gold</div>
      <div class="w-5 text-right">👁</div>
    </div>`;
}

function TeamTable(participants, label, teamWin, focused, maxDmg, maxGold, gameDur) {
    const isBlue = label === 'Blue';
    const winBadge = teamWin
        ? `<span class="ml-2 px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-600/20 text-blue-300 border border-blue-500/20">WIN</span>`
        : `<span class="ml-2 px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-900/30 text-red-400 border border-red-700/20">LOSS</span>`;
    const headerColor = isBlue ? 'text-blue-400' : 'text-red-400';
    const accentBorder = isBlue ? 'border-t-blue-500/40' : 'border-t-red-500/40';
    const rows = participants.map(p => {
        const isFocused = focused && p.puuid === focused.puuid;
        return ParticipantRow(p, isFocused, teamWin, maxDmg, maxGold, gameDur);
    }).join('');
    return `<div class="bg-slate-800/80 rounded-lg overflow-hidden border-t-2 ${accentBorder}">
    <div class="flex items-center justify-between px-3 py-2 ${headerColor} text-xs font-semibold border-b border-slate-700/40">
        <div class="flex items-center"><span>${label} Team</span>${winBadge}</div>
    </div>
    ${ScoreboardHeader()}${rows}</div>`;
}

function MatchDetailHeader(focused, gameDuration, gameModeLabel, gameCreation) {
    if (!focused) return '';
    const win = focused.win;
    const champImg = `${DD}/img/champion/${champKey(focused.champion)}.png`;
    const splash = `https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${champKey(focused.champion)}_0.jpg`;
    const kda = `${focused.kills}/${focused.deaths}/${focused.assists}`;
    const kdaRatio = focused.deaths > 0 ? ((focused.kills + focused.assists) / focused.deaths).toFixed(2) : 'Perfect';
    const accentColor = win ? 'rgba(37,99,235,0.25)' : 'rgba(239,68,68,0.2)';
    const borderColor = win ? 'border-blue-500/30' : 'border-red-500/30';

    return `
    <div class="relative rounded-xl overflow-hidden mb-4 border ${borderColor}" style="min-height:140px">
      <div class="absolute inset-0" style="background:url('${splash}');background-size:cover;background-position:center 20%;filter:brightness(0.25) saturate(1.3)"></div>
      <div class="absolute inset-0" style="background:linear-gradient(135deg, ${accentColor}, transparent 60%)"></div>
      <div class="absolute inset-0" style="background:linear-gradient(to top, rgba(15,23,42,0.85), transparent 50%)"></div>
      <div class="relative z-10 flex items-center gap-4 p-4 sm:p-5 h-full">
        <img src="${champImg}" class="w-14 h-14 sm:w-18 sm:h-18 rounded-xl border-2 ${win ? 'border-blue-500/60' : 'border-red-500/60'} shadow-lg shrink-0" onerror="this.style.display='none'">
        <div class="min-w-0">
          <div class="text-2xl sm:text-3xl font-black tracking-tight ${win ? 'text-blue-300' : 'text-red-300'}">${win ? 'VICTORY' : 'DEFEAT'}</div>
          <div class="text-lg sm:text-xl font-bold text-white mt-0.5">${kda} <span class="text-sm font-normal text-slate-400">${kdaRatio} KDA</span></div>
          <div class="flex flex-wrap gap-x-2 gap-y-0.5 text-xs sm:text-sm text-slate-400 mt-1">
            <span>${gameModeLabel}</span><span class="text-slate-600">·</span>
            <span>${fmtDuration(gameDuration)}</span><span class="text-slate-600">·</span>
            <span>${fmtDate(gameCreation)}</span>
          </div>
        </div>
      </div>
    </div>`;
}

function MatchOutcomeBar(focusedWin, gameDuration, gameModeLabel, gameCreation) {
    if (focusedWin === undefined) return '';
    return `<div class="px-4 py-2 rounded-lg mb-4 text-center font-bold text-sm tracking-wide ${
        focusedWin ? 'bg-blue-900/60 text-blue-300 border border-blue-600/40' : 'bg-red-900/50 text-red-300 border border-red-700/40'
    }">${focusedWin ? '✦ VICTORY' : '✦ DEFEAT'} &nbsp;·&nbsp; ${fmtDuration(gameDuration)} &nbsp;·&nbsp; ${gameModeLabel} &nbsp;·&nbsp; ${fmtDate(gameCreation)}</div>`;
}

/* ── Skeleton components ─────────────────────────────────────────── */

function SkeletonMatchItem() {
    return `
    <div class="flex items-center gap-2 px-3 py-2 border-l-2 border-slate-700">
      <div class="skeleton w-8 h-8 shrink-0"></div>
      <div class="flex-1 space-y-1.5">
        <div class="skeleton h-3 w-3/4"></div>
        <div class="skeleton h-2.5 w-1/2"></div>
      </div>
      <div class="skeleton h-2.5 w-10 shrink-0"></div>
    </div>`;
}

function SkeletonStatCard() {
    return `
    <div class="bg-slate-800 rounded-lg p-3 space-y-2">
      <div class="skeleton h-7 w-16 mx-auto"></div>
      <div class="skeleton h-2.5 w-12 mx-auto"></div>
    </div>`;
}

function SkeletonChampItem() {
    return `
    <div class="bg-slate-800 rounded-lg p-2 flex flex-col items-center gap-1">
      <div class="skeleton w-10 h-10 rounded"></div>
      <div class="skeleton h-2.5 w-14"></div>
      <div class="skeleton h-2 w-10"></div>
    </div>`;
}

function skeletonMatchList() { return Array.from({ length: 8 }, SkeletonMatchItem).join(''); }
function skeletonStatsRow()  { return Array.from({ length: 3 }, SkeletonStatCard).join(''); }
function skeletonChampGrid() { return Array.from({ length: 8 }, SkeletonChampItem).join(''); }

/* ── Timeline per-minute charts container ────────────────────────── */

function TimelineChartsContainer() {
    return `
    <div class="flex flex-col gap-3">
      <div class="bg-slate-700/40 rounded-lg p-2.5">
        <div class="flex items-center gap-1.5 mb-1.5">
          <span class="w-2 h-2 rounded-full bg-yellow-400"></span>
          <span class="text-[11px] text-slate-400 font-semibold">Gold / min</span>
        </div>
        <div class="relative" style="height:110px"><canvas id="chart-gold-pm"></canvas></div>
      </div>
      <div class="bg-slate-700/40 rounded-lg p-2.5">
        <div class="flex items-center gap-1.5 mb-1.5">
          <span class="w-2 h-2 rounded-full bg-red-400"></span>
          <span class="text-[11px] text-slate-400 font-semibold">Damage / min</span>
        </div>
        <div class="relative" style="height:110px"><canvas id="chart-damage-pm"></canvas></div>
      </div>
      <div class="bg-slate-700/40 rounded-lg p-2.5">
        <div class="flex items-center gap-1.5 mb-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
          <span class="text-[11px] text-slate-400 font-semibold">CS / min</span>
        </div>
        <div class="relative" style="height:110px"><canvas id="chart-cs-pm"></canvas></div>
      </div>
    </div>`;
}

function MatchTimelineCharts() {
    return `
    <div class="bg-slate-800/60 rounded-lg p-4 mt-3">
      <div class="text-xs text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">📈 Player Timeline</div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div class="bg-slate-700/40 rounded-lg p-2.5">
          <div class="flex items-center gap-1.5 mb-1.5">
            <span class="w-2 h-2 rounded-full bg-yellow-400"></span>
            <span class="text-[11px] text-slate-400 font-semibold">Gold</span>
          </div>
          <div class="relative" style="height:120px"><canvas id="match-chart-gold"></canvas></div>
        </div>
        <div class="bg-slate-700/40 rounded-lg p-2.5">
          <div class="flex items-center gap-1.5 mb-1.5">
            <span class="w-2 h-2 rounded-full bg-red-400"></span>
            <span class="text-[11px] text-slate-400 font-semibold">Damage</span>
          </div>
          <div class="relative" style="height:120px"><canvas id="match-chart-damage"></canvas></div>
        </div>
        <div class="bg-slate-700/40 rounded-lg p-2.5">
          <div class="flex items-center gap-1.5 mb-1.5">
            <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span class="text-[11px] text-slate-400 font-semibold">CS</span>
          </div>
          <div class="relative" style="height:120px"><canvas id="match-chart-cs"></canvas></div>
        </div>
      </div>
    </div>`;
}
