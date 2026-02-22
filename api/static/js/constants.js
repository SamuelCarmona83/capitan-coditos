/* ── DDragon base URL (updated on init) ─────────────────────────── */
let DD = 'https://ddragon.leagueoflegends.com/cdn/14.24.1';

/* ── Rank display ────────────────────────────────────────────────── */
const TIER_COLOR = {
    IRON: '#7c7c7c', BRONZE: '#cd7f32', SILVER: '#a8adb4',
    GOLD: '#f0b927', PLATINUM: '#4dc6b0', EMERALD: '#2ecc71',
    DIAMOND: '#9b59b6', MASTER: '#b24fff', GRANDMASTER: '#e74c3c', CHALLENGER: '#f8c300'
};
const TIER_LABEL = t => t ? t.charAt(0) + t.slice(1).toLowerCase() : '';
const ROMAN = { I: 1, II: 2, III: 3, IV: 4 };

/* ── Queue labels + mode buckets ─────────────────────────────────── */
const QUEUE_LABEL = {
    400: 'Normal Draft', 420: 'Ranked Solo', 430: 'Normal Blind', 440: 'Ranked Flex',
    450: 'ARAM', 480: 'Partida rápida', 490: 'Quickplay',
    700: 'Clash', 720: 'Clash ARAM', 900: 'ARURF', 1020: 'One for All',
    1300: 'Nexus Blitz', 1400: 'Ultimate Spellbook', 1700: 'Arena', 1710: 'Arena (16j)',
    1900: 'Pick URF', 2300: 'Brawl', 2400: 'ARAM: Mayhem', 0: 'Custom'
};
// Maps queue_id → mode bucket used by the stats tabs
const QUEUE_MODE = {
    400: 'normal', 420: 'ranked', 430: 'normal', 440: 'ranked',
    450: 'aram', 480: 'normal', 490: 'normal',
    700: 'ranked', 720: 'aram', 900: 'other', 1020: 'other',
    1300: 'other', 1400: 'other', 1700: 'other', 1710: 'other',
    1900: 'other', 2300: 'other', 2400: 'aram',
};

/* ── Champion key overrides (DDragon naming quirks) ──────────────── */
const CHAMP_KEYS = {
    'Wukong': 'MonkeyKing', 'Nunu & Willump': 'Nunu', "Cho'Gath": 'Chogath',
    "Kai'Sa": 'Kaisa', "Kha'Zix": 'Khazix', "Kog'Maw": 'KogMaw',
    'LeBlanc': 'Leblanc', "Vel'Koz": 'Velkoz', "Rek'Sai": 'RekSai',
    'Renata Glasc': 'Renata', "Bel'Veth": 'Belveth', 'FiddleSticks': 'Fiddlesticks',
};
const champKey = n => CHAMP_KEYS[n] ?? n;

/* ── Pure formatting utilities ───────────────────────────────────── */
const fmtDuration = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
const fmtDate = ms => new Date(ms).toLocaleDateString();

function dateBucket(ms) {
    const now = new Date();
    const d = new Date(ms);
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const diff = todayStart - new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const days = diff / 86400000;
    if (days === 0) return 'Hoy';
    if (days === 1) return 'Ayer';
    if (days < 7) return 'Esta semana';
    if (days < 14) return 'La semana pasada';
    if (d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()) return 'Este mes';
    return d.toLocaleDateString('es', { month: 'long', year: 'numeric' });
}

function timeAgo(iso) {
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
}
