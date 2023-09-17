import asyncio as aio
import json
import logging
from pathlib import Path
from typing import (
    Optional,
)

import instagrapi as ig
import instagrapi.exceptions as igexc
import instagrapi.types as igtypes

log = logging.getLogger(__name__)

_semaphore = aio.Semaphore(1)

_client: Optional[ig.Client] = None
_client_is_ready: bool = False
_client_lock = aio.Lock()


class Client:
    def __init__(self, username: str, password: str, path: Path, proxy: Optional[str] = None):
        self._lock = aio.Lock()
        self._semaphore = aio.Semaphore(1)

        self._client: Optional[ig.Client] = None
        self._client_is_ready: bool = False

        self.username = username
        self.password = password
        self.path = path / f'{self.username}.json'
        self.proxy = proxy

    def warmup(self):
        aio.get_event_loop().run_until_complete(self.get_client())

    async def get_client(self) -> Optional[ig.Client]:
        global _client
        global _client_is_ready

        async with self._lock:
            if self._client_is_ready:
                return self._client

            self._client = await self._get_client()
            self._client_is_ready = True

        return self._client

    async def _get_client(self) -> Optional[ig.Client]:
        loop = aio.get_event_loop()
        return await loop.run_in_executor(None, self._get_client_sync)

    def _get_client_sync(self) -> Optional[ig.Client]:
        c = ig.Client()

        c.set_proxy(self.proxy)

        try:
            c.load_settings(self.path)
            c.get_timeline_feed()
            return c
        except igexc.LoginRequired:
            log.warning("failed to use session", exc_info=True)
            uuids = c.get_settings()['uuids']
            c.set_settings({})
            c.set_uuids(uuids)
            c.dump_settings(self.path)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            log.error("failed to load session: %s", exc)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch()

        try:
            c.login(self.username, self.password)
            c.dump_settings(self.path)
        except igexc.ClientError:
            log.error("failed to login", exc_info=True)
            return None

        return c

    async def invalidate_client(self):
        async with self._lock:
            self._client = None
            self._client_is_ready = False

    async def get_media_info_from_url(self, url: str) -> Optional[igtypes.Media]:
        c = await self.get_client()
        async with self._semaphore:
            try:
                return await aio.get_event_loop().run_in_executor(None, self._get_media_info_from_url, c, url)
            except igexc.LoginRequired:
                await self.invalidate_client()
                return None

    @staticmethod
    def _get_media_info_from_url(c: ig.Client, url: str) -> Optional[igtypes.Media]:
        pk = c.media_pk_from_url(url)
        try:
            return c.media_info_v1(pk)
        except igexc.ClientError:
            log.error("failed to get media info")
            return None
