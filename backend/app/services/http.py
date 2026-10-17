"""Pooled HTTP clients. Building an httpx client loads the CA bundle and makes a fresh TLS handshake, about 30 ms of
CPU each time; at WhatsApp volume that alone capped a worker near 12 messages a second. One client per provider and
event loop keeps connections alive and reuses the TLS context."""

import asyncio
from typing import Any

import httpx

_clients: dict[str, tuple[Any, asyncio.AbstractEventLoop, httpx.AsyncClient]] = {}


def shared(name: str, **options: Any) -> httpx.AsyncClient:
    """The pooled client for `name` on this event loop. A new loop (tests, a reload) or a swapped httpx.AsyncClient
    (a test transport) gets a new client, so nothing leaks across them."""
    loop = asyncio.get_running_loop()
    found = _clients.get(name)
    if found and found[0] is httpx.AsyncClient and found[1] is loop and not found[2].is_closed:
        return found[2]
    client = httpx.AsyncClient(**options)
    _clients[name] = (httpx.AsyncClient, loop, client)
    return client


async def close_all() -> None:
    loop = asyncio.get_running_loop()
    for name, (_, owner, client) in list(_clients.items()):
        if owner is loop:
            await client.aclose()
            _clients.pop(name, None)
