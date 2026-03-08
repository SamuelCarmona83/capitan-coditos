"""
Async HTTP client used by bot commands to call the Flask API.
Uses a single shared aiohttp.ClientSession (initialized once on first use).
"""
import asyncio
import os
from typing import Any
from urllib.parse import quote

import aiohttp

API_BASE: str = os.getenv("API_BASE_URL", "http://api:5000")

_session: aiohttp.ClientSession = None
_session_lock = asyncio.Lock()


async def _get_session() -> aiohttp.ClientSession:
    global _session
    async with _session_lock:
        if _session is None or _session.closed:
            _session = aiohttp.ClientSession(
                base_url=API_BASE,
                timeout=aiohttp.ClientTimeout(total=600),  # long for Celery task polling
            )
    return _session


def _encode_path(path: str) -> str:
    """Percent-encode characters that break URL parsing (e.g. '#' in Riot IDs)."""
    return quote(path, safe='/:?=&@')


async def get(path: str, params: dict = None) -> Any:
    session = await _get_session()
    async with session.get(_encode_path(path), params=params) as resp:
        resp.raise_for_status()
        return await resp.json()


async def post(path: str, json: dict = None) -> Any:
    session = await _get_session()
    async with session.post(_encode_path(path), json=json) as resp:
        resp.raise_for_status()
        if resp.status == 204:
            return {}
        return await resp.json()


async def poll_task(task_id: str, progress_callback=None, poll_interval: float = 5.0) -> dict:
    """
    Poll GET /api/tasks/<task_id> until SUCCESS or FAILURE.
    Calls progress_callback(current, total) whenever state is PROGRESS.
    Returns the final result dict.
    Raises RuntimeError on FAILURE.
    """
    while True:
        status = await get(f"/api/tasks/{task_id}")
        state = status.get("status")

        if state == "PROGRESS" and progress_callback:
            prog = status.get("progress") or {}
            await progress_callback(prog.get("current", 0), prog.get("total", 0))

        if state == "SUCCESS":
            return status.get("result", {})

        if state == "FAILURE":
            raise RuntimeError(status.get("error", "Task failed"))

        await asyncio.sleep(poll_interval)
