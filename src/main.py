import json
import logging
import os
import random
import re
import string
import uuid
from pathlib import Path

import instagrapi as ig
import sentry_sdk as ss
from dotenv import load_dotenv
from instagrapi import exceptions as igexc
from pytube import YouTube
from telegram import (
    InlineQueryResultVideo,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    InlineQueryHandler,
)

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)

log = logging.getLogger(__name__)


async def instagram_inline_query_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    log.warning(
        '[instagram][%s][%s] inline query received: %s',
        update.effective_user.id,
        update.effective_user.username,
        update.inline_query.query,
    )

    try:
        pk = c.media_pk_from_url(update.inline_query.query)
        info = c.media_info_v1(pk)
    except Exception:
        log.exception(
            '[instagram][%s][%s] inline query failed: %s',
            update.effective_user.id,
            update.effective_user.username,
            update.inline_query.query,
        )
        await update.inline_query.answer([], is_personal=True, cache_time=0)
        return

    await update.inline_query.answer(
        [
            InlineQueryResultVideo(
                id=str(uuid.uuid4()),
                video_url=info.video_url,
                mime_type='video/mp4',
                thumbnail_url=info.thumbnail_url,
                title=info.title or c.media_code_from_pk(pk),
                # caption=info.caption_text,
                video_duration=int(float(info.video_duration)),
                video_width=1080,
                video_height=1920,
            )
        ],
        is_personal=True,
        cache_time=0,
    )


async def youtube_inline_query_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    log.info(
        'youtube inline query received, user_id=%s, username=%s, query=%s',
        update.effective_user.id,
        update.effective_user.username,
        update.inline_query.query,
    )
    try:
        yt = YouTube(update.inline_query.query)
        stream = yt.streams.filter().get_highest_resolution()
        video_url = stream.url
    except Exception:
        log.exception(
            'youtube inline query failed, user_id=%s, username=%s, query=%s',
            update.effective_user.id,
            update.effective_user.username,
            update.inline_query.query,
        )
        await update.inline_query.answer([], is_personal=True, cache_time=0)
        return

    await update.inline_query.answer(
        [
            InlineQueryResultVideo(
                id=str(uuid.uuid4()),
                video_url=video_url,
                mime_type=stream.mime_type,
                thumb_url=yt.thumbnail_url,
                title=yt.title,
                # caption=info.caption_text,
                video_duration=yt.length,
                # video_width=1080,
                # video_height=1920,
            )
        ],
        is_personal=True,
        cache_time=0,
    )


def login(
        client: ig.Client,
        username: str,
        password: str,
        verification_code: str,
        session_settings_path: Path,
):
    try:
        session = c.load_settings(session_settings_path)
    except (FileNotFoundError, json.JSONDecodeError):
        session = None

    if session:
        client.set_settings(session)
        try:
            client.get_timeline_feed()
        except igexc.LoginRequired:
            old_session = client.get_settings()
            client.set_settings({})
            client.set_uuids(old_session['uuids'])
            client.login(
                username=username,
                password=password,
                verification_code=verification_code,
            )
            client.dump_settings(session_settings_path)

        return

    client.login(
        username=username,
        password=password,
        verification_code=verification_code,
    )
    client.dump_settings(session_settings_path)


if __name__ == '__main__':
    load_dotenv()

    if sentry_dsn := os.getenv('SENTRY_DSN'):
        ss.init(
            dsn=sentry_dsn,
            traces_sample_rate=1.0,
        )

    session_username = os.getenv('IG_USERNAME')
    session_password = os.getenv('IG_PASSWORD')
    session_verification_code = os.getenv('IG_VERIFICATION_CODE')
    session_settings_path = Path(os.getenv('IG_SETTINGS_PATH'))

    c = ig.Client(logger=log, delay_range=[1, 5])
    login(c, session_username, session_password, session_verification_code, session_settings_path)

    bot_url = os.getenv('BOT_URL')
    bot_token = os.getenv('BOT_TOKEN')
    bot_port = int(os.getenv('BOT_PORT'))

    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(
        InlineQueryHandler(
            instagram_inline_query_handler,
            pattern=re.compile(r".*instagram\.com/reel.*"),
        )
    )
    app.add_handler(
        InlineQueryHandler(
            youtube_inline_query_handler,
            pattern=re.compile(r".*youtube\.com/shorts.*"),
        )
    )
    app.run_webhook(
        listen='0.0.0.0',
        port=bot_port,
        url_path=bot_token,
        webhook_url='/'.join([bot_url, bot_token]),
    )
