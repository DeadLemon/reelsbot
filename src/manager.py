import asyncio as aio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

import instagrapi as ig
import instagrapi.exceptions as igexc
import instagrapi.types as igtypes

log = logging.getLogger(__name__)


class Manager:
    def __init__(self, path: Path):
        self.path = path

        self._clients = aio.Queue()

    async def add_client_by_url(self, url: str):
        if c := await self.get_client(url):
            self._clients.put_nowait(c)

    async def get_client(self, url: str) -> Optional[ig.Client]:
        return await aio.get_event_loop().run_in_executor(None, self._get_client_sync, url)

    def _get_client_sync(self, url: str) -> Optional[ig.Client]:
        parsed = urlparse(url)
        username, password, proxy, path = (
            parsed.username,
            parsed.password,
            urlunparse(parsed),
            self.path / f'{parsed.username}.json'
        )

        log.warning("initializing client username=%s password=%s proxy=%s, path=%s",
                    username, password, proxy, path)

        c = ig.Client(proxy=proxy)

        try:
            log.warning("trying to use session file: %s", path)
            c.load_settings(path)
            c.get_timeline_feed()
            return c
        except igexc.LoginRequired as exc:
            log.warning("failed to use session: %s", exc)
            uuids = c.get_settings()['uuids']
            c.set_settings({})
            c.set_uuids(uuids)
            c.dump_settings(path)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            log.error("failed to load session: %s", exc)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

        try:
            log.warning("trying to login using credentials...")
            c.login(username, password)
            c.dump_settings(path)
        except igexc.ClientError as exc:
            log.error("failed to login: %s", exc)
            return None

        log.warning("initializing client username=%s password=%s proxy=%s, path=%s",
                    url, username, password, proxy, path)
        return c

    async def get_media_info_from_url(self, url: str) -> igtypes.Media:
        c: ig.Client
        async with self._client() as c:
            pk = c.media_pk_from_url(url)
            return c.media_info_v1(pk)

    @asynccontextmanager
    async def _client(self) -> ig.Client:
        log.warning("client waiting")
        c: ig.Client = await self._clients.get()
        log.warning("client acquired")
        try:
            yield c
        except Exception:
            log.error("error occurred while using client")
            ...
        else:
            log.warning("client returning")
            await self._clients.put(c)
