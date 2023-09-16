import asyncio as aio
import logging
from typing import Optional

import instagrapi as ig
import instagrapi.exceptions as igexc
import instagrapi.types as igtypes

log = logging.getLogger(__name__)

_semaphore = aio.Semaphore(1)


async def get_media_info_from_url(c: ig.Client, url: str) -> Optional[igtypes.Media]:
    async with _semaphore:
        return await aio.get_event_loop().run_in_executor(None, _get_media_info_from_url, c, url)


def _get_media_info_from_url(c: ig.Client, url: str) -> Optional[igtypes.Media]:
    pk = c.media_pk_from_url(url)
    try:
        return c.media_info_v1(pk)
    except igexc.ClientError:
        log.error("failed to get media info")
        return None