# Working on Capitán Coditos with GitHub Copilot

This document captures the conventions, architecture decisions, and workflow patterns established during iterative development of this project with an AI assistant. Use it as a starting point for any new session.

---

## Architecture at a glance

```
Discord Bot (bot/)  ──HTTP──►  Flask API (api/)  ──►  MongoDB  (match data)
                                    │                   Redis    (cache + queue)
                                    └──►  Celery Workers (heavy tasks)
```

- **`api/`** — Flask REST API served by Gunicorn on port 5000 (host: 5001).  
  All business logic lives here. The bot is a thin HTTP client.
- **`bot/`** — Discord bot. Calls the API, builds embeds, handles slash commands.
- **MongoDB** — Stores raw match data (`matches` collection), summoner registry (`summoners`), and profiles (`summoner_profiles`).
- **Redis** — L1 cache, Celery broker/backend, and real-time keys like `sync:progress`.
- **Celery** — Worker + Beat. Tasks live in `api/tasks/`. Enqueued via `POST /api/tasks/*`, polled via `GET /api/tasks/{task_id}`.

---

## Key files

| File | What it does |
|---|---|
| `api/app.py` | Flask app factory |
| `api/config.py` | All env var loading |
| `api/routes/db.py` | Main data API: match detail, stats, summoner list, sync progress |
| `api/routes/tasks.py` | Task enqueue + status poll endpoint |
| `api/database/match_cache.py` | Redis + MongoDB cache-aside layer for match data |
| `api/database/summoners.py` | Summoner registry CRUD |
| `api/tasks/celery_app.py` | Celery config (broker, backend, beat schedule) |
| `api/tasks/duration_stats.py` | Duration bucket analysis task |
| `api/tasks/matchups.py` | Champion matchup task |
| `api/tasks/worst_games.py` | Worst games task |
| `api/templates/index.html` | Web dashboard HTML shell — loads the four static JS files below |
| `api/static/js/constants.js` | Data constants (`DD`, `TIER_COLOR`, `QUEUE_MODE`…) + pure formatting utils (`fmtDuration`, `timeAgo`…) |
| `api/static/js/components.js` | Pure UI components returning HTML strings (`StatsRow`, `MatchCard`, `TeamTable`, skeletons…) + `$`/`mount` helpers |
| `api/static/js/mobile.js` | Mobile panel navigation — `setMobilePanel(panel)`, `isMobile()` |
| `api/static/js/app.js` | All app state, render functions, API calls, event wiring, and bootstrap calls |
| `bot/utils/api_client.py` | aiohttp wrapper + task polling helper for the bot |
| `bot/utils/embed_builders.py` | Discord embed factory functions |
| `docker-compose.prod.yml` | Production stack |

---

## Dashboard SPA

The web dashboard is served at `/` and is a **vanilla JS + Tailwind CDN app — no build step**. The JS is split across four files loaded in dependency order:

```html
<script src="/static/js/constants.js"></script>
<script src="/static/js/components.js"></script>
<script src="/static/js/mobile.js"></script>
<script src="/static/js/app.js"></script>
```

**Load order is critical** — all globals are `window`-scoped, so later files depend on earlier ones.

### File responsibilities

| File | Contains |
|---|---|
| `constants.js` | `DD`, `TIER_COLOR`, `TIER_LABEL`, `ROMAN`, `QUEUE_LABEL`, `QUEUE_MODE`, `CHAMP_KEYS`, `champKey()`, `fmtDuration()`, `fmtDate()`, `dateBucket()`, `timeAgo()` |
| `components.js` | `$()`, `mount()`, `StatsRow`, `ChampGridItem`, `MatchCard`, `RankBadge`, `ParticipantRow`, `TeamTable`, `MatchOutcomeBar`, skeleton helpers |
| `mobile.js` | `mobileView`, `isMobile()`, `setMobilePanel(panel)` — panels: `'list'` `'profile'` `'matches'` `'match-detail'` |
| `app.js` | All global state, every render/API/event function, and the `setupModalAutocomplete(); init();` bootstrap |

### Global state (in `app.js`)
```js
DD              // DDragon CDN base URL (updated to latest version in init)
allSummoners    // full summoner list from API
activeSummonerId
activeMatches
activeStats
activeRank
activeMode      // 'all' | 'ranked' | 'normal' | 'aram'
activeMatchEl   // currently selected match DOM element
chartWR         // Chart.js doughnut (winrate ring)
chartDUR        // Chart.js combo bar+line (duration win%)
durationCache   // { [riot_id]: result } — in-memory cache per summoner
```

