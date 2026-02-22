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
    const goldPct = Math.round(p.goldEarned / maxGold * 100);
    const rowBg = isFocused
        ? (teamWin ? 'bg-blue-900/30 border border-blue-600/30' : 'bg-red-900/20 border border-red-700/20')
        : 'border border-transparent';
    const cspm = gameDur > 0 ? (p.cs / (gameDur / 60)).toFixed(1) : '?';
    return `
    <div class="flex items-center gap-2 rounded-lg px-2 py-1.5 mb-0.5 ${rowBg}">
      <img src="${DD}/img/champion/${champKey(p.champion)}.png" class="w-8 h-8 rounded shrink-0" onerror="this.style.display='none'">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-1">
          <span class="text-xs font-semibold truncate">${p.name}</span>
          ${isFocused ? '<span class="text-xs text-violet-400">★</span>' : ''}
        </div>
        <div class="text-xs text-slate-300 font-medium">${p.kills}/${p.deaths}/${p.assists}</div>
        <div class="flex gap-2 text-xs text-slate-500 mt-0.5">
          <span title="CS">🗡 ${p.cs} <span class="text-slate-600">(${cspm}/m)</span></span>
          <span title="Vision">👁 ${p.visionScore}</span>
        </div>
        <div class="mt-1 space-y-0.5">
          <div class="flex items-center gap-1">
            <span class="text-slate-600 w-6 text-right text-xs">DMG</span>
            <div class="flex-1 h-1 bg-slate-700 rounded overflow-hidden">
              <div class="h-full bg-violet-500" style="width:${dmgPct}%"></div>
            </div>
            <span class="text-xs text-slate-500 w-12 text-right">${(p.totalDamageDealtToChampions/1000).toFixed(1)}k</span>
          </div>
          <div class="flex items-center gap-1">
            <span class="text-slate-600 w-6 text-right text-xs">GOLD</span>
            <div class="flex-1 h-1 bg-slate-700 rounded overflow-hidden">
              <div class="h-full bg-yellow-500" style="width:${goldPct}%"></div>
            </div>
            <span class="text-xs text-slate-500 w-12 text-right">${(p.goldEarned/1000).toFixed(1)}k</span>
          </div>
        </div>
      </div>
    </div>`;
}

function TeamTable(participants, label, teamWin, focused, maxDmg, maxGold, gameDur) {
    const isBlue = label === 'Blue';
    const winBadge = teamWin
        ? `<span class="ml-2 px-1.5 py-0.5 rounded text-xs font-bold bg-blue-600/30 text-blue-300 border border-blue-500/30">WIN</span>`
        : `<span class="ml-2 px-1.5 py-0.5 rounded text-xs font-bold bg-red-900/40 text-red-400 border border-red-700/30">LOSS</span>`;
    const headerColor = isBlue ? 'text-blue-400' : 'text-red-400';
    const rows = participants.map(p => {
        const isFocused = focused && p.puuid === focused.puuid;
        return ParticipantRow(p, isFocused, teamWin, maxDmg, maxGold, gameDur);
    }).join('');
    return `<div class="bg-slate-800 rounded-lg p-3">
    <div class="flex items-center text-xs font-semibold ${headerColor} mb-2">
        <span>${label} Team</span>${winBadge}
    </div>${rows}</div>`;
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
