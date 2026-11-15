"""Expiry is a database state transition; it never sends SMTP."""

import asyncio
import logging
from contextlib import asynccontextmanager

from .scheduling import expire_due


@asynccontextmanager
async def lifespan(app):
    stop = asyncio.Event()

    async def loop():
        while not stop.is_set():
            try:
                await asyncio.to_thread(expire_due)
            except Exception:
                logging.error(
                    "Proposal expiry sweep failed; will retry on next interval"
                )
            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
            except TimeoutError:
                pass

    task = asyncio.create_task(loop())
    try:
        yield
    finally:
        stop.set()
        await task