### Key flow
1. **`selectSummoner(riot_id)`** — fetches matches + stats + rank in parallel, calls `renderProfile()` + `runDurationAnalysis()`.
2. **`renderProfile(mode)`** — builds stats row, champ grid, profile header (splash crossfade + rank badge), triggers duration chart.
3. **`runDurationAnalysis(force=false)`** — checks `durationCache` first; if miss, POSTs task, polls every 2s, calls `renderDurationResult()` on success. The ↻ button passes `force=true`.
4. **`selectMatch(match_id)`** — hides profile view, shows match view with team tables.
5. **`closeMatch()`** / **`closeProfile()`** — restore previous state.

### Adding a new UI component
1. Add the pure function to `components.js` (returns an HTML string, no side effects).
2. Use `mount('element-id', MyComponent(data))` from `app.js` to render it.

### CommunityDragon assets
Rank mini-crests:
```
https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-mini-crests/{tier}.svg
```
`{tier}` must be **lowercase** (e.g. `gold`, `platinum`, `diamond`).

### Chart.js notes
- Always call `chart.destroy()` before re-creating a chart on the same canvas.
- Duration card uses `maintainAspectRatio: false` with the canvas inside an `absolute inset-0` wrapper so it fills its flex parent.

---

## Celery task pattern

### Creating a task

```python
# api/tasks/my_task.py
from .celery_app import celery_app

@celery_app.task(bind=True)
def my_task(self, riot_id, region):
    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})
    # ... work ...
    return {"result": ...}
```

### Enqueue + poll via API

```
POST /api/tasks/my-task          → { "task_id": "..." }
GET  /api/tasks/{task_id}        → { "status": "SUCCESS"|"PENDING"|"PROGRESS"|"FAILURE", "result": {...} }
```

### Redis progress key pattern
For sync-all tasks that write live progress:
```python
PROGRESS_KEY = "sync:progress"   # must match GET /api/db/sync-progress
r.set(PROGRESS_KEY, json.dumps({"status": "running", "current": n, "total": total}))
```

---

## `slim(p)` — match participant fields

`api/routes/db.py` exposes a `slim(p)` function that strips raw Riot data down to what the UI needs. Currently includes:

```python
"champion", "kills", "deaths", "assists", "win", "teamId",
"totalDamageDealtToChampions", "cs", "visionScore", "goldEarned",
"damageDealtToTurrets", "puuid", "name"
```

Add fields here first before using them in the dashboard.

---

## Deployment workflow

### Rebuild only the API (most common)
```bash
docker compose -f docker-compose.prod.yml up -d --build api
```

### Rebuild everything
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Tail logs
```bash
docker logs -f capitan-api
docker logs -f capitan-celery-worker
docker logs -f capitan-coditos   # discord bot
```

### Port note
macOS AirPlay occupies 5000. Production compose maps **host 5001 → container 5000**.

---

## Common gotchas

| Symptom | Cause | Fix |
|---|---|---|
| Duration chart overflows / doesn't fill card | `maintainAspectRatio` default is `true` | Set `maintainAspectRatio: false`, wrap canvas in `absolute inset-0` div |
| Rank badge not visible | Dark pill on dark banner | Add tier-colored border + opaque background to the badge pill |
| Splash image blinks on summoner switch | Hard-clearing `backgroundImage` | Set `opacity: 0`, preload via `new Image()`, set URL + `opacity: 1` in `onload` |
| `sync:progress` returning stale/null | Task key and route key mismatch | Both must use the same constant (`PROGRESS_KEY = "sync:progress"`) |
| CommunityDragon SVG 404 | Wrong plugin path or uppercase tier | Use `rcp-fe-lol-static-assets` and lowercase tier names |
| Stats capped at 250 games | `.limit(250)` left in `get_summoner_match_stats()` | Remove the `.limit()` call in `api/database/match_cache.py` |
| Task stuck in PENDING | Celery worker not connected | Check `docker logs capitan-celery-worker`; verify Redis URL |

---

## Tips for AI-assisted sessions

- **Paste the summary from the previous session** into the chat at the start. The conversation summary block captures all global state, pending work, and last known code locations.
- **Provide screenshots** when a visual bug is hard to describe — the AI can read layout issues from them.
- **Mention the line number or function name** when asking about a specific bug. The AI will read those lines before editing.
- **One concern at a time** works best for layout edits; for backend changes you can batch related files.
- **Multi-file edits** are applied atomically in one tool call — safe to do for related route + task + template changes together.
- **After every deploy**, check `docker logs capitan-api` for Python errors before reporting a UI bug — often the issue is a 500 from the API, not the JS.
