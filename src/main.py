import json
import logging
import os
import re
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

    answers = []
    try:
        yt = YouTube(update.inline_query.query)
        answers = [
            InlineQueryResultVideo(
                id=str(uuid.uuid4()),
                video_url=stream.url,
                mime_type=stream.mime_type,
                thumb_url=yt.thumbnail_url,
                title="[{}][{} mb] {}".format(stream.resolution, stream.filesize_mb, yt.title),
                video_duration=yt.length,
            )
            for stream in yt.streams.filter(only_video=True, file_extension='mp4')
            if stream.filesize_mb < 50
        ]
    except Exception:
        log.exception(
            'youtube inline query failed, user_id=%s, username=%s, query=%s',
            update.effective_user.id,
            update.effective_user.username,
            update.inline_query.query,
        )

    await update.inline_query.answer(answers, is_personal=True, cache_time=0)


def login(
        client: ig.Client,
        username: str,
        password: str,
        settings_path: Path,
):
    try:
        session = c.load_settings(settings_path)
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
            )
            client.dump_settings(settings_path)

        return

    client.login(
        username=username,
        password=password,
    )
    client.dump_settings(settings_path)


if __name__ == '__main__':
    load_dotenv()

    if sentry_dsn := os.getenv('SENTRY_DSN'):
        ss.init(
            dsn=sentry_dsn,
            traces_sample_rate=1.0,
        )

    session_username = os.getenv('IG_USERNAME')
    session_password = os.getenv('IG_PASSWORD')
    session_settings_path = Path(os.getenv('IG_SETTINGS_PATH'))

    proxy_dsn = os.getenv('PROXY_DSN')

    c = ig.Client(logger=log, delay_range=[1, 3])
    c.set_proxy(proxy_dsn)
    login(c, session_username, session_password, session_settings_path)
    log.warning("successfully logged in, username: %s", session_username)

    bot_url = os.getenv('BOT_URL')
    bot_token = os.getenv('BOT_TOKEN')
    bot_port = int(os.getenv('BOT_PORT'))
    bot_use_polling = bool(int(os.getenv('BOT_USE_POLLING')))

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
    if bot_use_polling:
        app.run_polling()
    else:
        app.run_webhook(
            listen='0.0.0.0',
            port=bot_port,
            url_path=bot_token,
            webhook_url='/'.join([bot_url, bot_token]),
        )
