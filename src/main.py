import logging
import os
import re
import uuid
from pathlib import Path

import humanize as hmz
from dotenv import load_dotenv
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

from src.instagram import client as igc

logging.basicConfig(
    level=logging.WARN,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logging.getLogger('https').setLevel(logging.CRITICAL)

log = logging.getLogger(__name__)

reel_url_pattern = re.compile(r".*instagram\.com/(p|reel).*")


async def instagram_inline_query_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    query, username, user_id = update.inline_query.query, update.effective_user.username, update.effective_user.id
    log.warning('[instagram][%s][%s] inline query received: %s', user_id, username, query)

    if whitelist_enabled and user_id not in whitelist:
        await update.inline_query.answer([], is_personal=True)
        return

    info = await ic.get_media_info_from_url(query)
    if not info:
        await update.inline_query.answer([], is_personal=True)
        return

    counters = ' '.join(
        [counter for counter in [
            f'👀{hmz.scientific(info.view_count or info.play_count, precision=2)}' if info.view_count or info.play_count else None,
            f'❤️{hmz.scientific(info.like_count, precision=2)}' if info.like_count else None,
            f'💬{hmz.scientific(info.comment_count, precision=2)}' if info.comment_count else None,
        ] if counter]
    )

    source = f'🔗https://instagram.com/reel/{info.code}'

    await update.inline_query.answer(
        [
            InlineQueryResultVideo(
                id=f'{username}:{info.code}',
                video_url=info.video_url,
                mime_type='video/mp4',
                thumbnail_url=info.thumbnail_url,
                title=info.code,
                caption=f'{counters}\n{source}',
                video_duration=int(info.video_duration),
                video_height=1920,
                video_width=1080,
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


if __name__ == '__main__':
    load_dotenv()

    path = Path(os.getenv('SESSIONS_PATH'))
    log.warning("using sessions from %s", path)

    ic = igc.Client(
        username=os.getenv('USERNAME'),
        password=os.getenv('PASSWORD'),
        path=path,
        proxy=os.getenv('PROXY'),
    )
    ic.warmup()

    whitelist_enabled = bool(int(os.getenv('WHITELIST_ENABLED')))

    whitelist = []
    if whitelist_enabled:
        whitelist = [int(item) for item in os.getenv('WHITELIST').split(',')]

    bot_url = os.getenv('BOT_URL')
    bot_token = os.getenv('BOT_TOKEN')
    bot_port = int(os.getenv('BOT_PORT'))
    bot_use_polling = bool(int(os.getenv('BOT_USE_POLLING')))

    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(
        InlineQueryHandler(
            instagram_inline_query_handler,
            pattern=reel_url_pattern,
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
