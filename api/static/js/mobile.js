/* ── Mobile panel navigation ─────────────────────────────────────── */
// On screens < 640px the layout stacks: only one panel is shown at a time.
// JS toggles .mobile-hidden to switch between them.
// Panels: 'list' (sidebar), 'profile' (profile + match history), 'match-detail'

let mobileView = 'list';
const isMobile = () => window.innerWidth < 640;

function setMobilePanel(panel) {
    if (!isMobile()) return;
    mobileView = panel;

    const sidebar = document.getElementById('summoner-sidebar');
    const detail  = document.getElementById('detail-panel');
    const splash  = document.getElementById('splash');

    // Splash is replaced by the sidebar on mobile
    splash.classList.add('mobile-hidden');

    // Reset all panels, then hide the ones not needed
    [sidebar, detail].forEach(el => el.classList.remove('mobile-hidden'));

    if (panel === 'list') {
        detail.classList.add('mobile-hidden');

    } else if (panel === 'profile') {
        sidebar.classList.add('mobile-hidden');
        const pv = document.getElementById('profile-view');
        const mv = document.getElementById('match-view');
        const ps = document.getElementById('profile-strip');
        if (pv) pv.classList.remove('hidden');
        if (mv) mv.classList.add('hidden');
        if (ps) ps.classList.add('hidden');

    } else if (panel === 'match-detail') {
        sidebar.classList.add('mobile-hidden');
        const pv = document.getElementById('profile-view');
        const mv = document.getElementById('match-view');
        if (pv) pv.classList.add('hidden');
        if (mv) mv.classList.remove('hidden');
    }
}
